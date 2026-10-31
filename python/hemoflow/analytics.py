"""Read-only chart projections from IRIS and live federated FHIR observations.

No stock replica, fabricated ABO series, invented event timestamps or causal claims.
Chart payloads are presentation-only; workflow contracts remain unchanged.
"""
import json
import sys
import uuid
from collections import Counter, defaultdict
from datetime import timedelta
from .common import now, stamp, date, require, BLOOD
from .settings import demo
from . import repository as repo, federation, intelligence, policy
from .ui import t, label, display_name
from .products import BLOOD_TYPES,validate_product,matches
from .projections import simulate,proposed_receipts

def synthetic(row, demo_centers=()):
    return bool(row.get('demo_run_id') or row.get('synthetic') or row.get('synthetic_fixture')
                or str(row.get('id', '')).startswith('DEMO-')
                or str(row.get('correlation_id','')).startswith(('DEMO-','hemoflow-demo-'))
                or str(row.get('event','')).startswith('DEMO_')
                or row.get('scope') in demo_centers or row.get('center_id') in demo_centers)

def visible(rows, demo_centers=()):
    return rows if demo() else [r for r in rows if not synthetic(r, demo_centers)]

def chart(key, kind, source, unit='units', categories=None, series=None, note='', **extra):
    return dict(id=key, title=t('chart.'+key), kind=kind, source=source, unit=t('unit.'+unit),
                categories=categories or [], series=series or [], note=t(note) if note else '', **extra)

