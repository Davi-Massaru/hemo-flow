"""Production command handlers. Web never writes workflow entities directly."""
import json, uuid, hashlib, math, time
from datetime import timedelta
import iris
from . import repository as repo, federation, intelligence, policy, workflow, metrics
from .common import dumps, stamp, now, date, require, Problem, COMPONENT, BLOOD
from .fhir import supply_request, supply_delivery
from .products import validate_product, matches

def actor(identity): return repo.get('User',identity)

def permission(user,role,scope=None):
    require(user['role']==role or user['role']=='admin','Permission denied',403)
    if scope: require(user['role']=='admin' or user['scope']==scope,'Institution scope denied',403)

def transition(kind,row,new,user,**data):
    old=row['status']; row.update(data,status=new); repo.put(kind,row)
    repo.audit('EventAudit',row['correlation_id'],kind.upper()+'_TRANSITION',user['id'],
               entity_id=row['id'],previous=old,current=new,**data)
    return row

def approver(scope,role='manager'):
    users=[u for u in repo.all('User',scope=scope) if u['role']==role]
    require(users,'Institution has no authorized approver',409)
    return users[0]['id']

def decide(command,user):
    """Compatibility entry: all decisions are orchestrated by the Production BPL."""
    result=federation.call('DecisionBPL',dict(command,op='decide',actor_id=user['id']))
    require(result.get('ok'),result.get('error','Decision failed'),result.get('status',503))
    return result['result']

def command_identity(command,user):
    excluded={'correlation_id'}
    key=user['id']+':'+command['op']+':'+command['idempotency_key']
    if command['op']=='decide' and command.get('event_id'):
        scope=command.get('center_id',user['scope']);permission(user,'manager',scope)
        key='event:'+scope+':'+command['event_id'];excluded.add('actor_id')
    fingerprint=hashlib.sha256(dumps({k:v for k,v in command.items() if k not in excluded}).encode()).hexdigest()
    return key,fingerprint

def begin_decision(command):
    user=actor(command['actor_id'])
    if command['op']=='recover_decision':
        context=repo.get('DecisionContext',command['request_id']);permission(user,'manager',context['scope'])
        audit=repo.get('DecisionAudit',context['id'])
        require(audit['status']=='DECIDED','Decision is not recoverable',409)
        return dict(ok=True,route=audit['decision']['decision'],request_id=context['id'],result=audit)
    key,fingerprint=command_identity(command,user)
    previous=repo.get('Command',key,False)
    if previous:
        require(previous['fingerprint']==fingerprint,'Idempotency key reused with different payload',409)
        if previous.get('result') is not None:return previous['result']
        require(time.time()<previous['deadline_epoch'],'Evaluation interrupted; operational review required',409)
        raise Problem(409,'Evaluation already in progress')
    original=dict(command)
    if command['op']=='demo_scenario':
        from .demo import restore,guard,SCENARIOS
        guard(user);scenario=command['scenario'];require(scenario in SCENARIOS,'Unknown scenario')
        if scenario=='EXPIRED_INVITE':return dict(ok=True,result=demo_scenario(command,user))
        restore(user,scenario)
        command=dict(command,center_id='HEMO-A',need_by=stamp(now()+timedelta(hours=12 if scenario=='STOCKOUT' else 168)))
    scope=command.get('center_id',user['scope']); permission(user,'manager',scope)
    blood_type=validate_product(command.get('blood_type',BLOOD),command.get('component',COMPONENT))
    need=command.get('need_by',stamp(now()+timedelta(days=7)))
    require(date(need)>now(),'Need date must be future')
    identity=command['correlation_id']
    # One open plan per center avoids over-ordering on repeated analyses.
    open_transfers=[r for r in repo.all('Transfer',scope=scope) if matches(r,blood_type) and r['status'] in ('PENDING_SOURCE_APPROVAL','APPROVED','REQUESTED','IN_TRANSIT')]
    require(not open_transfers or command.get('review_only'),'An active transfer already covers this center; finish or decline it first',409)
    center=repo.get('NetworkCenter',scope)
    for pending in repo.all('DecisionContext',scope=scope,state='ANALYZING'):
        require(not (matches(pending,blood_type) and pending.get('deadline_epoch',0)>time.time()),'Evaluation already in progress for this center and blood type',409)
    context=dict(id=identity,scope=scope,center_id=scope,blood_type=blood_type,component=COMPONENT,region=center['region'],
        need_by=need,correlation_id=identity,demo_run_id=center.get('demo_run_id'),expires_at=stamp(now()+timedelta(minutes=5)),
        status='ANALYZING',command=original,command_key=key,actor_id=user['id'],deadline_epoch=time.time()+100,
        evidence_version=0,observations={},evidence_ids=[],confirmed_receipts=[],
        allowed_centers=[r['id'] for r in repo.all('NetworkCenter')])
    repo.put('DecisionContext',context,create=True)
    repo.put('Command',dict(id=key,fingerprint=fingerprint,status='ANALYZING',result=None,
        request_id=identity,correlation_id=identity,deadline_epoch=context['deadline_epoch']),create=True)
    if command.get('review_only'):
        audit=repo.put('DecisionAudit',dict(id=identity,scope=scope,blood_type=blood_type,correlation_id=identity,status='ESCALATED',
            reason='One review after expiry or decline; a manager must authorize new planning'),create=True)
        return complete_decision(context,dict(ok=True,result=audit,correlation_id=identity))
    return dict(ok=True,evaluate=True,request_id=identity,correlation_id=identity)

