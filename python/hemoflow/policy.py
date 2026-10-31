"""Deterministic candidate construction and independent validation after the LLM."""
import json, math
from datetime import timedelta
from jsonschema import Draft202012Validator, FormatChecker
from .common import ROOT, COMPONENT, BLOOD, date, now, stamp, require

SCHEMA=json.loads((ROOT/'schemas/decision.schema.json').read_text())
VALIDATOR=Draft202012Validator(SCHEMA,format_checker=FormatChecker())

def gap(forecast,own,confirmed=(),at=None):
    require(own['status']=='AVAILABLE','Local stock unavailable',503)
    # Daily FEFO simulation: units expiring before consumption never cover later days.
    daily=forecast['expected_units']/7
    buckets=[{'expires':date(b['expiresAt']),'units':b['units']} for b in own['expiry_buckets']]
    # own usable stock includes institutional reserve; remote offers do not.
    if 'usable_buckets' in own:
        buckets=[{'expires':date(b['expiresAt']),'units':b['units']} for b in own['usable_buckets']]
    unmet=0.0
    anchor=at or now()
    for day in range(1,8):
        at=anchor+timedelta(days=day)
        remaining=daily
        for receipt in confirmed:
            if anchor+timedelta(days=day-1)<date(receipt['available_at'])<=at:
                buckets.append({'expires':date(receipt['expires_at']),'units':receipt['units']})
        for bucket in sorted(buckets,key=lambda b:b['expires']):
            if bucket['expires']<=at: continue
            use=min(bucket['units'],remaining)
            bucket['units']-=use; remaining-=use
        unmet+=remaining
    return int(math.ceil(max(0,unmet)-1e-8))

def transfer_capacity(remote,forecast,need_by):
    if remote['status']!='AVAILABLE': return 0
    arrival=now()+timedelta(hours=remote['handling_lead_hours'])
    if arrival>date(need_by): return 0
    used_capacity=0
    # A unit must be usable after arrival + one day's handling/consumption margin.
    for bucket in sorted(remote['expiry_buckets'],key=lambda b:b['expiresAt']):
        days=max(0,min(7,(date(bucket['expiresAt'])-arrival).total_seconds()/86400-1))
        capacity=max(0,math.floor(days*forecast['expected_units']/7)-used_capacity)
        used_capacity+=min(bucket['units'],capacity)
    return min(used_capacity,remote['transferable_units'])

def network_gap(context,offers,at):
    """Compare hypothetical offers together without treating them as confirmed stock.

    Shared FEFO prevents origins from claiming the same demand before expiry.
    Keep the one-day usage margin used to size offers. This projection decides
    whether a campaign may be considered; it never reduces its target.
    """
    forecast=context['forecast']
    own=next(row for row in context['network'] if row['center_id']==context['center_id'])
    receipts=list(context.get('confirmed_receipts',[]))
    by_center={row['center_id']:row for row in context['network']}
    for offer in offers:
        remote=by_center[offer['source_center_id']]
        arrival=at+timedelta(hours=remote['handling_lead_hours'])
        available=max(arrival,at+timedelta(microseconds=1))
        remaining=offer['requested_units']; allocated=0
        for bucket in sorted(remote['expiry_buckets'],key=lambda b:b['expiresAt']):
            expires=date(bucket['expiresAt'])-timedelta(days=1)
            days=max(0,min(7,(expires-arrival).total_seconds()/86400))
            capacity=max(0,math.floor(days*forecast['expected_units']/7)-allocated)
            units=min(bucket['units'],capacity,remaining)
            if units:
                receipts.append(dict(available_at=available.isoformat(),expires_at=expires.isoformat(),units=units))
                allocated+=units;remaining-=units
            if not remaining:break
    return gap(forecast,own,receipts,at=at)


