"""Pre-seed acceptance gate with disposable institutional systems and real LLM.

Fixture state is removed in finally. This is not the demonstration seed.
"""
import sys,os,tempfile,importlib.util,uuid,time,json,subprocess,urllib.request
from datetime import timedelta
sys.path.insert(0,'/opt/hemoflow/python')
import iris
from werkzeug.security import generate_password_hash
from hemoflow import repository as repo,federation,intelligence
from hemoflow.common import ROOT,now,stamp,checked,dumps
from hemoflow.settings import setting

assert not repo.all('NetworkCenter'),'Disposable gate requires empty network registry'
assert not list(iris.sql.exec('SELECT TOP 1 ExternalId FROM HemoFlow.ConsumptionDaily')),'Disposable gate requires empty dataset'
key=uuid.uuid4().hex[:8]
servers=[]; modules=[]; owned=[]
tmp=tempfile.TemporaryDirectory(prefix='hemoflow-gate-')
def save(kind,row):
    repo.put(kind,row,create=True);owned.append((kind,row['id']));return row
def command(op,actor,**payload):
    target='TransferBPL' if op in ('transfer_reply','dispatch','delivery') else 'CampaignBPL' if op in ('campaign_approve','invitation_reply','campaign_result') else 'DecisionBPL'
    result=federation.call(target,dict(op=op,actor_id=actor,correlation_id=str(uuid.uuid4()),idempotency_key=str(uuid.uuid4()),**payload))
    if not result.get('ok'):
        print('GATE_COMMAND_FAILURE',op,result)
        raise AssertionError(result)
    return result['result']
def stock(module,count):
    with module.connection() as db:
        db.execute('DELETE FROM units')
        for i in range(count):db.execute('INSERT INTO units(id,expires) VALUES(?,?)',(f'TEST-{module.CENTER}-{i}',stamp(now()+timedelta(days=15))))
