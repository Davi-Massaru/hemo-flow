"""Final demonstration seed, installed only after the real application gate.

Fixed identities and anchor, no overwrite on install. Restore touches only marked
synthetic state, takes backups, closes open plans and preserves all audit/ledgers.
"""
import json,hashlib,uuid
from datetime import timedelta
from pathlib import Path
import iris
from . import repository as repo,federation,intelligence,workflow
from .common import now,stamp,date,require,checked,dumps
from .settings import demo as demo_enabled
from .products import BLOOD_TYPES

RUN='hemoflow-demo-v1'
PASSWORD='DemoHemoFlow2026!'
SCENARIOS=('TRANSFER','CAMPAIGN','NO_ACTION','EXPIRY','STOCKOUT','OFFLINE','DECLINED','EXPIRED_INVITE')

def guard(user):
    require(demo_enabled(),'Demonstration operations disabled',403)
    require(user['role']=='admin','Administrator required',403)

def password_hash(identity):
    salt=hashlib.sha256((RUN+identity).encode()).hexdigest()[:16]
    value=hashlib.pbkdf2_hmac('sha256',PASSWORD.encode(),salt.encode(),600000).hex()
    return 'pbkdf2:sha256:600000$'+salt+'$'+value

def save(kind,row,anchor):
    old=repo.get(kind,row['id'],False)
    require(not old or old.get('demo_run_id')==RUN,'Existing '+kind+' prevents seed: '+row['id'],409)
    if old:return old
    return repo.put(kind,dict(row,demo_run_id=RUN,created_at=anchor),create=True)

def manifests(anchor,scenario='TRANSFER'):
    counts={'HEMO-A':8,'HEMO-B':16,'HEMO-C':4}
    if scenario=='CAMPAIGN':counts['HEMO-B']=4
    if scenario=='NO_ACTION':counts.update({'HEMO-A':45,'HEMO-B':4})
    if scenario=='STOCKOUT':counts.update({'HEMO-A':0,'HEMO-B':4})
    result={}
    for center_id,count in counts.items():
        units=[]
        for i in range(count):
            offset=3 if center_id=='HEMO-B' and scenario in ('TRANSFER','DECLINED') and i<6 else 15
            expiry=date(anchor)+timedelta(days=offset)
            if center_id=='HEMO-B' and scenario=='EXPIRY':expiry=date(anchor)+timedelta(hours=1)
            units.append(dict(id=f'DEMO-{center_id}-FREE-{i:03d}',expires=stamp(expiry)))
        for state,offset in (('RESERVED',10),('BLOCKED',5),('EXPIRED',-1)):
            for i in range(2):
                units.append(dict(id=f'DEMO-{center_id}-{state}-{i}',expires=stamp(date(anchor)+timedelta(days=offset)),
                                  reserved=int(state=='RESERVED'),blocked=int(state=='BLOCKED')))
        center_index=('HEMO-A','HEMO-B','HEMO-C').index(center_id)
        for group_index,group in enumerate(BLOOD_TYPES[1:],1):
            amount=(8,42,14,29,6,18,10)[group_index-1]+center_index*7
            if (center_index+group_index)%4==0:amount=3
            for i in range(amount):
                units.append(dict(id=f'DEMO-V2-{center_id}-{group}-FREE-{i:03d}',blood_type=group,
                    expires=stamp(date(anchor)+timedelta(days=2 if i<3 and group_index%2 else 9+i%18))))
            for state in ('RESERVED','BLOCKED','EXPIRED'):
                units.append(dict(id=f'DEMO-V2-{center_id}-{group}-{state}',blood_type=group,
                    expires=stamp(date(anchor)+timedelta(days=-1 if state=='EXPIRED' else 12)),reserved=int(state=='RESERVED'),blocked=int(state=='BLOCKED')))
        result[center_id]=dict(run_id=RUN,center_id=center_id,epoch=anchor,units=units,
            settings=dict(reserve=4,lead_hours=4,offline=int(scenario=='OFFLINE' and center_id=='HEMO-C'),decline=0))
    return result