def complete_decision(context,result):
    command=context['command']
    if command['op']=='demo_scenario':
        scenario=command['scenario']
        if not result.get('ok') and scenario in ('OFFLINE','STOCKOUT'):
            result=dict(ok=True,result=dict(message='Expected operational review: '+result['error'],scenario=scenario,
                expected_block=True,correlation_id=context['id']))
        elif result.get('ok'):
            audit=result['result']
            if scenario=='DECLINED':
                row=repo.get('Transfer','TR-'+context['id'])
                if row['status']=='PENDING_SOURCE_APPROVAL':
                    for _ in range(30):
                        if list(iris.sql.exec('SELECT ID FROM EnsLib_Workflow.TaskResponse WHERE %Subject=?',row['id'])):break
                        time.sleep(.1)
                    transfer_reply(dict(id=row['id'],accept=False),repo.get('User',approver(row['source_center_id'])))
            result=dict(ok=True,result=dict(message='Scenario '+scenario+': '+audit['decision']['decision'],
                decision_id=audit['id'],scenario=scenario),correlation_id=context['id'])
    record=repo.get('Command',context['command_key'])
    record.update(status='DONE',result=result);repo.put('Command',record)
    context.update(status='DONE');repo.put('DecisionContext',context)
    return result

def fail_decision(context,error,status=503):
    audit=repo.get('DecisionAudit',context['id'],False) or dict(id=context['id'],scope=context['scope'],correlation_id=context['id'])
    audit.update(status='ESCALATED',reason=error);repo.put('DecisionAudit',audit)
    return complete_decision(context,dict(ok=False,status=status,error=error,correlation_id=context['id']))

def validate_decision(context,result):
    require('decision' in result,'AI Hub unavailable or output invalid',503)
    require(time.time()<context['deadline_epoch'],'Decision deadline expired',409)
    catalog=context.get('catalog',{})
    require(catalog.get('evidence_version')==context['evidence_version']==result.get('evidence_version'),'Evidence revision changed',409)
    decision=policy.guard(result['decision'],context,policy.candidates(context))
    require(decision in [dict(c,reason=decision['reason']) for c in catalog['candidates']],'Candidate catalog changed',409)
    audit=repo.put('DecisionAudit',dict(id=context['id'],scope=context['scope'],correlation_id=context['id'],status='DECIDED',
        decision=decision,ai=result,forecast=context['forecast'],candidates=catalog['candidates'],kpi_before=metrics.risk(context),
        evidence_ids=context['evidence_ids'],evidence_version=context['evidence_version'],observations=context['observations'],
        similar_campaigns=context.get('similar_campaigns'),network_summary=[dict(center_id=r['center_id'],status=r['status']) for r in context['network']]))
    context['status']='VALIDATED';repo.put('DecisionContext',context)
    repo.audit('EventAudit',context['id'],'DECISION_VALIDATED',context['actor_id'],decision=decision['decision'],evidence_version=context['evidence_version'])
    if decision['decision']=='NO_ACTION':
        return complete_decision(context,dict(ok=True,result=audit,correlation_id=context['id']))
    repo.put('Outbox',dict(id='route:'+context['id'],event='DECISION_ROUTING_PENDING',status='PENDING',
        center_id=context['scope'],request_id=context['id'],correlation_id=context['id'],not_before=time.time()+15))
    return dict(ok=True,route=decision['decision'],request_id=context['id'],result=audit)