def candidates(context):
    forecast,network=context['forecast'],context['network']
    if forecast.get('method')!='INTEGRATEDML' or forecast.get('quality_flags'):
        return []
    if any(row['status']!='AVAILABLE' for row in network): return []
    own=next(row for row in network if row['center_id']==context['center_id'])
    anchor=now()
    deficit=gap(forecast,own,context.get('confirmed_receipts',[]),at=anchor)
    base=dict(schema_version='1.0',request_id=context['id'],component=COMPONENT,blood_type=context.get('blood_type',BLOOD),
              need_by=context['need_by'],evidence_ids=context['evidence_ids'],requires_approval=True)
    offers=[]
    for row in network:
        if row['center_id']==context['center_id']: continue
        count=min(deficit,transfer_capacity(row,forecast,context['need_by']))
        if count:
            offers.append(dict(base,decision='REQUEST_TRANSFER',source_center_id=row['center_id'],
                target_center_id=context['center_id'],requested_units=count,inventory_observed_at=row['observed_at']))
    if deficit:
        # Reconcile offers on a shared demand/expiry timeline before deciding
        # whether the network is sufficient; partial supply leaves a choice.
        if offers and not network_gap(context,offers,anchor):return offers
        # Confirmed campaign plans never count as stock, but block overlapping duplicate plans.
        if context.get('active_campaigns'): return offers
        for partner in context['partners']:
            collection=date(context['created_at'])+timedelta(hours=partner['organize_hours'])
            end=collection+timedelta(hours=partner['collection_hours'])
            release=end+timedelta(hours=partner['processing_hours'])
            if release<=date(context['need_by']):
                offers.append(dict(base,decision='REQUEST_CAMPAIGN',requesting_center_id=context['center_id'],
                    partner_id=partner['id'],target_units=min(deficit,partner['capacity']),
                    campaign_window_start=stamp(collection),campaign_window_end=stamp(end),expected_available_at=stamp(release)))
        return offers
    # NO_ACTION only if no remote near-expiry stock can usefully reduce avoidable waste.
    for row in network:
        if row['center_id']==context['center_id']: continue
        if any(date(b['expiresAt'])<now()+timedelta(days=3) and b['units'] for b in row['expiry_buckets']):
            return []
    return [dict(schema_version='1.0',request_id=context['id'],decision='NO_ACTION',
                 evidence_ids=context['evidence_ids'],requires_approval=False)]

def guard(decision,context,allowed):
    errors=list(VALIDATOR.iter_errors(decision))
    require(not errors,'Invalid decision schema: '+('; '.join(error.message for error in errors))[:400])
    require(decision['request_id']==context['id'],'Wrong decision correlation')
    require(set(decision['evidence_ids'])<=set(context['evidence_ids']),'Unknown evidence ID')
    if 'evidence_version' in context:
        require(set(decision['evidence_ids'])==set(context['evidence_ids']),
                'Decision must cite all current evidence IDs')
    require((now()-date(context['created_at'])).total_seconds()<=120,'Decision context stale')
    require(allowed,'No safe candidate')
    fields=set(decision)-{'reason','evidence_ids'}
    legacy_transfer=decision['decision']=='REQUEST_TRANSFER' and 'evidence_version' not in context
    if legacy_transfer:
        source=decision['source_center_id']
        observed=context.get('inventory_observations',{}).get(source,[])
        require(decision['inventory_observed_at'] in observed or any(
            candidate.get('inventory_observed_at')==decision['inventory_observed_at'] for candidate in allowed),
            'Inventory timestamp lacks a real tool observation')
        fields.discard('inventory_observed_at')
    # Exact candidate matching prevents quantity/date/identity invention and conflicting extra fields.
    ignored={'reason','evidence_ids'} | ({'inventory_observed_at'} if legacy_transfer else set())
    require(any(fields==set(candidate)-ignored and
                all(decision[key]==candidate[key] for key in fields) for candidate in allowed),
            'Decision is not an authorized candidate')
    return decision