def native_user(identity):
    user=iris.cls('EnsLib.Workflow.UserDefinition');role=iris.cls('EnsLib.Workflow.RoleDefinition')
    if not user._ExistsId(identity):checked(user.CreateUser(identity,identity))
    if not role._ExistsId('Approvals'):checked(role.CreateRole('Approvals'))
    exists=list(iris.sql.exec('SELECT COUNT(*) FROM EnsLib_Workflow.RoleMembership WHERE RoleName=? AND UserName=?','Approvals',identity))[0][0]
    if not exists:checked(role.AddUserToRole('Approvals',identity))

def install(user,epoch=None):
    guard(user)
    run=repo.get('DemoRun',RUN,False)
    if run and run['status']=='READY':
        if run.get('version',1)<2:return upgrade(user)
        repaired=repair_legacy_history(user)
        if repaired or repo.config('history_repair_pending',False):
            run['model']=intelligence.train();repo.put('DemoRun',run)
            repo.put('SystemConfig',dict(id='history_repair_pending',value=False))
            return dict(status='REPAIRED',run_id=RUN,repaired_rows=repaired,version=2)
        return dict(status='ALREADY_LOADED',run_id=RUN,epoch=run['epoch'])
    anchor=run['epoch'] if run else (epoch or stamp(now().replace(hour=0,minute=0,second=0,microsecond=0)))
    date(anchor)
    # Refuse mixed real/demo registries and datasets before loading any data.
    for kind in ('NetworkCenter','Partner','DonorContact','Transfer','Campaign'):
        require(all(r.get('demo_run_id')==RUN for r in repo.all(kind)),'Existing non-demo '+kind+' prevents seed',409)
    for cls in ('ConsumptionDaily','CampaignExperience'):
        require(not list(iris.sql.exec('SELECT TOP 1 ExternalId FROM HemoFlow.'+cls+" WHERE NOT (ExternalId %STARTSWITH 'DEMO-')")),
                'Existing non-demo '+cls+' prevents seed',409)
    if not run:run=repo.put('DemoRun',dict(id=RUN,status='PREPARING',epoch=anchor,version=1,synthetic=True))
    center_names=('Aurora Blood Center','Bandeirantes Blood Center','Central Blood Center')
    for index,center_id in enumerate(('HEMO-A','HEMO-B','HEMO-C')):
        save('NetworkCenter',dict(id=center_id,name=center_names[index],scope=center_id,region='SP',
             endpoint='http://center-'+center_id[-1].lower()+':8080',secret_ref='HEMOFLOW_CENTER_TOKEN'),anchor)
    remote=manifests(anchor)
    for center_id,manifest in remote.items():federation.http(center_id,'/demo/seed',manifest)
    partner_names=('Horizon University','Vida Company','Solidarity Network NGO','Hope Church','Valley University','Tomorrow Company')
    types=('UNIVERSITY','COMPANY','NGO','CHURCH','UNIVERSITY','COMPANY')
    for i,name in enumerate(partner_names):
        scope=('HEMO-A','HEMO-A','HEMO-B','HEMO-B','HEMO-C','HEMO-C')[i]
        save('Partner',dict(id='PARTNER-'+str(i+1),name=name,type=types[i],scope=scope,region='SP',
                           capacity=30+i*3,organize_hours=48,collection_hours=8,processing_hours=48),anchor)
    people=[('gestor-a','manager','HEMO-A'),('gestor-b','manager','HEMO-B'),('gestor-c','manager','HEMO-C'),('auditor','auditor','NETWORK')]
    people += [('parceiro-'+str(i),'partner','PARTNER-'+str(i)) for i in range(1,7)]
    people += [('doador-'+str(i),'donor','DONOR-'+str(i)) for i in range(1,4)]
    for identity,role,scope in people:
        save('User',dict(id=identity,name=identity,role=role,scope=scope,password_hash=password_hash(identity)),anchor)
        if role!='auditor':native_user(identity)
    for i in range(1,4):
        save('DonorContact',dict(id='DONOR-'+str(i),scope='HEMO-A',opt_in=i!=3,channel='DEMO_ONLY',
                               name='Synthetic donor '+str(i)),anchor)
    for center_index,center_id in enumerate(('HEMO-A','HEMO-B','HEMO-C')):
        for day in range(180):
            day_value=(date(anchor)-timedelta(days=180-day)).date().isoformat()
            identity='DEMO-'+center_id+'-'+day_value
            exists=list(iris.sql.exec('SELECT COUNT(*) FROM HemoFlow.ConsumptionDaily WHERE ExternalId=?',identity))[0][0]
            if not exists:
                units=2+(day%11)//4+(day//21)%2+center_index
                iris.sql.exec("INSERT INTO HemoFlow.ConsumptionDaily (ExternalId,CenterId,Day,UsedUnits,DemandUnmet) VALUES(?,?,TO_DATE(?,'YYYY-MM-DD'),?,?)",
                              identity,center_id,day_value,units,int(day in (65,66)))
    for i in range(40):
        identity=f'DEMO-EXP-{i+1:03d}'
        if list(iris.sql.exec('SELECT COUNT(*) FROM HemoFlow.CampaignExperience WHERE ExternalId=?',identity))[0][0]:continue
        partner_id='PARTNER-'+str(i%6+1);partner=repo.get('Partner',partner_id)
        summary=f"{partner['type']} blood donation campaign, red cells O negative shortage, Sao Paulo region, {20+i%10} usable units released after processing, {15+i%8} used before expiry."
        metrics=dict(invited=80+i,attended=40+i%15,collected=28+i%10,released_usable=20+i%10,
                     used_before_expiry=15+i%8,period=(date(anchor)-timedelta(days=10+i*3)).date().isoformat(),synthetic=True)
        iris.sql.exec('''INSERT INTO HemoFlow.CampaignExperience
            (ExternalId,PartnerId,PartnerType,Region,Summary,ReleasedUsable,Metrics,Embedding,EmbeddingModel,ContentHash)
            VALUES(?,?,?,?,?,?,?,TO_VECTOR(?,DOUBLE),?,?)''',identity,partner_id,partner['type'],'SP',summary,
            metrics['released_usable'],dumps(metrics),intelligence.embedding(summary),
            'BAAI/bge-small-en-v1.5',hashlib.sha256(summary.encode()).hexdigest())
    # Durable historical states; examples are labelled fixtures, never claimed as traces.
    for suffix,status,received,used in (('DELIVERED','DELIVERED',10,6),('DECLINED','DECLINED',0,0),('PENDING','PENDING_SOURCE_APPROVAL',0,0)):
        target='HEMO-C' if suffix=='PENDING' else 'HEMO-A'
        row=save('Transfer',dict(id='DEMO-TR-'+suffix,scope=target,source_center_id='HEMO-B',target_center_id=target,
            component='RED_BLOOD_CELLS',blood_type='O-',requested_units=10,approved_units=received,
            received_units=received,used_units=used,status=status,need_by=stamp(date(anchor)+timedelta(days=7)),
            correlation_id='DEMO-TR-'+suffix,synthetic_fixture=True),anchor)
        if status=='PENDING_SOURCE_APPROVAL':workflow.start(row,'gestor-b','Synthetic source approval example')
    examples=(('PENDING','HEMO-B','PARTNER-3','PENDING_CENTER_APPROVAL'),('WAITING','HEMO-C','PARTNER-5','AWAITING_PARTNER'),
              ('CONFIRMED','HEMO-B','PARTNER-4','CONFIRMED'),('COMPLETED','HEMO-C','PARTNER-6','COMPLETED'),
              ('CANCELLED','HEMO-B','PARTNER-3','CANCELLED'))
    for suffix,scope,partner_id,status in examples:
        start=date(anchor)+timedelta(days=-10 if status=='COMPLETED' else 2)
        row=save('Campaign',dict(id='DEMO-CA-'+suffix,scope=scope,requesting_center_id=scope,partner_id=partner_id,
            status=status,target_units=20,invited=1,interested=0,collected=24 if status=='COMPLETED' else 0,
            released_usable=20 if status=='COMPLETED' else 0,used_before_expiry=18 if status=='COMPLETED' else 0,
            campaign_window_start=stamp(start),campaign_window_end=stamp(start+timedelta(hours=8)),
            expected_available_at=stamp(start+timedelta(days=2,hours=8)),need_by=stamp(start+timedelta(days=5)),
            correlation_id='DEMO-CA-'+suffix,synthetic_fixture=True),anchor)
        if status=='PENDING_CENTER_APPROVAL':workflow.start(row,'gestor-b','Synthetic campaign manager approval')
    for suffix,status,scope,campaign in (('PENDING','PENDING','PARTNER-5','WAITING'),('ACCEPTED','ACCEPTED','PARTNER-4','CONFIRMED'),
        ('DECLINED','DECLINED','PARTNER-3','CANCELLED'),('EXPIRED','EXPIRED','PARTNER-5','WAITING')):
        expires=stamp(date(anchor)+timedelta(hours=24)) if status=='PENDING' else stamp(date(anchor)-timedelta(hours=1))
        row=save('InvitationLedger',dict(id='DEMO-INV-'+suffix,scope=scope,recipient_id=scope,recipient_type='PARTNER',
            center_id='HEMO-C' if scope=='PARTNER-5' else 'HEMO-B',campaign_id='DEMO-CA-'+campaign,
            status=status,expires_at=expires,published_at=stamp(date(expires)-timedelta(hours=24)),
            correlation_id='DEMO-INV-'+suffix,synthetic_fixture=True),anchor)
        if status=='PENDING':
            save('PendingInvitation',dict(row),anchor);workflow.start(row,'parceiro-5','Synthetic partner invitation')
    run.update(status='READY',counts=dict(centers=3,partners=6,history_days=180,consumption_rows=540,experiences=40,users=len(people)),
               model=intelligence.train(),manifest_hash=hashlib.sha256(dumps(remote).encode()).hexdigest())
    repo.put('DemoRun',run)
    repo.audit('EventAudit',RUN,'DEMO_SEED_LOADED',user['id'],counts=run['counts'],epoch=anchor)
    return upgrade(user)