def start_proposal(context,route):
    audit=repo.get('DecisionAudit',context['id']);decision=audit['decision'];user=actor(context['actor_id'])
    require(audit['status']=='DECIDED' and decision['decision']==route,'Decision does not authorize this workflow',403)
    key=context['id'];scope=context['scope'];center=repo.get('NetworkCenter',scope)
    kind='Transfer' if route=='REQUEST_TRANSFER' else 'Campaign'
    identity=('TR-' if kind=='Transfer' else 'CA-')+key
    row=repo.get(kind,identity,False)
    if row is None:
        require(time.time()<context['deadline_epoch'],'Decision expired before routing',409)
        require(context['status']=='VALIDATED','Decision not validated',409)
        conflicts=[r for r in repo.all('Transfer',scope=scope) if matches(r,context['blood_type']) and r['status'] in ('PENDING_SOURCE_APPROVAL','APPROVED','REQUESTED','IN_TRANSIT')]
        require(not conflicts,'An active transfer already covers this center; operational review required',409)
        if kind=='Campaign':
            require(not any(matches(r,context['blood_type']) and r['status'] in ('PENDING_CENTER_APPROVAL','AWAITING_PARTNER','CONFIRMED') for r in repo.all('Campaign',scope=scope)), 'An active campaign already covers this planning scope',409)
        row=dict(decision,id=identity,scope=scope,correlation_id=key,demo_run_id=center.get('demo_run_id'))
        if kind=='Transfer':row.update(status='PENDING_SOURCE_APPROVAL',approved_units=0,received_units=0,used_units=0)
        else:row.update(similar_campaigns=context.get('similar_campaigns'),forecast=context['forecast'],projected_deficit=metrics.risk(context)['deficit'],status='PENDING_CENTER_APPROVAL',invited=0,interested=0,collected=0,released_usable=0,used_before_expiry=0)
        repo.put(kind,row,create=True)
    if row['status'] in ('PENDING_SOURCE_APPROVAL','PENDING_CENTER_APPROVAL'):
        workflow.start(row,approver(row['source_center_id'] if kind=='Transfer' else scope),
            'Confirm source stock, handling and transport' if kind=='Transfer' else 'Authorize collection plan and release window')
    if not audit.get('routed_to'):
        audit.update(routed_to='TransferBPL' if kind=='Transfer' else 'CampaignBPL');repo.put('DecisionAudit',audit)
        repo.audit('EventAudit',key,'DECISION_ROUTED',user['id'],target=audit['routed_to'],entity_id=identity)
    event=repo.get('Outbox','route:'+key);event['status']='DONE';repo.put('Outbox',event)
    return complete_decision(context,dict(ok=True,result=audit,correlation_id=key))

def execute_phase(phase,raw):
    """Internal message phase is set by BPL, never accepted from HTTP JSON."""
    data=json.loads(raw);runtime=iris.cls('HemoFlow.Runtime');context=None
    require(runtime.Lock('mutations'),'Busy, retry command',409)
    try:
        if phase=='prepare':result=begin_decision(data)
        else:
            context=repo.get('DecisionContext',data['request_id'])
            if phase=='guard':result=validate_decision(context,data['ai'])
            elif phase in ('start_transfer','start_campaign'):result=start_proposal(context,'REQUEST_TRANSFER' if phase=='start_transfer' else 'REQUEST_CAMPAIGN')
            else:raise Problem(403,'Unknown internal phase')
        return dumps(result)
    except Exception as exc:
        error=exc.message if isinstance(exc,Problem) else type(exc).__name__
        status=exc.status if isinstance(exc,Problem) else 503
        return dumps(fail_decision(context,error,status) if context else dict(ok=False,status=status,error=error))
    finally:runtime.Unlock('mutations')

