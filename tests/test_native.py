"""Executed inside Embedded Python; isolated test records are removed afterwards."""
import uuid,time,json
from datetime import timedelta
import pytest
import iris
from hemoflow import repository as repo, federation, workflow, ttl
from hemoflow.common import stamp,now,checked

def test_vector_native():
    assert list(iris.sql.exec("SELECT VECTOR_COSINE(TO_VECTOR('1,0',DOUBLE),TO_VECTOR('1,0',DOUBLE))"))[0][0]==1

def test_tool_evidence_correlation_is_filtered_before_limit():
    own='TEST-'+str(uuid.uuid4());other='TEST-'+str(uuid.uuid4())
    try:
        repo.put('EventAudit',dict(id=own,correlation_id=own,created_at=stamp(now()-timedelta(days=1))))
        repo.put('EventAudit',dict(id=other,correlation_id=other,created_at=stamp(now()+timedelta(days=30))))
        assert repo.all('EventAudit',correlation=own,limit=1)[0]['id']==own
    finally:
        for identity in (own,other):repo.delete('EventAudit',identity)

def test_censored_history_marks_forecast_quality():
    from hemoflow.intelligence import forecast
    center='TEST-'+str(uuid.uuid4())
    try:
        for i in range(28):
            day=(now()-timedelta(days=i+1)).date().isoformat()
            iris.sql.exec("INSERT INTO HemoFlow.ConsumptionDaily (ExternalId,CenterId,Day,UsedUnits,DemandUnmet) VALUES(?,?,TO_DATE(?,'YYYY-MM-DD'),?,?)",center+':'+day,center,day,3,int(i==0))
        result=forecast(center)
        assert result['method']=='INTEGRATEDML' and 'stockout_affected' in result['quality_flags']
    finally:iris.sql.exec('DELETE FROM HemoFlow.ConsumptionDaily WHERE CenterId=?',center)

def test_pex_inventory_live():
    from hemoflow.fhir import availability_input,parse_availability
    raw=federation.call('FederatedInventoryOperation',dict(endpoint='http://center-b:8080/fhir/$inventory-availability',body=availability_input('HEMO-A',stamp(now()+timedelta(days=7)))))
    result=parse_availability(raw,'HEMO-B')
    assert result['status']=='AVAILABLE'

def test_custom_adapter_timeout_remains_unavailable():
    import socket,subprocess,sys
    server_socket=socket.socket();server_socket.bind(('127.0.0.1',0));port=server_socket.getsockname()[1];server_socket.close()
    source="""import time,sys
from http.server import HTTPServer,BaseHTTPRequestHandler
class Slow(BaseHTTPRequestHandler):
 def do_POST(self):
  time.sleep(8);self.send_response(200);self.end_headers();self.wfile.write(b'{}')
 def log_message(self,*args):pass
HTTPServer(('127.0.0.1',int(sys.argv[1])),Slow).serve_forever()
"""
    child=subprocess.Popen(['/usr/bin/python3','-c',source,str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    identity='TEST-TIMEOUT-'+str(uuid.uuid4())
    try:
        for _ in range(30):
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1):break
            except OSError:time.sleep(.1)
        repo.put('NetworkCenter',dict(id=identity,endpoint='http://127.0.0.1:'+str(port)))
        result=federation.inventory(identity,'HEMO-A',stamp(now()+timedelta(days=7)),identity)
        assert result['status']=='UNAVAILABLE' and 'available_units' not in result
    finally:
        child.terminate();child.wait(timeout=5)
        if repo.get('NetworkCenter',identity,False):repo.delete('NetworkCenter',identity)

def test_pex_creates_only_approved_consented_plan():
    raw=federation.call('CampaignCreationOperation',dict(campaign_id='TEST-CAMPAIGN',approved=True,
                         recipients=[dict(id='TEST-PARTNER',type='PARTNER')]))
    assert raw['creator']=='JAVA_PEX' and len(raw['invitations'])==1

def test_workflow_native_task():
    key='TEST-'+str(uuid.uuid4()); user='TEST-WORKFLOW-'+uuid.uuid4().hex[:8]
    u=iris.cls('EnsLib.Workflow.UserDefinition'); role=iris.cls('EnsLib.Workflow.RoleDefinition')
    if not u._ExistsId(user): checked(u.CreateUser(user,'Synthetic test approver'))
    if not role._ExistsId('Approvals'): checked(role.CreateRole('Approvals'))
    checked(role.AddUserToRole('Approvals',user))
    entity=dict(id=key,correlation_id=key)
    workflow.start(entity,user,'Native task integration test')
    try:
        for _ in range(40):
            rows=list(iris.sql.exec('SELECT ID FROM EnsLib_Workflow.TaskResponse WHERE %Subject=?',key))
            if rows: break
            time.sleep(.1)
        assert rows,'Native workflow task not created'
        workflow.complete(entity,user,'ACCEPT')
        assert repo.get('WorkflowLink',key)['status']=='ACCEPT'
    finally: repo.delete('WorkflowLink',key)

def test_ttl_two_classes_preserves_ledger():
    key='TEST-'+str(uuid.uuid4()); expired=stamp(now()-timedelta(seconds=1))
    row=dict(id=key,status='PENDING',scope='TEST-PARTNER',center_id='TEST-A',correlation_id=key,expires_at=expired)
    repo.put('InvitationLedger',dict(row));repo.put('PendingInvitation',dict(row));repo.put('DecisionContext',dict(row))
    try:
        assert not any(i['id']==key for i in ttl.pending())
        ttl.expire()
        assert repo.get('PendingInvitation',key,False) is None
        assert repo.get('DecisionContext',key,False) is None
        assert repo.get('InvitationLedger',key)['status']=='EXPIRED'
        ttl.expire()
        events=[r for r in repo.all('EventAudit') if r.get('invitation_id')==key]
        assert len(events)==1
    finally:
        for kind in ('PendingInvitation','DecisionContext','InvitationLedger'):
            if repo.get(kind,key,False):repo.delete(kind,key)
        if repo.get('Outbox','expired:'+key,False):repo.delete('Outbox','expired:'+key)

def test_web_five_screens_and_authentication():
    from hemoflow.web import app
    from hemoflow.settings import setting
    client=app.test_client()
    assert client.get('/api/inventory/HEMO-A').status_code==401
    client.get('/login')
    with client.session_transaction() as s: token=s['csrf']
    response=client.post('/login',data=dict(username='admin',password=setting('HEMOFLOW_ADMIN_PASSWORD'),csrf=token))
    assert response.status_code==302
    for path in ('/dashboard','/blood-center-network','/blood-transfers','/donation-campaigns','/audit-analytics'):
        response=client.get(path)
        assert response.status_code==200,(path,response.data[:300])
    assert client.post('/api/decisions',json={}).status_code==403
