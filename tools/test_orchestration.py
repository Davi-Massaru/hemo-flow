"""Read-only causal trace acceptance, following test_demo_e2e.py."""
import json,pathlib
import iris
from hemoflow import repository as repo
from hemoflow.intelligence import TOOL_NAMES

folder=pathlib.Path('/durable/hemoflow-evidence')
cases=json.loads((folder/'demo-acceptance.json').read_text())
assert all(c['status']=='PASSED' for c in cases),cases
proof=[]
for case in cases:
    if not case.get('correlation_id') or not case['case'].startswith('REQUEST_'):continue
    identity=case['correlation_id'];audit=repo.get('DecisionAudit',identity)
    action=audit['decision']['decision'];target='TransferBPL' if action=='REQUEST_TRANSFER' else 'CampaignBPL'
    assert audit['routed_to']==target
    assert set(audit['observations'])==set(TOOL_NAMES)
    assert len(set(audit['evidence_ids']))==5 and audit['evidence_version']>=5
    rows=[list(r) for r in iris.sql.exec('''SELECT ID,SessionId,SourceConfigName,TargetConfigName
        FROM Ens.MessageHeader WHERE SessionId IN
        (SELECT SessionId FROM Ens.MessageHeader WHERE MessageBodyClassName='HemoFlow.Message'
         AND MessageBodyId IN (SELECT ID FROM HemoFlow.Message WHERE CorrelationId=?)) ORDER BY ID''',identity)]
    sessions={r[1] for r in rows if r[2]=='DecisionBPL' and r[3]=='AIHubDecisionOperation'}
    assert sessions
    root=next(iter(sessions));trace=[r for r in rows if r[1]==root]
    assert any(r[2]=='AIHubDecisionOperation' and r[3]=='AIReadOperation' for r in trace)
    assert any(r[2]=='AIReadOperation' and r[3]=='FederatedInventoryOperation' for r in trace)
    assert any(r[2]=='DecisionBPL' and r[3]==target for r in trace)
    opposite='CampaignBPL' if target=='TransferBPL' else 'TransferBPL'
    assert not any(r[2]=='DecisionBPL' and r[3]==opposite for r in trace)
    proof.append(dict(decision_id=identity,action=action,session_id=root,trace=trace))
assert len(proof)==2,proof
for audit in repo.all('DecisionAudit',limit=200):
    if audit.get('decision',{}).get('decision')!='NO_ACTION' and audit.get('status')!='ESCALATED':continue
    identity=audit['id']
    assert not any(r['correlation_id']==identity for kind in ('Transfer','Campaign') for r in repo.all(kind))
    assert not audit.get('routed_to')
(folder/'orchestration-trace.json').write_text(json.dumps(proof,indent=2))
print('ORCHESTRATION_TRACE_PASSED',json.dumps([dict(action=p['action'],session_id=p['session_id'],messages=len(p['trace'])) for p in proof]))