def transfer_reply(command,user):
    row=repo.get('Transfer',command['id']); permission(user,'manager',row['source_center_id'])
    require(row['status']=='PENDING_SOURCE_APPROVAL','Transfer is not awaiting approval',409)
    require(type(command.get('accept')) is bool,'accept must be boolean')
    if not command['accept']:
        workflow.complete(row,user['id'],'DECLINE')
        result=transition('Transfer',row,'DECLINED',user)
        repo.put('Outbox',dict(id='declined:'+row['id'],status='PENDING',event='TRANSFER_DECLINED',
                              center_id=row['target_center_id'],correlation_id=row['correlation_id']))
        return result
    # No remote write until explicit source confirmation of handling conditions.
    require(command.get('handling_confirmed') is True,'Source must confirm handling conditions')
    current=federation.inventory(row['source_center_id'],row['target_center_id'],row['need_by'],row['correlation_id'],row.get('blood_type',BLOOD))
    require(current['status']=='AVAILABLE','Source unavailable',503)
    forecast=intelligence.forecast(row['target_center_id'],row.get('blood_type',BLOOD))
    require(forecast['method']=='INTEGRATEDML' and not forecast['quality_flags'],'Forecast quality changed',409)
    require(policy.transfer_capacity(current,forecast,row['need_by'])>=row['requested_units'],'Availability or expiry changed',409)
    workflow.complete(row,user['id'],'ACCEPT')
    try:
        request=supply_request(row)
        # Conservatively require all units to survive need_by at approval.
        federation.exchange(row['source_center_id'],'/fhir/SupplyRequest',request,{'X-Daily-Use':str(forecast['expected_units']/7)})
        transition('Transfer',row,'APPROVED',user,approved_units=row['requested_units'])
        return transition('Transfer',row,'REQUESTED',user,fhir_request=request,
            fhir_request_uri=federation.center(row['source_center_id'])['endpoint']+'/fhir/SupplyRequest/'+row['id'])
    except Problem:
        transition('Transfer',row,'FAILED',user)
        raise

def dispatch(command,user):
    row=repo.get('Transfer',command['id']); permission(user,'manager',row['source_center_id'])
    require(row['status']=='REQUESTED','Transfer has not been requested',409)
    shipment=federation.exchange(row['source_center_id'],'/transfers/'+row['id']+'/dispatch',{})
    require(all(unit.get('blood_type',BLOOD)==row.get('blood_type',BLOOD) for unit in shipment.get('units',[])), 'Shipment blood type mismatch',409)
    # Individual unit payload stays transient; logistics audit keeps only resource references/count.
    context_id='shipment:'+row['id']
    repo.put('DecisionContext',dict(id=context_id,shipment=shipment,correlation_id=row['correlation_id'],expires_at=stamp(now()+timedelta(days=2))))
    return transition('Transfer',row,'IN_TRANSIT',user,shipment_context_id=context_id)

def delivery(command,user):
    row=repo.get('Transfer',command['id']); permission(user,'manager',row['target_center_id'])
    require(row['status']=='IN_TRANSIT','Transfer is not in transit',409)
    require(command.get('receipt_confirmed') is True,'Destination must confirm receipt')
    context=repo.get('DecisionContext',row['shipment_context_id'])
    require(all(unit.get('blood_type',BLOOD)==row.get('blood_type',BLOOD) for unit in context['shipment'].get('units',[])), 'Shipment blood type mismatch',409)
    received=federation.exchange(row['target_center_id'],'/transfers/'+row['id']+'/receive',context['shipment'])
    resource=supply_delivery(row,received['received_units'])
    federation.exchange(row['target_center_id'],'/fhir/SupplyDelivery',resource)
    return transition('Transfer',row,'DELIVERED',user,received_units=received['received_units'],fhir_delivery=resource)

