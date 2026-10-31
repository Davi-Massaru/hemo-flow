"""Independent-system contract tests with temporary fixtures, never demo seed."""
import importlib.util
from datetime import timedelta
import pytest
from hemoflow.common import ROOT,stamp,now
from hemoflow.fhir import availability_input,parse_availability,supply_request

@pytest.fixture
def center(tmp_path,monkeypatch):
    from hemoflow import common
    previous_clock=common._clock_offset
    monkeypatch.setenv('CENTER_DB',str(tmp_path/'center.sqlite'))
    spec=importlib.util.spec_from_file_location('test_center',ROOT/'simulators/center.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'DB',str(tmp_path/'center.sqlite'))
    monkeypatch.setattr(module,'TOKEN','test-only-token')
    monkeypatch.setattr(module,'CENTER','HEMO-B')
    client=module.app.test_client()
    client.environ_base['HTTP_AUTHORIZATION']='Bearer test-only-token'
    with module.connection() as db:
        for i in range(20):
            db.execute('INSERT INTO units(id,expires,reserved,blocked) VALUES(?,?,?,?)',
                ('TEST-'+str(i),stamp(now()+timedelta(days=15)),int(i==0),int(i==1)))
        db.execute('INSERT INTO units(id,expires) VALUES(?,?)',('TEST-EXPIRED',stamp(now()-timedelta(seconds=1))))
    yield module,client
    common.set_clock(previous_clock)

def test_live_federation_and_reservation_revalidation(center):
    module,client=center
    need=stamp(now()+timedelta(days=7))
    p=availability_input('HEMO-A',need)
    response=client.post('/fhir/$inventory-availability',json=p)
    inventory=parse_availability(response.json,'HEMO-B')
    assert inventory['available_units']==18
    assert inventory['transferable_units']==14
    with module.connection() as db:
        db.execute("UPDATE units SET blocked=1 WHERE id LIKE 'TEST-1%'")
    current=parse_availability(client.post('/fhir/$inventory-availability',json=p).json,'HEMO-B')
    assert current['available_units']<inventory['available_units']
    transfer=dict(id='TEST-TRANSFER',requested_units=14,source_center_id='HEMO-B',target_center_id='HEMO-A',need_by=need)
    assert client.post('/fhir/SupplyRequest',json=supply_request(transfer)).status_code==409

def test_remote_idempotent_reserve_dispatch_receive(center):
    module,client=center
    transfer=dict(id='TEST-TRANSFER',requested_units=5,source_center_id='HEMO-B',target_center_id='HEMO-A',need_by=stamp(now()+timedelta(days=7)))
    first=client.post('/fhir/SupplyRequest',json=supply_request(transfer));assert first.status_code==200
    assert client.post('/fhir/SupplyRequest',json=supply_request(transfer)).json==first.json
    shipment=client.post('/transfers/TEST-TRANSFER/dispatch',json={})
    assert shipment.status_code==200 and len(shipment.json['units'])==5
    assert client.post('/transfers/TEST-TRANSFER/receive',json=shipment.json).json['received_units']==5
    assert client.post('/transfers/TEST-TRANSFER/receive',json=shipment.json).json['received_units']==5

def test_unavailability_never_reports_empty_stock(center):
    module,client=center
    with module.connection() as db: db.execute("INSERT INTO settings VALUES('offline','1')")
    response=client.post('/fhir/$inventory-availability',json=availability_input('HEMO-A',stamp(now()+timedelta(days=7))))
    assert response.status_code==503 and 'parameter' not in response.json

def test_blood_types_are_isolated_through_reserve_dispatch_and_receipt(center):
    module,client=center
    need=stamp(now()+timedelta(days=7))
    with module.connection() as db:
        for i in range(12):db.execute('INSERT INTO units(id,expires,blood_type) VALUES(?,?,?)',('A-POS-'+str(i),stamp(now()+timedelta(days=15)),'A+'))
    def stock(group):return parse_availability(client.post('/fhir/$inventory-availability',json=availability_input('HEMO-A',need,group)).json,'HEMO-B',group)['available_units']
    assert stock('O-')==18 and stock('A+')==12 and stock('AB-')==0
    transfer=dict(id='TEST-A-POS',blood_type='A+',requested_units=5,source_center_id='HEMO-B',target_center_id='HEMO-A',need_by=need)
    assert client.post('/fhir/SupplyRequest',json=supply_request(transfer)).status_code==200
    assert stock('O-')==18 and stock('A+')==7
    assert client.post('/fhir/SupplyRequest',json=supply_request(dict(transfer,blood_type='O-'))).status_code==409
    shipment=client.post('/transfers/TEST-A-POS/dispatch',json={}).json
    assert {r['blood_type'] for r in shipment['units']}=={'A+'}
    assert client.post('/transfers/TEST-A-POS/receive',json=shipment).status_code==200
    assert stock('A+')==12 and stock('O-')==18

def test_unknown_blood_type_is_rejected(center):
    _,client=center
    body=availability_input('HEMO-A',stamp(now()+timedelta(days=7)))
    next(p for p in body['parameter'] if p['name']=='bloodType')['valueCode']='UNKNOWN'
    assert client.post('/fhir/$inventory-availability',json=body).status_code==422

def test_seed_refuses_foreign_state_and_restores_only_owned(center,monkeypatch):
    from hemoflow.demo import manifests,RUN
    module,client=center;monkeypatch.setattr(module,'DEMO',True)
    manifest=manifests(stamp())['HEMO-B']
    assert client.post('/demo/seed',json=manifest).status_code==409
    with module.connection() as db:db.execute('DELETE FROM units') # disposable test fixture only
    assert client.post('/demo/seed',json=manifest).status_code==200
    assert client.post('/demo/seed',json=manifest).json['status']=='ALREADY_LOADED'
    with module.connection() as db:db.execute("UPDATE units SET blocked=1 WHERE id LIKE 'DEMO-%'")
    assert client.post('/demo/restore',json=dict(run_id=RUN)).status_code==200
    with module.connection() as db:db.execute("INSERT INTO units(id,expires) VALUES('FOREIGN',?)",(stamp(now()+timedelta(days=20)),))
    assert client.post('/demo/restore',json=dict(run_id=RUN)).status_code==409
