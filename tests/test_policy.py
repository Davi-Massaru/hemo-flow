import copy, json
from datetime import timedelta
import pytest
from hemoflow.common import stamp,now,Problem
from hemoflow import policy

def context():
    expiry=stamp(now()+timedelta(days=15))
    return dict(id='test-request',center_id='HEMO-A',created_at=stamp(),need_by=stamp(now()+timedelta(days=7)),
        forecast=dict(expected_units=24,method='INTEGRATEDML',quality_flags=[]),
        network=[dict(center_id='HEMO-A',status='AVAILABLE',transferable_units=4,available_units=8,
            handling_lead_hours=4,observed_at=stamp(),expiry_buckets=[dict(units=8,expiresAt=expiry)]),
            dict(center_id='HEMO-B',status='AVAILABLE',transferable_units=12,available_units=16,
            handling_lead_hours=4,observed_at=stamp(),expiry_buckets=[dict(units=12,expiresAt=expiry)])],
        partners=[dict(id='P1',capacity=30,organize_hours=48,collection_hours=8,processing_hours=48)],
        evidence_ids=['e1','e2'],active_campaigns=[])

def test_transfer_guard():
    c=context(); candidates=policy.candidates(c)
    assert candidates[0]['decision']=='REQUEST_TRANSFER'
    decision=dict(candidates[0],reason='Synthetic supply deficit')
    assert policy.guard(decision,c,candidates)==decision
    decision['requested_units']=13
    with pytest.raises(Problem): policy.guard(decision,c,candidates)

def test_partial_transfer_keeps_campaign_alternative_without_discounting_hypothesis():
    c=context(); allowed=policy.candidates(c)
    assert {row['decision'] for row in allowed}=={'REQUEST_TRANSFER','REQUEST_CAMPAIGN'}
    transfer=next(row for row in allowed if row['decision']=='REQUEST_TRANSFER')
    campaign=next(row for row in allowed if row['decision']=='REQUEST_CAMPAIGN')
    assert transfer['requested_units']==12
    assert campaign['target_units']==16  # The twelve units have not been approved/received.
    assert policy.guard(dict(campaign,reason='Future deficit exceeds available network supply'),c,allowed)


def test_sufficient_network_excludes_unnecessary_campaign():
    c=context();c['network'][1]['transferable_units']=16
    c['network'][1]['expiry_buckets'][0]['units']=16
    assert {row['decision'] for row in policy.candidates(c)}=={'REQUEST_TRANSFER'}


def test_combined_origins_cover_deficit_without_campaign():
    c=context();third=copy.deepcopy(c['network'][1]);third['center_id']='HEMO-C'
    third['transferable_units']=4;third['expiry_buckets'][0]['units']=4
    c['network'].append(third)
    allowed=policy.candidates(c)
    assert len(allowed)==2
    assert {row['decision'] for row in allowed}=={'REQUEST_TRANSFER'}


def test_network_reconciles_competing_short_expiry_capacity(monkeypatch):
    at=now();monkeypatch.setattr(policy,'now',lambda:at)
    c=context();c['network'][1]['expiry_buckets'][0]['expiresAt']=stamp(at+timedelta(days=4))
    third=copy.deepcopy(c['network'][1]);third['center_id']='HEMO-C';c['network'].append(third)
    allowed=policy.candidates(c)
    transfers=[row for row in allowed if row['decision']=='REQUEST_TRANSFER']
    assert sum(row['requested_units'] for row in transfers)>=16
    # Both origins compete for the same consumption window; adding their limits is unsafe.
    assert policy.network_gap(c,transfers,at)>0
    assert any(row['decision']=='REQUEST_CAMPAIGN' for row in allowed)


def test_partial_transfer_does_not_make_late_campaign_valid():
    c=context();c['need_by']=stamp(now()+timedelta(hours=12))
    assert {row['decision'] for row in policy.candidates(c)}=={'REQUEST_TRANSFER'}


def test_confirmed_campaign_does_not_remove_valid_transfer():
    c=context();c['active_campaigns']=[dict(id='already-confirmed')]
    assert {row['decision'] for row in policy.candidates(c)}=={'REQUEST_TRANSFER'}


