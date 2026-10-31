"""Acceptance of the final seed on real simulator containers and Production."""
import sys,time,uuid,json,pathlib
sys.path.insert(0,'/opt/hemoflow/python')
import iris
from hemoflow import repository as repo,federation,demo,ttl
from hemoflow.common import now,stamp,date,enable_iris_demo_clock
enable_iris_demo_clock()
results=[]
def command(op,actor='admin',expect=200,**payload):
    result=federation.call('TransferBPL' if op in ('transfer_reply','dispatch','delivery') else
        'CampaignBPL' if op in ('campaign_approve','invitation_reply','demo_process') else 'DecisionBPL',
        dict(op=op,actor_id=actor,correlation_id=str(uuid.uuid4()),idempotency_key=str(uuid.uuid4()),**payload))
    if expect==200:assert result.get('ok'),(op,result)
    else:assert not result.get('ok') and result.get('status')==expect,(op,result)
    return result.get('result',result)
def ready(identity):
    for _ in range(40):
        if list(iris.sql.exec('SELECT ID FROM EnsLib_Workflow.TaskResponse WHERE %Subject=?',identity)):return
        time.sleep(.1)
    raise AssertionError('Workflow task missing '+identity)
def scenario(name):return command('demo_scenario',scenario=name)
def record(name,**data):
    results.append(dict(case=name,status='PASSED',**data));print('DEMO_PASS',name)
try:
    manifest=repo.get('DemoRun',demo.RUN);assert manifest['status']=='READY'
    assert len(repo.all('NetworkCenter'))==3 and len(repo.all('Partner'))>=6
    assert list(iris.sql.exec('SELECT COUNT(*) FROM HemoFlow.ConsumptionDaily'))[0][0]>=540
    assert list(iris.sql.exec('SELECT COUNT(*) FROM HemoFlow.CampaignExperience'))[0][0]>=40
    assert demo.install(repo.get('User','admin'))['status']=='ALREADY_LOADED'
    record('SEED_COUNTS_AND_IDEMPOTENCY')
    # The real source offers near-expiry units plus longer-lived ones.
    result=scenario('TRANSFER');decision=repo.get('DecisionAudit',result['decision_id'])
    assert decision['decision']['decision']=='REQUEST_TRANSFER'
    transfer=next(r for r in repo.all('Transfer',scope='HEMO-A') if r['correlation_id']==decision['id'])
    ready(transfer['id'])
    command('transfer_reply','gestor-b',id=transfer['id'],accept=True,handling_confirmed=True)
    command('dispatch','gestor-b',id=transfer['id'])
    delivered=command('delivery','gestor-a',id=transfer['id'],receipt_confirmed=True)
    assert delivered['status']=='DELIVERED' and delivered['received_units']>0 and delivered['used_units']==0
    record('REQUEST_TRANSFER_FULL_WORKFLOW',correlation_id=decision['id'],received=delivered['received_units'])
    result=scenario('CAMPAIGN');decision=repo.get('DecisionAudit',result['decision_id'])
    assert decision['decision']['decision']=='REQUEST_CAMPAIGN'
    campaign=next(r for r in repo.all('Campaign',scope='HEMO-A') if r['correlation_id']==decision['id'])
    ready(campaign['id']);command('campaign_approve','gestor-a',id=campaign['id'],accept=True)
    invitation=next(r for r in repo.all('InvitationLedger') if r['campaign_id']==campaign['id'])
    ready(invitation['id']);partner_user='parceiro-'+invitation['recipient_id'].split('-')[-1]
    command('invitation_reply',partner_user,id=invitation['id'],accept=True)
    completed=command('demo_process','gestor-a',id=campaign['id'])
    assert completed['status']=='COMPLETED' and completed['released_usable']>0
    record('REQUEST_CAMPAIGN_FULL_WORKFLOW',correlation_id=decision['id'],released=completed['released_usable'])
    result=scenario('NO_ACTION');assert repo.get('DecisionAudit',result['decision_id'])['decision']['decision']=='NO_ACTION'
    record('NO_ACTION')
    for name in ('OFFLINE','STOCKOUT'):
        assert scenario(name)['expected_block'];record(name)
    result=scenario('EXPIRY');assert repo.get('DecisionAudit',result['decision_id'])['decision']['decision']!='REQUEST_TRANSFER'
    record('EXPIRY_BLOCKS_TRANSFER')
    result=scenario('DECLINED')
    assert any(r['status']=='DECLINED' and not r.get('synthetic_fixture') for r in repo.all('Transfer',scope='HEMO-A'))
    record('DECLINED')
    assert scenario('EXPIRED_INVITE')['http_status']==409;record('EXPIRED_INVITE')
    # Create a fresh invitation and let the automatic Production timer expire it.
    result=scenario('CAMPAIGN');campaign=next(r for r in repo.all('Campaign',scope='HEMO-A') if r['correlation_id']==result['decision_id'])
    ready(campaign['id']);command('campaign_approve','gestor-a',id=campaign['id'],accept=True)
    invitation=next(r for r in repo.all('InvitationLedger') if r['campaign_id']==campaign['id']);ready(invitation['id'])
    assert (date(invitation['expires_at'])-date(invitation['published_at'])).total_seconds()==24*3600
    repo.put('DecisionContext',dict(id='DEMO-AUTO-TTL',correlation_id=invitation['correlation_id'],expires_at=invitation['expires_at'],demo_run_id=demo.RUN))
    command('demo_advance',hours=25)
    assert not any(r['id']==invitation['id'] for r in ttl.pending())
    for _ in range(45):
        if repo.get('InvitationLedger',invitation['id'])['status']=='EXPIRED' and not repo.get('DecisionContext','DEMO-AUTO-TTL',False):break
        time.sleep(1)
    assert repo.get('InvitationLedger',invitation['id'])['status']=='EXPIRED','Automatic expiration did not run'
    assert repo.get('DecisionContext','DEMO-AUTO-TTL',False) is None
    command('invitation_reply','parceiro-'+invitation['recipient_id'].split('-')[-1],expect=409,id=invitation['id'],accept=True)
    assert repo.get('DecisionAudit',result['decision_id'])['status']=='DECIDED'
    record('AUTOMATIC_TTL_24H_TWO_CLASSES_AND_LATE_409')
    for _ in range(45):
        outbox=repo.get('Outbox','expired:'+invitation['id'],False)
        if outbox and outbox['status']=='DONE':break
        time.sleep(1)
    assert outbox and outbox['status']=='DONE'
    record('SINGLE_EXPIRATION_REASSESSMENT')
    command('demo_restore')
    record('SAFE_RESTORE_PRESERVES_AUDIT_AND_LEDGER')
except Exception as exc:
    import traceback
    results.append(dict(case='FAILURE',status='FAILED',detail=str(exc),trace=traceback.format_exc()))
    print('DEMO_E2E_FAILED',str(exc),traceback.format_exc())
evidence=pathlib.Path('/durable/hemoflow-evidence');evidence.mkdir(exist_ok=True)
(evidence/'demo-acceptance.json').write_text(json.dumps(results,indent=2))
print('DEMO_E2E_RESULT',json.dumps(results))
