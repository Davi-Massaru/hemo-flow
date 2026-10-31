"""Synthetic operational measurements; comparison is a hypothesis, never clinical gain."""
from datetime import timedelta
from .common import now,date
from . import policy

def risk(context):
    own=next((r for r in context['network'] if r['center_id']==context['center_id']),None)
    deficit=policy.gap(context['forecast'],own) if own and own['status']=='AVAILABLE' else None
    exposure=sum(b['units'] for r in context['network'] if r['status']=='AVAILABLE'
                 for b in r['expiry_buckets'] if now()<date(b['expiresAt'])<=now()+timedelta(days=3))
    return dict(center_id=context['center_id'],component='RED_BLOOD_CELLS',blood_type=context.get('blood_type','O-'),
                deficit=deficit,expiry_exposure=exposure,complete=all(r['status']=='AVAILABLE' for r in context['network']))

def dashboard(decisions,transfers,campaigns,network):
    previous=next((d for d in decisions if d.get('kpi_before') and d.get('forecast')),None)
    before=previous.get('kpi_before') if previous else None
    after=risk(dict(network=network,center_id=before['center_id'],blood_type=before.get('blood_type','O-'),forecast=previous['forecast'])) if previous and network else None
    return dict(before=before,after=after,received=sum(t.get('received_units',0) for t in transfers),
                used=sum(t.get('used_units',0) for t in transfers),campaigns=len(campaigns),
                approved=sum(c.get('status') in ('AWAITING_PARTNER','CONFIRMED','COMPLETED') for c in campaigns),
                released=sum(c.get('released_usable',0) for c in campaigns),
                blocked=sum(d['status'] in ('ESCALATED','INVALID_OUTPUT') for d in decisions))