def campaign_approve(command,user):
    row=repo.get('Campaign',command['id']); permission(user,'manager',row['scope'])
    require(row['status']=='PENDING_CENTER_APPROVAL','Campaign not awaiting approval',409)
    require(type(command.get('accept')) is bool,'accept must be boolean')
    if not command['accept']:
        workflow.complete(row,user['id'],'DECLINE')
        return transition('Campaign',row,'CANCELLED',user)
    require(date(row['expected_available_at'])<=date(row['need_by']) and date(row['campaign_window_start'])>now(),'Campaign window no longer viable',409)
    partner=repo.get('Partner',row['partner_id'])
    require(partner['scope']==row['scope'],'Partner scope mismatch',403)
    recipients=[dict(id=partner['id'],type='PARTNER')]
    if command.get('mode')=='CENTER_DIRECT':
        recipients=[dict(id=d['id'],type='DONOR',opt_in=True) for d in repo.all('DonorContact',scope=row['scope']) if d['opt_in']]
        require(recipients,'No consented contacts')
    result=federation.call('CampaignCreationOperation',dict(campaign_id=row['id'],approved=True,
        recipients=recipients,correlation_id=row['correlation_id']))
    workflow.complete(row,user['id'],'ACCEPT')
    ttl=repo.config('invite_ttl_hours',24)
    for invitation in result['invitations']:
        scope=invitation['recipient_id']
        invitation.update(scope=scope,center_id=row['scope'],status='PENDING',
            demo_run_id=row.get('demo_run_id'),
            correlation_id=row['correlation_id'],expires_at=stamp(now()+timedelta(hours=ttl)),published_at=stamp())
        if not repo.get('InvitationLedger',invitation['id'],False):
            repo.put('InvitationLedger',invitation,create=True)
            repo.put('PendingInvitation',dict(invitation),create=True)
            workflow.start(invitation,approver(scope,'partner' if invitation['recipient_type']=='PARTNER' else 'donor'),'Invitation response, expires '+invitation['expires_at'])
    return transition('Campaign',row,'CONFIRMED' if command.get('mode')=='CENTER_DIRECT' else 'AWAITING_PARTNER',user,invited=len(recipients),mode=command.get('mode','PARTNER_HOSTED'))

def invitation_reply(command,user):
    row=repo.get('InvitationLedger',command['id'])
    permission(user,'partner' if row['recipient_type']=='PARTNER' else 'donor',row['recipient_id'])
    if row['recipient_type']=='DONOR':require(repo.get('DonorContact',row['recipient_id'])['opt_in'],'Donor no longer opted in',403)
    require(row['status']=='PENDING','Invitation already resolved',409)
    # Query-time expiry is authoritative, even if the automatic sweeper has not run.
    require(now()<date(row['expires_at']),'Invitation expired',409)
    require(type(command.get('accept')) is bool,'accept must be boolean')
    action='ACCEPT' if command['accept'] else 'DECLINE'
    workflow.complete(row,user['id'],action)
    new=('INTERESTED' if row['recipient_type']=='DONOR' else 'ACCEPTED') if command['accept'] else 'DECLINED'
    transition('InvitationLedger',row,new,user,responded_at=stamp())
    repo.delete('PendingInvitation',row['id'])
    campaign=repo.get('Campaign',row['campaign_id'])
    if new=='ACCEPTED': transition('Campaign',campaign,'CONFIRMED',user)
    elif new=='INTERESTED':
        campaign['interested']+=1; repo.put('Campaign',campaign)
    elif new=='DECLINED' and row['recipient_type']=='PARTNER': transition('Campaign',campaign,'CANCELLED',user)
    return row

def campaign_result(command,user):
    row=repo.get('Campaign',command['id']); permission(user,'manager',row['scope'])
    require(row['status']=='CONFIRMED','Campaign not confirmed',409)
    require(date(row['expected_available_at'])<=now(),'Processing and release have not finished',409)
    collected,released,used=(command.get(k,0) for k in ('collected','released_usable','used_before_expiry'))
    if command.get('attended') is not None:
        require(type(command['attended']) is int and command['attended']>=0,'Invalid attendance count')
    require(all(type(v) is int and v>=0 for v in (collected,released,used)) and used<=released<=collected,'Inconsistent campaign outcome')
    require(collected<=repo.get('Partner',row['partner_id'])['capacity'],'Declared collection capacity exceeded')
    expiry=command.get('expires_at')
    require(expiry and date(expiry)>now(),'Origin must declare product expiry')
    federation.exchange(row['scope'],'/campaigns/'+row['id']+'/release',dict(released_units=released-used,expires_at=expiry,blood_type=row.get('blood_type',BLOOD)))
    completed=transition('Campaign',row,'COMPLETED',user,collected=collected,released_usable=released,used_before_expiry=used,attended=command.get('attended'),expires_at=expiry)
    try: intelligence.record_campaign(completed)
    except Exception: repo.audit('EventAudit',row['correlation_id'],'CAMPAIGN_INDEX_PENDING',user['id'],entity_id=row['id'])
    return completed

