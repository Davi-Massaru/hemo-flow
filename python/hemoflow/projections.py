"""Temporal FEFO projections, distinct from measured stock and model forecasts."""
from datetime import timedelta
from .common import now,stamp,date
from . import policy

def simulate(own,forecast,receipts=()):
    if not own or own.get('status')!='AVAILABLE' or forecast.get('method')!='INTEGRATEDML' or forecast.get('quality_flags'):
        return None
    buckets=[dict(units=b['units'],expires=date(b['expiresAt'])) for b in own.get('usable_buckets',own.get('expiry_buckets',[]))]
    daily=forecast['expected_units']/7;remaining_stock=[];shortages=[];days=[];anchor=now()
    for day in range(1,8):
        at=anchor+timedelta(days=day);need=daily
        for receipt in receipts:
            if anchor+timedelta(days=day-1)<date(receipt['available_at'])<=at:
                buckets.append(dict(units=receipt['units'],expires=date(receipt['expires_at'])))
        for bucket in sorted(buckets,key=lambda b:b['expires']):
            if bucket['expires']<=at:bucket['units']=0;continue
            used=min(need,bucket['units']);bucket['units']-=used;need-=used
        days.append(stamp(at)[:10]);remaining_stock.append(round(sum(b['units'] for b in buckets),2));shortages.append(round(need,2))
    return dict(days=days,stock=remaining_stock,unmet=shortages,deficit=policy.gap(forecast,own,receipts))

def proposed_receipts(transfer,source,forecast):
    if not source or source.get('status')!='AVAILABLE':return []
    count=transfer['requested_units']
    if policy.transfer_capacity(source,forecast,transfer['need_by'])<count:return []
    arrival=now()+timedelta(hours=source['handling_lead_hours']);result=[]
    for bucket in sorted(source['expiry_buckets'],key=lambda b:b['expiresAt']):
        if date(bucket['expiresAt'])<=arrival+timedelta(days=1):continue
        units=min(count,bucket['units'])
        if units:result.append(dict(units=units,available_at=stamp(arrival),expires_at=bucket['expiresAt']))
        count-=units
        if not count:break
    return result if not count else []
