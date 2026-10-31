"""Production domain tests with explicit test doubles, independent of demonstration seed."""
import uuid
from datetime import timedelta
import pytest
from hemoflow import service,repository as repo,workflow,federation
from hemoflow.common import stamp,now,Problem

def test_scope_and_no_donor_consent_bypass():
    user=dict(id='test',role='partner',scope='P-OTHER')
    with pytest.raises(Problem): service.permission(user,'partner','P-CORRECT')
    with pytest.raises(Problem): service.permission(user,'manager','P-OTHER')

def test_expired_invite_rejected_before_workflow(monkeypatch):
    key='TEST-'+str(uuid.uuid4())
    row=dict(id=key,scope='P1',recipient_id='P1',recipient_type='PARTNER',center_id='HEMO-A',
             status='PENDING',expires_at=stamp(now()-timedelta(seconds=1)),correlation_id=key)
    monkeypatch.setattr(repo,'get',lambda *a,**kw:row)
    monkeypatch.setattr(workflow,'complete',lambda *a:pytest.fail('Expired invitation reached native completion'))
    with pytest.raises(Problem) as failure:
        service.invitation_reply(dict(id=key,accept=True),dict(id='partner1',role='partner',scope='P1'))
    assert failure.value.status==409

def test_transfer_requires_handling_and_current_stock(monkeypatch):
    row=dict(id='T1',scope='A',source_center_id='B',target_center_id='A',requested_units=10,
             status='PENDING_SOURCE_APPROVAL',need_by=stamp(now()+timedelta(days=7)),correlation_id='C1')
    monkeypatch.setattr(repo,'get',lambda *a,**kw:row)
    user=dict(id='manager-b',role='manager',scope='B')
    with pytest.raises(Problem): service.transfer_reply(dict(id='T1',accept=True),user)
    monkeypatch.setattr(federation,'inventory',lambda *a:dict(status='AVAILABLE',transferable_units=0,
        handling_lead_hours=4,expiry_buckets=[]))
    monkeypatch.setattr(service.intelligence,'forecast',lambda *a:dict(expected_units=24,method='INTEGRATEDML',quality_flags=[]))
    monkeypatch.setattr(federation,'http',lambda *a,**kw:pytest.fail('Insufficient stock reached reservation'))
    with pytest.raises(Problem): service.transfer_reply(dict(id='T1',accept=True,handling_confirmed=True),user)

def test_campaign_cannot_release_before_processing(monkeypatch):
    row=dict(id='CA1',scope='A',status='CONFIRMED',expected_available_at=stamp(now()+timedelta(days=3)))
    monkeypatch.setattr(repo,'get',lambda *a,**kw:row)
    with pytest.raises(Problem): service.campaign_result(dict(id='CA1',collected=20,released_usable=19),dict(id='manager',role='manager',scope='A'))

def test_foreign_invitation_forbidden_before_any_mutation(monkeypatch):
    row=dict(id='OTHER',scope='P1',recipient_id='P1',recipient_type='PARTNER')
    monkeypatch.setattr(repo,'get',lambda *a,**kw:row)
    monkeypatch.setattr(repo,'put',lambda *a,**kw:pytest.fail('Unauthorized mutation'))
    with pytest.raises(Problem) as failure:
        service.invitation_reply(dict(id='OTHER',accept=True),dict(id='partner2',role='partner',scope='P2'))
    assert failure.value.status==403

def test_no_consent_never_reaches_java_invitation_operation(monkeypatch):
    row=dict(id='CA1',scope='A',status='PENDING_CENTER_APPROVAL',partner_id='P1',
        expected_available_at=stamp(now()+timedelta(days=4)),need_by=stamp(now()+timedelta(days=7)),
        campaign_window_start=stamp(now()+timedelta(days=2)))
    monkeypatch.setattr(repo,'get',lambda kind,*a,**kw:row if kind=='Campaign' else dict(id='P1',scope='A'))
    monkeypatch.setattr(repo,'all',lambda *a,**kw:[dict(id='NO-CONSENT',opt_in=False)])
    monkeypatch.setattr(federation,'call',lambda *a,**kw:pytest.fail('Unconsented donor reached Java PEX'))
    with pytest.raises(Problem,match='No consented contacts'):
        service.campaign_approve(dict(id='CA1',accept=True,mode='CENTER_DIRECT'),dict(id='manager',role='manager',scope='A'))

def test_provider_failure_escalates_without_false_no_action(monkeypatch):
    from test_policy import context
    c=context();c.update(id='provider-failure',scope='HEMO-A',correlation_id='provider-failure',command_key='key',command={'op':'decide'})
    store={('Command','key'):dict(id='key')}
    def put(kind,row,**kw):
        store[(kind,row['id'])]=dict(row)
        return row
    monkeypatch.setattr(repo,'put',put)
    monkeypatch.setattr(repo,'get',lambda kind,key,*a:store.get((kind,key)))
    with pytest.raises(Problem):service.validate_decision(c,dict(error='provider unavailable'))
    result=service.fail_decision(c,'AI Hub unavailable')
    assert not result['ok']
    assert store[('DecisionAudit',c['id'])]['status']=='ESCALATED'
    assert not any(kind in ('Transfer','Campaign') for kind,key in store)

def test_changed_evidence_revision_rejected_before_routing():
    import time
    c=dict(deadline_epoch=time.time()+30,evidence_version=6,catalog=dict(evidence_version=5))
    with pytest.raises(Problem,match='Evidence revision changed'):
        service.validate_decision(c,dict(decision={},evidence_version=5))

def test_duplicate_evaluation_returns_saved_result_without_llm(monkeypatch):
    user=dict(id='manager',role='manager',scope='HEMO-A')
    command=dict(op='decide',actor_id='manager',idempotency_key='same',correlation_id='retry')
    key,fingerprint=service.command_identity(command,user)
    saved=dict(ok=True,result=dict(status='DECIDED'))
    monkeypatch.setattr(service,'actor',lambda _:user)
    monkeypatch.setattr(repo,'get',lambda *a:dict(fingerprint=fingerprint,result=saved))
    assert service.begin_decision(command)==saved

def test_duplicate_evaluation_in_progress_does_not_start_another_agent(monkeypatch):
    import time
    user=dict(id='manager',role='manager',scope='HEMO-A')
    command=dict(op='decide',actor_id='manager',idempotency_key='same',correlation_id='retry')
    key,fingerprint=service.command_identity(command,user)
    monkeypatch.setattr(service,'actor',lambda _:user)
    monkeypatch.setattr(repo,'get',lambda *a:dict(fingerprint=fingerprint,result=None,deadline_epoch=time.time()+30))
    with pytest.raises(Problem,match='already in progress'):service.begin_decision(command)