def registry(command,user):
    from urllib.parse import urlparse
    from .settings import demo
    permission(user,'admin')
    kind=command.get('kind'); require(kind in ('NetworkCenter','Partner'),'Invalid registry kind')
    identity=command.get('id',''); require(1<=len(identity)<=64 and all(c.isalnum() or c in '-_' for c in identity),'Invalid identifier')
    row=dict(id=identity,name=command['name'][:120],region=command['region'][:30])
    if kind=='NetworkCenter':
        endpoint=command['endpoint'].rstrip('/'); url=urlparse(endpoint)
        require(url.scheme=='https' or (demo() and url.scheme=='http' and url.hostname in ('center-a','center-b','center-c')),'Unapproved endpoint transport or host')
        require(not url.username and not url.password and not url.query and not url.fragment,'Endpoint must not contain credentials or query')
        row.update(endpoint=endpoint,secret_ref='HEMOFLOW_CENTER_TOKEN',scope=identity)
        require(len(repo.all('NetworkCenter'))<3,'Demo allows at most three centers')
    else:
        scope=command['scope']; repo.get('NetworkCenter',scope)
        count=int(command['capacity']); require(1<=count<=1000,'Invalid partner capacity')
        row.update(scope=scope,type=command['type'],capacity=count,organize_hours=48,collection_hours=8,processing_hours=48)
    return repo.put(kind,row,create=True)

def demo_seed(command,user):
    from .demo import install
    return install(user,command.get('epoch'))

def demo_restore(command,user):
    from .demo import restore
    return restore(user)

def demo_advance(command,user):
    from .demo import advance
    return advance(user,command.get('hours',25))

def demo_process(command,user):
    from .demo import advance,RUN
    from .settings import demo
    require(demo(),'Simulation disabled',403)
    row=repo.get('Campaign',command['id']);permission(user,'manager',row['scope'])
    require(row.get('demo_run_id')==RUN and row['status']=='CONFIRMED','Only a confirmed synthetic campaign can be simulated',409)
    hours=max(0,(date(row['expected_available_at'])-now()).total_seconds()/3600)+1/3600
    # The explicit demo action advances the shared synthetic clock, never host time.
    advance(repo.get('User','admin'),hours)
    capacity=repo.get('Partner',row['partner_id'])['capacity']
    return campaign_result(dict(id=row['id'],collected=min(capacity,row['target_units']+2),
        released_usable=row['target_units'],used_before_expiry=0,expires_at=stamp(now()+timedelta(days=35))),user)

def demo_scenario(command,user):
    import time
    from .demo import restore,guard,SCENARIOS,RUN
    guard(user);scenario=command['scenario'];require(scenario in SCENARIOS,'Unknown scenario')
    if scenario=='EXPIRED_INVITE':
        try:invitation_reply(dict(id='DEMO-INV-EXPIRED',accept=True),repo.get('User','parceiro-5'))
        except Problem as exc:
            require(exc.status==409,'Unexpected invitation result')
            return dict(message='Expired invitation: acceptance blocked with HTTP 409; ledger preserved.',http_status=409)
        raise Problem(409,'Expired fixture unexpectedly accepted')
    state=restore(user,scenario)
    request=dict(command,center_id='HEMO-A',need_by=stamp(now()+timedelta(hours=12 if scenario=='STOCKOUT' else 7*24)))
    try:decision=decide(request,user)
    except Problem as exc:
        if scenario in ('OFFLINE','STOCKOUT'):
            return dict(message='Expected operational review: '+exc.message,scenario=scenario,expected_block=True,correlation_id=command['correlation_id'])
        raise
    if scenario=='DECLINED':
        row=next(r for r in repo.all('Transfer',scope='HEMO-A') if r['correlation_id']==decision['correlation_id'])
        for _ in range(30):
            if list(iris.sql.exec('SELECT ID FROM EnsLib_Workflow.TaskResponse WHERE %Subject=?',row['id'])):break
            time.sleep(.1)
        transfer_reply(dict(id=row['id'],accept=False),repo.get('User','gestor-b'))
        repo.audit('EventAudit',row['correlation_id'],'DEMO_SOURCE_DECLINED',user['id'],simulated_actor='gestor-b')
    return dict(message='Scenario '+scenario+': '+decision['decision']['decision'],decision_id=decision['id'],scenario=scenario)

