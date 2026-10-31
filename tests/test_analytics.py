"""Chart integrity and access checks, running against isolated read fixtures."""
from datetime import timedelta
import pytest
from hemoflow import analytics as a
from hemoflow.common import Problem,stamp,now

@pytest.fixture
def data(monkeypatch):
    centers=[dict(id='A',name='A',scope='A'),dict(id='B',name='B',scope='B')]
    records={'NetworkCenter':centers}
    monkeypatch.setattr(a.repo,'all',lambda kind,**kw:records.get(kind,[]))
    monkeypatch.setattr(a,'demo',lambda:True)
    monkeypatch.setattr(a.federation,'inventory',lambda identity,*args:dict(center_id=identity,blood_type=args[-1],status='UNAVAILABLE',observed_at=stamp()) if identity=='B' or args[-1]!='O-' else dict(center_id='A',blood_type=args[-1],status='AVAILABLE',available_units=12,transferable_units=8,expiry_buckets=[dict(units=8,expiresAt=stamp(now()+timedelta(days=2)))],observed_at=stamp()))
    monkeypatch.setattr(a.intelligence,'forecast',lambda center,*args:dict(method='BASELINE',expected_units=99))
    return records

def test_missing_inventory_and_baseline_never_become_stock_or_automl(data):
    result=a.build('panel',dict(role='admin',scope='NETWORK'))
    charts={c['id']:c for c in result['charts']}
    assert charts['stock_forecast']['series'][0]['data']==[12,None]
    assert charts['stock_forecast']['series'][1]['data']==[None,None]
    assert charts['blood_distribution']['series'][0]['data']==[12]+[None]*7
    assert result['unavailable']==['B']

def test_demo_records_are_hidden_when_demo_disabled(monkeypatch):
    monkeypatch.setattr(a,'demo',lambda:False)
    rows=[dict(id='real'),dict(id='DEMO-example'),dict(id='x',demo_run_id='run'),dict(id='e',event='DEMO_RESTORED'),dict(id='d',scope='A')]
    assert a.visible(rows,{'A'})==[dict(id='real')]

def test_analytics_permissions_and_filters(data):
    with pytest.raises(Problem):a.build('audit',dict(role='manager',scope='A'))
    with pytest.raises(Problem):a.build('network',dict(role='donor',scope='D'))
    with pytest.raises(Problem):a.build('panel',dict(role='admin'),days=999)
    with pytest.raises(Problem):a.build('network',dict(role='admin'),selected='UNKNOWN')

def test_hypothetical_transfer_does_not_count_delivered_stock_twice(data,monkeypatch):
    data['Transfer']=[dict(id='open',scope='A',source_center_id='B',target_center_id='A',status='REQUESTED',requested_units=5,created_at=stamp()),dict(id='closed',scope='A',source_center_id='B',target_center_id='A',status='DELIVERED',requested_units=5,created_at=stamp())]
    monkeypatch.setattr(a.intelligence,'forecast',lambda center,*args:dict(method='INTEGRATEDML',expected_units=20))
    monkeypatch.setattr(a.policy,'gap',lambda forecast,own:8)
    chart=next(c for c in a.build('transfers',dict(role='admin'))['charts'] if c['id']=='shortage_projection')
    assert chart['categories']==['open']
    # The source is unreachable: no after-value may be invented.
    assert [s['data'] for s in chart['series']]==[[8],[None]]
