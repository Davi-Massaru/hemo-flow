from datetime import timedelta
from hemoflow.common import now,stamp
from hemoflow.projections import simulate,proposed_receipts

def test_expiring_stock_does_not_cover_later_days():
    own=dict(status='AVAILABLE',expiry_buckets=[dict(units=14,expiresAt=stamp(now()+timedelta(hours=12)))])
    result=simulate(own,dict(method='INTEGRATEDML',expected_units=14))
    assert result['deficit']==14 and result['stock']==[0]*7

def test_unavailable_sources_never_produce_projection():
    assert simulate(dict(status='UNAVAILABLE'),dict(method='INTEGRATEDML',expected_units=14)) is None
    assert proposed_receipts({},dict(status='UNAVAILABLE'),{})==[]

def test_timed_hypothesis_preserves_confirmed_stock():
    own=dict(status='AVAILABLE',expiry_buckets=[])
    forecast=dict(method='INTEGRATEDML',expected_units=14)
    source=dict(status='AVAILABLE',transferable_units=10,handling_lead_hours=4,expiry_buckets=[dict(units=10,expiresAt=stamp(now()+timedelta(days=12)))])
    receipts=proposed_receipts(dict(requested_units=6,need_by=stamp(now()+timedelta(days=7))),source,forecast)
    assert simulate(own,forecast)['deficit']==14
    assert simulate(own,forecast,receipts)['deficit']==8
    assert own['expiry_buckets']==[]
