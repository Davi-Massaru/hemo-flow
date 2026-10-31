"""Validate a non-O workflow, then leave two real proposals ready to demonstrate.

Demo only. Scenario reset backs up owned stock and closes open synthetic plans.
Does not send email or modify a real blood center.
"""
import sys,json,time,uuid,pathlib
sys.path.insert(0,'/opt/hemoflow/python')
import iris
from datetime import timedelta
from hemoflow import repository as repo,federation,demo
from hemoflow.common import enable_iris_demo_clock,now,stamp
enable_iris_demo_clock();demo.guard(repo.get('User','admin'))
def command(op,actor='admin',**payload):
    destination='TransferBPL' if op in ('transfer_reply','dispatch','delivery') else 'DecisionBPL'
    result=federation.call(destination,dict(op=op,actor_id=actor,correlation_id=str(uuid.uuid4()),idempotency_key=str(uuid.uuid4()),**payload))
    assert result.get('ok'),result
    return result['result']
def proposal():
    decision=command('decide','gestor-a',center_id='HEMO-A',blood_type='A+',need_by=stamp(now()+timedelta(days=7)))
    assert decision['decision']['decision']=='REQUEST_TRANSFER',decision
    row=next(r for r in repo.all('Transfer') if r['correlation_id']==decision['id'])
    assert row['blood_type']=='A+'
    for _ in range(40):
        if list(iris.sql.exec('SELECT ID FROM EnsLib_Workflow.TaskResponse WHERE %Subject=?',row['id'])):return row
        time.sleep(.1)
    raise AssertionError('Workflow task not ready')
need=stamp(now()+timedelta(days=7))
before=federation.inventory('HEMO-A','HEMO-A',need,str(uuid.uuid4()),'O-')['available_units']
row=proposal();source='gestor-'+row['source_center_id'][-1].lower()
command('transfer_reply',source,id=row['id'],accept=True,handling_confirmed=True)
command('dispatch',source,id=row['id'])
delivered=command('delivery','gestor-a',id=row['id'],receipt_confirmed=True)
assert delivered['status']=='DELIVERED' and delivered['blood_type']=='A+'
after=federation.inventory('HEMO-A','HEMO-A',need,str(uuid.uuid4()),'O-')['available_units']
assert before==after
assert list(iris.sql.exec("SELECT TOP 1 ExternalId FROM HemoFlow.CampaignExperience WHERE NOT (ExternalId %STARTSWITH 'DEMO-')"))
campaign=command('demo_scenario',scenario='CAMPAIGN')
transfer=proposal()
result=dict(non_o_transfer='PASSED',delivered_id=delivered['id'],received=delivered['received_units'],o_negative_unchanged=before,
    completed_campaign_indexed=True,pending_campaign_decision=campaign['decision_id'],pending_a_positive_transfer=transfer['id'])
pathlib.Path('/durable/hemoflow-evidence/presentation-acceptance.json').write_text(json.dumps(result,indent=2))
print('PRESENTATION_READY',json.dumps(result))