def build(page, user, selected='ALL', days=30, blood_type='O-'):
    import iris
    # Durable IRIS moves mgr; bulk PREDICT needs the installed AutoML serializers.
    if '/usr/irissys/mgr/python' not in sys.path: sys.path.append('/usr/irissys/mgr/python')
    require(page in ('panel','network','transfers','campaigns','audit'), 'Unknown analytics screen',404)
    require(user['role'] in ('admin','manager','auditor') or page=='campaigns', 'Analytics access denied',403)
    if page=='audit': require(user['role'] in ('admin','auditor'), 'Audit access denied',403)
    require(days in (7,30,90,180), 'Unsupported reporting period')
    if blood_type!='ALL':validate_product(blood_type)
    require(blood_type!='ALL' or page in ('campaigns','audit'),'Select one blood type')
    registry=repo.all('NetworkCenter')
    demo_ids={r['id'] for r in registry if synthetic(r)}
    centers=visible(registry)
    require(selected=='ALL' or selected in {c['id'] for c in centers}, 'Unknown blood center',422)
    # Match existing workflow scopes; only privileged network roles query stock.
    scope=None if user['role'] in ('admin','auditor') else user['scope']
    records={}
    for kind in ('Transfer','Campaign','DecisionAudit','InvitationLedger'):
        rows=visible(repo.all(kind,limit=1000),demo_ids)
        if scope:
            if kind=='Transfer': rows=[r for r in rows if scope in (r.get('source_center_id'),r.get('target_center_id'))]
            elif kind=='Campaign' and user['role'] in ('partner','donor'):
                ids={r['campaign_id'] for r in visible(repo.all('InvitationLedger',scope=scope),demo_ids)}
                rows=[r for r in rows if r['id'] in ids]
            else: rows=[r for r in rows if r.get('scope')==scope]
        if selected!='ALL':
            rows=[r for r in rows if selected in (r.get('scope'),r.get('center_id'),r.get('source_center_id'),r.get('target_center_id'),r.get('requesting_center_id'))]
        if kind!='InvitationLedger' and blood_type!='ALL':rows=[r for r in rows if matches(r,blood_type)]
        records[kind]=rows
    cutoff=stamp(now()-timedelta(days=days))
    end=stamp()
    network_centers=list(centers)
    centers=[c for c in centers if selected=='ALL' or c['id']==selected]
    live=[]; matrix=[]; forecasts={}; errors=[]
    if page in ('panel','network','transfers'):
        for center in network_centers:
            for group in BLOOD_TYPES:
                matrix.append(federation.inventory(center['id'],scope or center['id'],stamp(now()+timedelta(days=7)),str(uuid.uuid4()),group))
        for center in centers:
            live.append(next(r for r in matrix if r['center_id']==center['id'] and r['blood_type']==blood_type))
            if page in ('panel','transfers'):
                # A demo-trained model must not leak synthetic predictions into live mode.
                has_demo=bool(list(iris.sql.exec("SELECT TOP 1 ExternalId FROM HemoFlow.ConsumptionDaily WHERE ExternalId %STARTSWITH 'DEMO-'")))
                if not demo() and has_demo: forecasts[center['id']]={'method':'UNAVAILABLE'}
                else:
                    try: forecasts[center['id']]=intelligence.forecast(center['id'],blood_type)
                    except Exception: forecasts[center['id']]={'method':'UNAVAILABLE'}
    categories=[c['id'] for c in centers]
    live_by={r['center_id']:r for r in live}
    stock=[live_by.get(c,{}).get('available_units') if live_by.get(c,{}).get('status')=='AVAILABLE' else None for c in categories]
    predicted=[forecasts.get(c,{}).get('expected_units') if forecasts.get(c,{}).get('method')=='INTEGRATEDML' else None for c in categories]
    charts=[]
    if page=='panel':
        charts.append(chart('stock_forecast','bar','FHIR inventory + IRIS IntegratedML',categories=categories,
            series=[dict(name=t('confirmed_stock'),data=stock),dict(name=t('automl_forecast'),data=predicted,forecast=True)],note='note.forecast'))
        charts.append(chart('blood_distribution','bar','FHIR inventory · selected blood centers',categories=list(BLOOD_TYPES),
            series=[dict(name=t('confirmed_stock'),data=[sum(r['available_units'] for r in matrix if r['blood_type']==group and r['center_id'] in categories and r['status']=='AVAILABLE') if any(r['status']=='AVAILABLE' and r['blood_type']==group and r['center_id'] in categories for r in matrix) else None for group in BLOOD_TYPES])],note='note.blood_types'))
    if page in ('panel','transfers'):
        values=[]
        for low,high in ((0,3),(3,7),(7,100000)):
            values.append(sum(b['units'] for r in live if r['status']=='AVAILABLE' for b in r.get('expiry_buckets',[])
                if low<(date(b['expiresAt'])-now()).total_seconds()/86400<=high) if any(r['status']=='AVAILABLE' for r in live) else None)
        charts.append(chart('expiry_risk' if page=='panel' else 'expiry_distribution','bar','FHIR transferable expiry buckets',
            categories=[t('within_72h'),t('days_3_7'),t('after_7_days')],series=[dict(name=t('transferable_stock'),data=values)],note='note.expiry'))
    if page in ('panel','network'):
        matrix_centers=network_centers if page=='panel' else centers
        charts.append(chart('availability_heatmap','heatmap','Federated FHIR inventory',categories=categories,
            series=[dict(name=group,data=[next((r.get('available_units') for r in matrix if r['blood_type']==group and r['center_id']==c['id']),None) for c in matrix_centers]) for group in BLOOD_TYPES],note='note.missing'))
        charts[-1]['categories']=[c['id'] for c in matrix_centers]
        if page=='network':
            charts.append(chart('blood_comparison','bar','Federated FHIR inventory',categories=list(BLOOD_TYPES),
                series=[dict(name=c,data=[next((r.get('transferable_units') for r in matrix if r['center_id']==c and r['blood_type']==group),None) for group in BLOOD_TYPES]) for c in categories],note='note.comparison'))
    transfers=records['Transfer']; campaigns=records['Campaign']; decisions=records['DecisionAudit']
    if page=='transfers':
        before=[]; after=[]; names=[]
        for row in transfers:
            if row['status'] not in ('PENDING_SOURCE_APPROVAL','APPROVED','REQUESTED','IN_TRANSIT'): continue
            own=live_by.get(row['target_center_id']); forecast=forecasts.get(row['target_center_id'],{})
            deficit=policy.gap(forecast,own) if own and own['status']=='AVAILABLE' and forecast.get('method')=='INTEGRATEDML' else None
            names.append(row['id']); before.append(deficit)
            # Upper-bound quantity scenario; never presented as expiry-validated stock.
            source=next((r for r in matrix if r['center_id']==row['source_center_id'] and r['blood_type']==blood_type),None)
            receipts=proposed_receipts(row,source,forecast) if deficit is not None else []
            projected=simulate(own,forecast,receipts) if receipts else None
            after.append(projected['deficit'] if projected else None)
        charts.insert(0,chart('shortage_projection','bar','Live FHIR + IRIS forecast + open transfer requests',categories=names,
            series=[dict(name=t('before_transfer'),data=before,forecast=True),dict(name=t('hypothetical_after'),data=after,forecast=True)],note='note.hypothetical'))
        events=visible(repo.all('EventAudit',limit=1000),demo_ids)
        ids={r['id'] for r in transfers}; points=[]
        for row in transfers:
            if cutoff<=row['created_at']<=end: points.append(dict(name=row['id'],at=row['created_at'],status=t('created')))
        for event in events:
            if event.get('entity_id') in ids and event.get('event')=='TRANSFER_TRANSITION' and cutoff<=event['created_at']<=end:
                points.append(dict(name=event['entity_id'],at=event['created_at'],status=label(event['current'])))
        charts.append(chart('transfer_timeline','timeline','IRIS Transfer + EventAudit','events',points=points,note='note.timeline'))
    if page=='campaigns':
        partners={r['id']:r for r in visible(repo.all('Partner'))}
        experience=[]
        for identity,partner,metrics in iris.sql.exec('SELECT ExternalId,PartnerId,Metrics FROM HemoFlow.CampaignExperience'):
            item=json.loads(metrics)
            if blood_type!='ALL' and item.get('blood_type','O-')!=blood_type:continue
            if not demo() and (str(identity).startswith('DEMO-') or item.get('synthetic')):continue
            p=partners.get(partner)
            if not p or (selected!='ALL' and p['scope']!=selected): continue
            if user['role']=='manager' and p['scope']!=scope:continue
            if user['role']=='partner' and partner!=scope:continue
            if user['role']=='donor':continue
            if cutoff[:10]<=item.get('period','')<=end[:10]:experience.append(dict(item,id=identity))
        stages=['invited','attended','collected','released_usable','used_before_expiry']
        cohort=[r for r in experience if all(r.get(k) is not None for k in stages)]
        charts.append(chart('donation_funnel','funnel','IRIS CampaignExperience · matched historical cohort','stage_counts',
            categories=[t('stage.'+k) for k in stages],series=[dict(name=t('historical_cohort'),data=[sum(r[k] for r in cohort) for k in stages] if cohort else [])],note='note.funnel'))
        charts.append(chart('campaign_outcomes','bar','IRIS CampaignExperience',categories=[r['id'] for r in experience],
            series=[dict(name=t('stage.'+k),data=[r.get(k,0) for r in experience]) for k in stages[2:]],note='note.outcomes'))
        points=[]
        for row in campaigns:
            if row.get('campaign_window_end','')<cutoff or row.get('campaign_window_start','')>stamp(now()+timedelta(days=days)):continue
            for key in ('campaign_window_start','campaign_window_end','expected_available_at'):
                if row.get(key):points.append(dict(name=row['id'],at=row[key],status=t('schedule.'+key)))
        charts.append(chart('campaign_schedule','timeline','IRIS Campaign planned windows','milestones',points=points,note='note.schedule'))
    if page=='audit':
        allowed={c['id'] for c in centers}
        if not demo():allowed-=demo_ids
        has_demo=bool(list(iris.sql.exec("SELECT TOP 1 ExternalId FROM HemoFlow.ConsumptionDaily WHERE ExternalId %STARTSWITH 'DEMO-'")))
        validation=[]
        if demo() or not has_demo:
            try:
                # EAP 154 bulk PREDICT produces INVALID OREF after class reload.
                # Use the same parameterized native PREDICT path as live inference.
                result=iris.sql.exec("SELECT TO_CHAR(Day,'YYYY-MM-DD'),CenterId,Target7d,Avg7,Avg28,DayOfWeek,MonthNumber FROM HemoFlow.DemandFeature WHERE Split='VALIDATION'"+(" AND COALESCE(BloodType,'O-')=?" if blood_type!='ALL' else ''),*([blood_type] if blood_type!='ALL' else []))
                model=repo.config('forecast_model',{});predictions={}
                for day,center,actual,avg7,avg28,dow,month in result:
                    if center in allowed and cutoff[:10]<=str(day)<=end[:10]:
                        features=(avg7,avg28,dow,month)
                        if features not in predictions:predictions[features]=intelligence.predict_features(model,*features)
                        prediction=predictions[features]
                        validation.append((str(day),center,float(actual),float(prediction)))
                validation.sort()
            except Exception: errors.append('actual_predicted')
        totals=defaultdict(lambda:[0,0])
        for day,center,actual,prediction in validation:
            totals[day][0]+=actual;totals[day][1]+=prediction
        validation_days=sorted(totals)
        charts.append(chart('actual_predicted','line','IRIS DemandFeature validation + native PREDICT',categories=validation_days,
            series=[dict(name=t('actual_consumption'),data=[totals[d][0] for d in validation_days]),dict(name=t('automl_prediction'),data=[totals[d][1] for d in validation_days],forecast=True)],note='note.validation'))
        selected_decisions=[r for r in decisions if cutoff<=r['created_at']<=end]
        counts=Counter((r.get('decision') or {}).get('decision',r['status']) for r in selected_decisions)
        charts.append(chart('decision_distribution','donut','IRIS DecisionAudit','decisions',categories=[label(k) for k in counts],
            series=[dict(name=t('decisions'),data=list(counts.values()))],note='note.decisions'))
        daily=defaultdict(lambda:[0,0,0])
        for row in selected_decisions:
            day=row['created_at'][:10]; daily[day][0]+=1
            daily[day][1]+=int(row['status'] in ('ESCALATED','INVALID_OUTPUT'))
        for row in visible(repo.all('EventAudit',limit=1000),demo_ids):
            if cutoff<=row['created_at']<=end and row.get('event')=='TRANSFER_TRANSITION' and row.get('current')=='DELIVERED' and row.get('entity_id') in {r['id'] for r in transfers}:
                daily[row['created_at'][:10]][2]+=1
        dates=sorted(daily)
        charts.append(chart('operational_trends','line','IRIS DecisionAudit + delivery transition events','events',categories=dates,
            series=[dict(name=t(key),data=[daily[d][i] for d in dates]) for i,key in enumerate(('decisions','review_required','delivered_transfers'))],note='note.trends'))
    summary=[]; actions=[]; projections=[]
    if page=='panel':
        projections=[simulate(live_by[c],forecasts.get(c,{})) for c in categories]
        complete=bool(live) and all(r['status']=='AVAILABLE' for r in live)
        predicted_complete=bool(predicted) and all(v is not None for v in predicted)
        deficits=[p['deficit'] for p in projections if p]
        summary=[dict(label=t('kpi.usable'),value=sum(stock) if complete else None,unit=t('unit.units')),
            dict(label=t('kpi.forecast'),value=sum(predicted) if predicted_complete else None,unit=t('unit.units')),
            dict(label=t('kpi.deficit'),value=sum(deficits) if len(deficits)==len(categories) and deficits else None,unit=t('unit.units')),
            dict(label=t('kpi.expiry'),value=sum(b['units'] for r in live if r['status']=='AVAILABLE' for b in r.get('usable_buckets',r['expiry_buckets']) if now()<date(b['expiresAt'])<=now()+timedelta(days=3)) if complete else None,unit=t('unit.units')),
            dict(label=t('kpi.sources'),value=str(sum(all(r['status']=='AVAILABLE' for r in matrix if r['center_id']==c['id']) for c in network_centers))+'/'+str(len(network_centers)),unit=t('centers_reached'))]
        valid=bool(projections) and all(projections)
        charts.insert(1,chart('supply_projection','line','FHIR usable expiry buckets + IntegratedML seven-day total',categories=projections[0]['days'] if valid else [],
            series=[dict(name=t('projected_stock'),data=[sum(p['stock'][i] for p in projections) for i in range(7)] if valid else [],forecast=True),dict(name=t('daily_shortfall'),data=[sum(p['unmet'][i] for p in projections) for i in range(7)] if valid else [],forecast=True)],note='note.projection'))
        for kind,rows in (('transfers',transfers),('campaigns',campaigns)):
            for row in rows:
                if row['status'] in ('DELIVERED','COMPLETED','CANCELLED','DECLINED','FAILED'):continue
                actions.append(dict(kind=kind,id=row['id'],status=label(row['status']),blood_type=row.get('blood_type','O-'),center=row.get('target_center_id',row.get('scope')),
                    due=row.get('need_by'),expected=row.get('expected_available_at'),units=row.get('requested_units',row.get('target_units')),confirmed_stock=False))
    for item in charts:
        item.update(updated_at=end,period=dict(start=cutoff,end=end),demo=demo())
        if item['id'] in ('stock_forecast','shortage_projection','supply_projection'):
            item['period']=dict(start=end,end=stamp(now()+timedelta(days=7)))
        elif item['id'] in ('blood_distribution','expiry_risk','availability_heatmap','blood_comparison','expiry_distribution'):
            item['period']=dict(start=end,end=end)
        elif item['id']=='campaign_schedule':
            item['period']['end']=stamp(now()+timedelta(days=days))
        if live: item['observations']=[dict(center_id=r['center_id'],status=r['status'],observed_at=r['observed_at']) for r in live]
        if item['id'] in errors:item['error']=t('chart_error')
    return dict(charts=charts,summary=summary,actions=actions[:30],blood_type=blood_type,observations=matrix,centers=[dict(id=c['id'],name=display_name(c['name'])) for c in centers],
        unavailable=[r['center_id'] for r in live if r['status']!='AVAILABLE'],demo=demo(),updated_at=end,
        period=dict(start=cutoff,end=end),coverage=t('note.coverage'),limit=1000)
