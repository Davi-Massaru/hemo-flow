"""Read-only, secret-free evidence from the running product and final acceptance."""
import sys,json,pathlib,hashlib
sys.path.insert(0,'/opt/hemoflow/python')
import iris
from hemoflow import repository as repo,intelligence,demo,federation
from hemoflow.common import stamp

folder=pathlib.Path('/durable/hemoflow-evidence');folder.mkdir(exist_ok=True)
report=dict(observed_at=stamp(),seed=repo.get('DemoRun',demo.RUN),model=repo.config('forecast_model'))
acceptance=json.loads((folder/'demo-acceptance.json').read_text())
report['acceptance']=acceptance
assert all(case['status']=='PASSED' for case in acceptance)
report['persisted_decisions']={case['correlation_id']:repo.get('DecisionAudit',case['correlation_id'])['status']
    for case in acceptance if case.get('correlation_id')}
assert all(status=='DECIDED' for status in report['persisted_decisions'].values())
report['counts']={kind:list(iris.sql.exec('SELECT COUNT(*) FROM '+repo.table(kind)))[0][0]
                  for kind in ('NetworkCenter','Partner','User','DecisionAudit','EventAudit','InvitationLedger')}
report['consumption_rows']=list(iris.sql.exec('SELECT COUNT(*) FROM HemoFlow.ConsumptionDaily'))[0][0]
report['campaign_experiences']=list(iris.sql.exec('SELECT COUNT(*) FROM HemoFlow.CampaignExperience'))[0][0]
report['remote_status']={c['id']:federation.http(c['id'],'/demo/status',dict(run_id=demo.RUN)) for c in repo.all('NetworkCenter')}
query='blood donation campaign red blood cells O negative shortage'
first=intelligence.search(query,'SP');second=intelligence.search(query,'SP')
assert [r['campaign_id'] for r in first['results']]==[r['campaign_id'] for r in second['results']]
report['vector_top_k']=first
report['sessions']=[dict(decision_id=key,**repo.get('DecisionAudit',key)['ai']) for key in report['persisted_decisions']]
report['native_message_columns']=[r[0] for r in iris.sql.exec("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='Ens' AND TABLE_NAME='MessageHeader'")]
report['message_trace']=[list(r) for r in iris.sql.exec("SELECT TOP 40 ID,SessionId,SourceConfigName,TargetConfigName,MessageBodyClassName FROM Ens.MessageHeader WHERE TargetConfigName IN ('AIHubDecisionOperation','TransferBPL','CampaignBPL','CampaignCreationOperation','FHIRTransferOperation') ORDER BY ID DESC")]
(folder/'runtime-evidence.json').write_text(json.dumps(report,indent=2,default=str))
print('EVIDENCE_OK',json.dumps(dict(counts=report['counts'],history=report['consumption_rows'],vectors=report['campaign_experiences'],persisted=report['persisted_decisions'],top_k=len(first['results']))))