def repair_legacy_history(user):
    """Recover the known v1 list layout; reject unidentified data, never guess values."""
    guard(user)
    rows=[list(r) for r in iris.sql.exec('SELECT ExternalId,CenterId,BloodType,Day,UsedUnits,DemandUnmet FROM HemoFlow.ConsumptionDaily')
          if str(r[2]) not in BLOOD_TYPES and r[2] not in (None,'')]
    if not rows:return 0
    from datetime import datetime,timezone
    epoch=datetime(1840,12,31,tzinfo=timezone.utc)
    for identity,center,old_day,old_used,old_unmet,missing in rows:
        require(str(old_day).isdigit() and missing in (None,'') and int(old_unmet) in (0,1),'Unrecognized historical storage layout',409)
        day=(epoch+timedelta(days=int(old_day))).date().isoformat()
        require(identity=='DEMO-'+center+'-'+day and int(old_used)>=0,'History ownership or date mismatch',409)
    backup_dir=Path('/durable/hemoflow-demo-backups');backup_dir.mkdir(exist_ok=True)
    backup=backup_dir/('history-layout-'+uuid.uuid4().hex+'.json');backup.write_text(dumps(rows))
    repo.put('SystemConfig',dict(id='history_repair_pending',value=True))
    for identity,center,old_day,old_used,old_unmet,missing in rows:
        result=iris.cls('%SQL.Statement')._ExecDirect('',"UPDATE HemoFlow.ConsumptionDaily SET BloodType='O-',Day=?,UsedUnits=?,DemandUnmet=? WHERE ExternalId=?",int(old_day),int(old_used),int(old_unmet),identity)
        require(result._SQLCODE==0,'History layout migration failed')
    checked(iris.cls('HemoFlow.ConsumptionDaily')._BuildIndices())
    repo.audit('EventAudit',RUN,'DEMO_HISTORY_LAYOUT_REPAIRED',user['id'],rows=len(rows),backup=str(backup))
    return len(rows)