HANDLERS={'demo_seed':demo_seed,'demo_restore':demo_restore,'demo_scenario':demo_scenario,'demo_advance':demo_advance,'demo_process':demo_process,
          'registry':registry,'transfer_reply':transfer_reply,'dispatch':dispatch,'delivery':delivery,
          'campaign_approve':campaign_approve,'invitation_reply':invitation_reply,'campaign_result':campaign_result}

def dispatch_outbox():
    # Single periodic service; stable event IDs also deduplicate in the Production.
    for event in repo.all('Outbox',state='PENDING',limit=10):
        if event.get('not_before',0)>time.time():continue
        if event['event']=='DECISION_ROUTING_PENDING':
            try:
                context=repo.get('DecisionContext',event['request_id'])
                event['result']=federation.call('DecisionBPL',dict(op='recover_decision',request_id=context['id'],
                    actor_id=context['actor_id'],correlation_id=context['id']))
                event['status']='DONE' if event['result'].get('ok') else 'FAILED'
            except Exception as exc:
                event.update(status='FAILED',error_type=type(exc).__name__)
            repo.put('Outbox',event)
            continue
        try:
            identity=approver(event['center_id'])
            result=federation.call('DecisionBPL',dict(op='decide',actor_id=identity,center_id=event['center_id'],
                correlation_id=str(uuid.uuid4()),event_id=event['id'],idempotency_key=event['id'],review_only=True))
            event['result']=result
        except Exception as exc:event['error_type']=type(exc).__name__
        event['status']='DONE';repo.put('Outbox',event)
    runtime=iris.cls('HemoFlow.Runtime')
    if not runtime.Lock('mutations'):return
    try:
        for record in repo.all('Command',state='ANALYZING',limit=100):
            if record['deadline_epoch']>=time.time():continue
            context=repo.get('DecisionContext',record['request_id'],False)
            if context and context['status']=='ANALYZING':fail_decision(context,'Evaluation interrupted or timed out; operational review required')
    finally:runtime.Unlock('mutations')

def execute(raw):
    command=json.loads(raw); runtime=iris.cls('HemoFlow.Runtime')
    require(runtime.Lock('mutations'),'Busy, retry command',409)
    try:
        user=actor(command['actor_id'])
        operation=command['op']
        if operation=='settings':
            permission(user,'admin'); ttl=command['hours']; require(type(ttl) is int and 1<=ttl<=168,'TTL must be 1..168h')
            return dumps(dict(ok=True,result=repo.put('SystemConfig',dict(id='invite_ttl_hours',value=ttl))))
        require(operation in HANDLERS,'Unknown command')
        # Actor and operation are part of idempotency identity. Payload reuse is checked.
        key=user['id']+':'+operation+':'+command['idempotency_key']
        excluded={'correlation_id'}
        if operation=='decide' and command.get('event_id'):
            scope=command.get('center_id',user['scope']);permission(user,'manager',scope)
            key='event:'+scope+':'+command['event_id'];excluded.add('actor_id')
        fingerprint=hashlib.sha256(dumps({k:v for k,v in command.items() if k not in excluded}).encode()).hexdigest()
        previous=repo.get('Command',key,False)
        if previous:
            require(previous['fingerprint']==fingerprint,'Idempotency key reused with different payload',409)
            return dumps(previous['result'])
        try:
            result=dict(ok=True,result=HANDLERS[operation](command,user),correlation_id=command['correlation_id'])
        except Problem as exc: result=dict(ok=False,status=exc.status,error=exc.message,correlation_id=command['correlation_id'])
        repo.put('Command',dict(id=key,fingerprint=fingerprint,result=result,correlation_id=command['correlation_id']),create=True)
        return dumps(result)
    except Problem as exc: return dumps(dict(ok=False,status=exc.status,error=exc.message))
    except Exception as exc:
        repo.audit('EventAudit',command.get('correlation_id',''),'COMMAND_FAILED',command.get('actor_id',''),error_type=type(exc).__name__)
        return dumps(dict(ok=False,status=503,error='Operational failure; inspect correlation audit',error_type=type(exc).__name__))
    finally: runtime.Unlock('mutations')
