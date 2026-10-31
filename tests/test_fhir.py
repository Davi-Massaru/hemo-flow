from hemoflow.fhir import validate,supply_request,supply_delivery,availability_input
from hemoflow.common import stamp,now
from datetime import timedelta

def test_r4_request_delivery_parameters():
    t=dict(id='TEST-TRANSFER',requested_units=4,source_center_id='HEMO-B',target_center_id='HEMO-A',need_by=stamp(now()+timedelta(days=7)))
    req=supply_request(t); delivery=supply_delivery(t,4)
    assert 'itemCodeableConcept' in req and 'itemReference' not in req
    assert delivery['status']=='completed'
    validate(availability_input('HEMO-A',t['need_by']))

def test_custom_operation_definition_r4():
    import json
    from hemoflow.common import ROOT
    resource=json.loads((ROOT/'simulators/inventory-availability.json').read_text())
    validate(resource)
    assert resource['affectsState'] is False and resource['system'] is True