def upgrade(user):
    """Add version-two fixtures without resetting v1 stock, workflows or audit."""
    guard(user);run=repo.get('DemoRun',RUN)
    if run.get('version',1)>=2:return dict(status='ALREADY_LOADED',run_id=RUN,version=2)
    require(run['status']=='READY','Original seed must be ready',409)
    repair_legacy_history(user)
    backup_dir=Path('/durable/hemoflow-demo-backups');backup_dir.mkdir(exist_ok=True)
    backup=backup_dir/('multitype-v2-'+uuid.uuid4().hex+'.json')
    backup.write_text(dumps(dict(run=run,model=repo.config('forecast_model'),
        features=[list(r) for r in iris.sql.exec('SELECT CenterId,Day,Avg7,Avg28,DayOfWeek,MonthNumber,Target7d,Split FROM HemoFlow.DemandFeature')])) )
    anchor=run['epoch']
    for center,manifest in manifests(stamp()).items():federation.http(center,'/demo/extend',manifest)
    for table in ('ConsumptionDaily','DemandFeature'):
        result=iris.cls('%SQL.Statement')._ExecDirect('',"UPDATE HemoFlow."+table+" SET BloodType='O-' WHERE BloodType IS NULL")
        require(result._SQLCODE in (0,100),'Legacy product migration failed')
    checked(iris.cls('HemoFlow.ConsumptionDaily')._BuildIndices())
    for ci,center in enumerate(('HEMO-A','HEMO-B','HEMO-C')):
        for gi,group in enumerate(BLOOD_TYPES[1:],1):
            for day in range(180):
                day_value=(date(anchor)-timedelta(days=180-day)).date().isoformat()
                identity=f'DEMO-V2-{center}-{group}-{day_value}'
                if list(iris.sql.exec('SELECT ExternalId FROM HemoFlow.ConsumptionDaily WHERE ExternalId=?',identity)):continue
                units=(1,4,2,3,1,2,1)[gi-1]+ci+(day%13)//5+int(day%7 in (1,2))
                iris.sql.exec("INSERT INTO HemoFlow.ConsumptionDaily (ExternalId,CenterId,BloodType,Day,UsedUnits,DemandUnmet) VALUES(?,?,?,TO_DATE(?,'YYYY-MM-DD'),?,?)",
                    identity,center,group,day_value,units,int(day in (60+gi,61+gi)))
    for gi,group in enumerate(BLOOD_TYPES):
        for sample in range(4):
            identity=f'DEMO-V2-CA-{gi}-{sample}'
            partner=repo.get('Partner','PARTNER-'+str(1+(gi+sample)%6))
            start=date(anchor)-timedelta(days=10+sample*15+gi)
            collected=18+gi+sample*2;released=collected-3;used=released-2
            row=save('Campaign',dict(id=identity,scope=partner['scope'],requesting_center_id=partner['scope'],partner_id=partner['id'],
                component='RED_BLOOD_CELLS',blood_type=group,status='COMPLETED',target_units=20,invited=70+gi,attended=30+gi,
                interested=12,collected=collected,released_usable=released,used_before_expiry=used,
                campaign_window_start=stamp(start),campaign_window_end=stamp(start+timedelta(hours=8)),
                expected_available_at=stamp(start+timedelta(days=2)),need_by=stamp(start+timedelta(days=5)),
                correlation_id=identity,synthetic_fixture=True),stamp(start))
            intelligence.record_campaign(dict(row,updated_at=stamp(start+timedelta(days=4))))
    for gi,group in enumerate(('A+','B+','AB-')):
        center=('HEMO-A','HEMO-B','HEMO-C')[gi];partner=repo.all('Partner',scope=center)[0]
        start=now()+timedelta(days=3+gi)
        identity='DEMO-V2-PLAN-'+str(gi)
        row=save('Campaign',dict(id=identity,scope=center,requesting_center_id=center,partner_id=partner['id'],
            component='RED_BLOOD_CELLS',blood_type=group,status='PENDING_CENTER_APPROVAL',target_units=16+gi*3,projected_deficit=16+gi*3,
            invited=0,interested=0,collected=0,released_usable=0,used_before_expiry=0,
            campaign_window_start=stamp(start),campaign_window_end=stamp(start+timedelta(hours=8)),
            expected_available_at=stamp(start+timedelta(days=2,hours=8)),need_by=stamp(start+timedelta(days=4)),
            correlation_id=identity,synthetic_fixture=True,similar_campaigns=intelligence.search('blood donation campaign red cells '+group+' shortage',partner['region'])),stamp())
        if not repo.get('WorkflowLink',identity,False):workflow.start(row,'gestor-'+center[-1].lower(),'Authorize synthetic '+group+' collection plan')
    model=intelligence.train()
    repo.put('SystemConfig',dict(id='history_repair_pending',value=False))
    run.update(version=2,model=model,upgraded_at=stamp(),backup=str(backup),
        counts=dict(centers=3,blood_types=8,history_days=180,consumption_rows=4320,experiences=72,users=13))
    repo.put('DemoRun',run)
    repo.audit('EventAudit',RUN,'DEMO_MULTITYPE_UPGRADED',user['id'],version=2,backup=str(backup))
    return dict(status='UPGRADED',version=2,counts=run['counts'])