def test_campaign_future_not_urgent():
    c=context(); c['network'][1]['transferable_units']=0;c['network'][1]['expiry_buckets']=[]
    assert policy.candidates(c)[0]['decision']=='REQUEST_CAMPAIGN'
    c['need_by']=stamp(now()+timedelta(hours=12))
    assert policy.candidates(c)==[]

def test_confirmed_campaign_blocks_duplicate_invitation():
    c=context();c['network'][1]['transferable_units']=0;c['network'][1]['expiry_buckets']=[]
    c['active_campaigns']=[dict(id='already-confirmed')]
    assert policy.candidates(c)==[]

def test_offline_is_not_zero_or_no_action():
    c=context(); c['network'][1]={'center_id':'HEMO-B','status':'UNAVAILABLE'}
    assert policy.candidates(c)==[]

def test_expired_units_do_not_cover_future():
    c=context(); c['network'][0]['expiry_buckets'][0]['expiresAt']=stamp(now()-timedelta(seconds=1))
    assert policy.gap(c['forecast'],c['network'][0])==24

def test_no_action_requires_coverage_and_forecast_quality():
    c=context(); c['network'][0]['expiry_buckets'][0]['units']=30
    assert policy.candidates(c)[0]['decision']=='NO_ACTION'
    c['forecast']['quality_flags']=['stockout_affected']
    assert policy.candidates(c)==[]

def test_unknown_evidence_or_identity_rejected():
    c=context(); allowed=policy.candidates(c); decision=dict(allowed[0],reason='Synthetic supply deficit')
    decision['evidence_ids']=['invented']
    with pytest.raises(Problem): policy.guard(decision,c,allowed)

def test_versioned_decision_requires_all_current_evidence():
    c=context();c['evidence_version']=2;c['evidence_ids']=['forecast:v2','inventory:v2']
    allowed=policy.candidates(c);decision=dict(allowed[0],reason='Verified current evidence')
    assert policy.guard(decision,c,allowed)==decision
    decision['evidence_ids']=['forecast:v2']
    with pytest.raises(Problem,match='all current evidence'):policy.guard(decision,c,allowed)
    decision['evidence_ids']=['forecast:v2','inventory:v1']
    with pytest.raises(Problem,match='Unknown evidence'):policy.guard(decision,c,allowed)


def test_versioned_transfer_rejects_previous_inventory_timestamp():
    c=context();c['evidence_version']=2
    older=stamp(now()-timedelta(seconds=10))
    c['inventory_observations']={'HEMO-B':[older,c['network'][1]['observed_at']]}
    allowed=policy.candidates(c);decision=dict(allowed[0],reason='Current candidate, stale timestamp',inventory_observed_at=older)
    with pytest.raises(Problem,match='not an authorized candidate'):policy.guard(decision,c,allowed)


def test_legacy_decision_can_cite_subset_of_known_evidence():
    c=context();allowed=policy.candidates(c)
    decision=dict(allowed[0],reason='Legacy supported evidence contract',evidence_ids=['e1'])
    assert policy.guard(decision,c,allowed)==decision


def test_model_omission_requires_repair_and_evidence_cannot_be_invented():
    c=context();c['network'][1]['transferable_units']=0;c['network'][1]['expiry_buckets']=[]
    allowed=policy.candidates(c);decision=dict(allowed[0],reason='Synthetic campaign requirement')
    del decision['need_by']
    with pytest.raises(Problem,match='Invalid decision schema'):policy.guard(decision,c,allowed)
    decision['need_by']=allowed[0]['need_by'];decision['evidence_ids']=['misspelled-tool-id']
    with pytest.raises(Problem,match='Unknown evidence'):policy.guard(decision,c,allowed)
    decision['evidence_ids']=allowed[0]['evidence_ids']
    assert policy.guard(decision,c,allowed)==decision

def test_infeasible_expiry_never_transferred():
    c=context(); c['network'][1]['expiry_buckets'][0]['expiresAt']=stamp(now()+timedelta(hours=1))
    assert policy.transfer_capacity(c['network'][1],c['forecast'],c['need_by'])==0

def test_strict_schema_fixture_contracts():
    from hemoflow.common import ROOT
    for fixture in (ROOT/'fixtures').glob('decision-*.json'):
        policy.VALIDATOR.validate(json.loads(fixture.read_text()))