try:
    for index,center_id in enumerate(('HEMO-A','HEMO-B','HEMO-C')):
        os.environ['CENTER_DB']=tmp.name+'/'+center_id+'.sqlite'
        spec=importlib.util.spec_from_file_location('fixture_'+center_id,ROOT/'simulators/center.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        mod.CENTER=center_id;mod.TOKEN=setting('HEMOFLOW_CENTER_TOKEN')
        with mod.connection(): pass
        environment=dict(os.environ,CENTER_DB=mod.DB,CENTER_ID=center_id,
                         CENTER_TOKEN=mod.TOKEN,PORT=str(18081+index),PYTHONPATH=str(ROOT/'python'))
        server=subprocess.Popen(['/usr/bin/python3',str(ROOT/'simulators/center.py')],env=environment,
                                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        servers.append(server);modules.append(mod)
        for attempt in range(50):
            try:
                urllib.request.urlopen(f'http://localhost:{18081+index}/health',timeout=1).close();break
            except OSError: time.sleep(.1)
        save('NetworkCenter',dict(id=center_id,name='Disposable gate '+center_id,scope=center_id,region='SP',endpoint=f'http://localhost:{18081+index}'))
    users=[('TEST-MA-'+key,'manager','HEMO-A'),('TEST-MB-'+key,'manager','HEMO-B'),('TEST-MC-'+key,'manager','HEMO-C'),('TEST-PARTNER-'+key,'partner','TEST-P1-'+key)]
    for identity,role,scope in users:
        save('User',dict(id=identity,name=identity,role=role,scope=scope,password_hash=generate_password_hash('test-only')))
        checked(iris.cls('EnsLib.Workflow.UserDefinition').CreateUser(identity,identity))
        checked(iris.cls('EnsLib.Workflow.RoleDefinition').AddUserToRole('Approvals',identity))
    partner_id='TEST-P1-'+key
    save('Partner',dict(id=partner_id,name='Disposable university',scope='HEMO-A',region='SP',type='UNIVERSITY',capacity=30,organize_hours=48,collection_hours=8,processing_hours=48))
    for i in range(180):
        iris.sql.exec("INSERT INTO HemoFlow.ConsumptionDaily (ExternalId,CenterId,Day,UsedUnits,DemandUnmet) VALUES(?,?,TO_DATE(?,'YYYY-MM-DD'),?,?)",
                      'TEST-E2E-'+str(i),'HEMO-A',(now()-timedelta(days=180-i)).date().isoformat(),2+(i%11)//4+(i//21)%2,0)
    print('E2E_MODEL',intelligence.train())
    vec=intelligence.embedding('University blood donation campaign red cells shortage')
    iris.sql.exec('''INSERT INTO HemoFlow.CampaignExperience
        (ExternalId,PartnerId,PartnerType,Region,Summary,ReleasedUsable,Metrics,Embedding,EmbeddingModel,ContentHash)
        VALUES(?,?,?,?,?,?,?,TO_VECTOR(?,DOUBLE),?,?)''','TEST-E2E-VECTOR',partner_id,'UNIVERSITY','SP','University blood donation campaign',20,'{}',vec,'BAAI/bge-small-en-v1.5','test')
    results=[]
    # Real REQUEST_TRANSFER -> human source approval -> dispatch -> destination receipt.
    stock(modules[0],8);stock(modules[1],20);stock(modules[2],4)
    decision=command('decide',users[0][0],center_id='HEMO-A',need_by=stamp(now()+timedelta(days=7)))
    print('E2E_DECISION',decision)
    assert decision['decision']['decision']=='REQUEST_TRANSFER'
    transfer=next(t for t in repo.all('Transfer') if t['correlation_id']==decision['correlation_id'])
    owned.append(('Transfer',transfer['id']))
    time.sleep(.5)
    command('transfer_reply',users[1][0],id=transfer['id'],accept=True,handling_confirmed=True)
    command('dispatch',users[1][0],id=transfer['id'])
    delivered=command('delivery',users[0][0],id=transfer['id'],receipt_confirmed=True)
    assert delivered['status']=='DELIVERED' and delivered['received_units']>0
    results.append({'case':'TRANSFER','status':'PASSED','decision_id':decision['id']})
    # Real REQUEST_CAMPAIGN -> native manager approval -> Java PEX -> partner acceptance.
    stock(modules[0],8);stock(modules[1],4);stock(modules[2],4)
    decision=command('decide',users[0][0],center_id='HEMO-A',need_by=stamp(now()+timedelta(days=7)))
    print('E2E_DECISION',decision)
    assert decision['decision']['decision']=='REQUEST_CAMPAIGN'
    campaign=next(c for c in repo.all('Campaign') if c['correlation_id']==decision['correlation_id'])
    owned.append(('Campaign',campaign['id']));time.sleep(.5)
    command('campaign_approve',users[0][0],id=campaign['id'],accept=True)
    invitation=next(i for i in repo.all('InvitationLedger') if i['campaign_id']==campaign['id'])
    owned.extend([('InvitationLedger',invitation['id']),('PendingInvitation',invitation['id'])]);time.sleep(.5)
    command('invitation_reply',users[3][0],id=invitation['id'],accept=True)
    assert repo.get('Campaign',campaign['id'])['status']=='CONFIRMED'
    results.append({'case':'CAMPAIGN','status':'PASSED','decision_id':decision['id']})
    # Plans are no longer active for the third independent fixture scenario.
    campaign=repo.get('Campaign',campaign['id']);campaign['status']='COMPLETED';repo.put('Campaign',campaign)
    stock(modules[0],45)
    decision=command('decide',users[0][0],center_id='HEMO-A',need_by=stamp(now()+timedelta(days=7)))
    print('E2E_DECISION',decision)
    assert decision['decision']['decision']=='NO_ACTION'
    results.append({'case':'NO_ACTION','status':'PASSED','decision_id':decision['id']})
    evidence=__import__('pathlib').Path('/durable/hemoflow-evidence');evidence.mkdir(exist_ok=True)
    (evidence/'e2e-gate.json').write_text(json.dumps(results,indent=2))
    print('E2E_GATE_PASSED',results)
except Exception as exc:
    import traceback
    print('E2E_GATE_FAILED',type(exc).__name__,str(exc),traceback.format_exc())
finally:
    for server in servers:
        server.terminate();server.wait(timeout=5)
    for kind,identity in reversed(owned):
        if repo.get(kind,identity,False):repo.delete(kind,identity)
    for cls in ('ConsumptionDaily','DemandFeature'):
        if list(iris.sql.exec('SELECT COUNT(*) FROM HemoFlow.'+cls+" WHERE CenterId='HEMO-A'"))[0][0]:
            iris.sql.exec('DELETE FROM HemoFlow.'+cls+" WHERE CenterId='HEMO-A'")
    if list(iris.sql.exec("SELECT COUNT(*) FROM HemoFlow.CampaignExperience WHERE ExternalId='TEST-E2E-VECTOR'"))[0][0]:
        iris.sql.exec("DELETE FROM HemoFlow.CampaignExperience WHERE ExternalId='TEST-E2E-VECTOR'")
    tmp.cleanup()