def restore(user,scenario='TRANSFER'):
    guard(user);run=repo.get('DemoRun',RUN)
    require(run['status']=='READY','Seed incomplete',409)
    require(scenario in SCENARIOS,'Unknown scenario')
    for kind in ('Transfer','Campaign'):
        require(all(r.get('demo_run_id')==RUN for r in repo.all(kind)), 'Foreign workflow prevents demonstration restore',409)
    for center in repo.all('NetworkCenter'):
        status=federation.http(center['id'],'/demo/status',dict(run_id=RUN))
        require(status['seeded'] and status['safe_to_restore'],'Foreign institution data prevents restore',409)
    backup_dir=Path('/durable/hemoflow-demo-backups');backup_dir.mkdir(exist_ok=True)
    backup_id=uuid.uuid4().hex
    snapshot={k:[r for r in repo.all(k,limit=1000) if r.get('demo_run_id')==RUN] for k in ('Transfer','Campaign','InvitationLedger','PendingInvitation','DecisionContext')}
    with (backup_dir/(backup_id+'.json')).open('x') as out:json.dump(snapshot,out)
    # No audit/ledger deletion. Open synthetic plans are explicitly closed before resetting sources.
    for row in repo.all('Transfer'):
        if row['status'] in ('PROPOSED','PENDING_SOURCE_APPROVAL','APPROVED','REQUESTED','IN_TRANSIT'):
            workflow.timeout(row);row.update(status='FAILED',closure_reason='DEMO_RESTORE');repo.put('Transfer',row)
    for row in repo.all('Campaign'):
        if row['status'] in ('PROPOSED','PENDING_CENTER_APPROVAL','AWAITING_PARTNER','CONFIRMED'):
            workflow.timeout(row);row.update(status='CANCELLED',closure_reason='DEMO_RESTORE');repo.put('Campaign',row)
    for row in repo.all('InvitationLedger',state='PENDING'):
        if row.get('demo_run_id')==RUN:
            workflow.timeout(row);row.update(status='EXPIRED',closure_reason='DEMO_RESTORE');repo.put('InvitationLedger',row)
            if repo.get('PendingInvitation',row['id'],False):repo.delete('PendingInvitation',row['id'])
    repo.put('SystemConfig',dict(id='demo_clock_offset',value=0))
    anchor=stamp(now())
    backups={}
    for center_id,manifest in manifests(anchor,scenario).items():
        backups[center_id]=federation.http(center_id,'/demo/restore',dict(run_id=RUN,manifest=manifest))
    repo.audit('EventAudit',RUN,'DEMO_RESTORED',user['id'],scenario=scenario,backup=backup_id,remote_backups=backups,epoch=anchor)
    return dict(status='RESTORED',scenario=scenario,epoch=anchor,backup_id=backup_id)

def advance(user,hours):
    guard(user);run=repo.get('DemoRun',RUN)
    require(run['status']=='READY','Seed incomplete',409)
    require(type(hours) in (int,float) and 0<hours<=7*24,'Advance must be within seven days')
    previous=repo.config('demo_clock_offset',0);offset=previous+hours*3600
    require(offset<=30*86400,'Demo clock limited to 30 days; restore first')
    changed=[]
    try:
        for center in repo.all('NetworkCenter'):
            require(center.get('demo_run_id')==RUN,'Foreign center prevents clock simulation',409)
            federation.http(center['id'],'/demo/clock',dict(run_id=RUN,offset_seconds=offset));changed.append(center['id'])
        repo.put('SystemConfig',dict(id='demo_clock_offset',value=offset))
    except Exception:
        for center_id in changed:federation.http(center_id,'/demo/clock',dict(run_id=RUN,offset_seconds=previous))
        raise
    repo.audit('EventAudit',RUN,'DEMO_CLOCK_ADVANCED',user['id'],offset_seconds=offset,simulated_at=stamp())
    return dict(message='Demo clock advanced. Automatic expiry will check pending invitations.',simulated_at=stamp())
