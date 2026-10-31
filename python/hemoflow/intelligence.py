import json, time, math, hashlib
from datetime import timedelta
import iris
from . import repository as repo
from .common import dumps, date, now, stamp, require, ROOT, Problem, checked
from .settings import setting
from . import federation, policy
from .products import validate_product, matches
import sys
if '/usr/irissys/mgr/python' not in sys.path: sys.path.append('/usr/irissys/mgr/python')

EMBEDDING_DIM=384
_encoder=None

def embedding(text):
    global _encoder
    if _encoder is None:
        from fastembed import TextEmbedding
        _encoder=TextEmbedding(model_name=setting('HEMOFLOW_EMBEDDING_MODEL','BAAI/bge-small-en-v1.5'),
                              cache_dir='/durable/embeddings',threads=2)
    vector=list(next(_encoder.embed([text])))
    require(len(vector)==EMBEDDING_DIM,'Embedding dimension mismatch')
    return ','.join(str(float(v)) for v in vector)

def search(text,region,partner_type=None,k=5):
    start=time.monotonic()
    vector=embedding(text)
    sql='''SELECT TOP 5 ExternalId, PartnerId, Summary, ReleasedUsable,
        VECTOR_COSINE(Embedding,TO_VECTOR(?,DOUBLE)) AS Score
        FROM HemoFlow.CampaignExperience WHERE Region=? AND EmbeddingModel=?'''
    args=[vector,region,setting('HEMOFLOW_EMBEDDING_MODEL','BAAI/bge-small-en-v1.5')]
    if partner_type: sql+=' AND PartnerType=?'; args.append(partner_type)
    sql+=' ORDER BY Score DESC, ExternalId'
    rows=[dict(campaign_id=r[0],partner_id=r[1],summary=r[2],released_usable=r[3],score=float(r[4])) for r in iris.sql.exec(sql,*args)]
    for row in rows:
        metrics=list(iris.sql.exec('SELECT Metrics FROM HemoFlow.CampaignExperience WHERE ExternalId=?',row['campaign_id']))
        row['metrics']=json.loads(metrics[0][0] or '{}') if metrics else {}
    return dict(results=rows[:min(k,5)],model=setting('HEMOFLOW_EMBEDDING_MODEL','BAAI/bge-small-en-v1.5'),
                dimension=EMBEDDING_DIM,latency_ms=round((time.monotonic()-start)*1000))

def predict_features(model,avg7,avg28,dow,month):
    model_name=model.get('model_name','Demand7d')
    require(model_name in ('Demand7d','Demand7dMulti'),'Unknown model')
    values=list(iris.sql.exec(f'''SELECT PREDICT({model_name}) AS Prediction FROM
        (SELECT CAST(? AS DOUBLE) AS Avg7,CAST(? AS DOUBLE) AS Avg28,
          CAST(? AS INTEGER) AS DayOfWeek,CAST(? AS INTEGER) AS MonthNumber)''',avg7,avg28,dow,month))
    return float(values[0][0])

def forecast(center_id,blood_type='O-'):
    validate_product(blood_type)
    model=repo.config('forecast_model')
    if not model:
        return dict(expected_units=0,method='UNAVAILABLE',quality_flags=['model_unavailable'],model_version=None)
    rows=list(iris.sql.exec('''SELECT UsedUnits,DemandUnmet FROM HemoFlow.ConsumptionDaily
        WHERE CenterId=? AND COALESCE(BloodType,'O-')=? ORDER BY Day DESC''',center_id,blood_type))
    require(len(rows)>=28,'Insufficient historical coverage',503)
    avg7=sum(r[0] for r in rows[:7])/7
    avg28=sum(r[0] for r in rows[:28])/28
    dow=now().weekday(); month=now().month
    try:
        expected=max(0,int(math.ceil(predict_features(model,avg7,avg28,dow,month))))
        return dict(expected_units=expected,method='INTEGRATEDML',model_version=model['version'],
                    horizon_days=7,forecast_as_of=stamp(),quality_flags=['stockout_affected'] if any(r[1] for r in rows[:28]) else [],
                    mae=model['mae'],baseline_mae=model['baseline_mae'])
    except Exception:
        return dict(expected_units=math.ceil(avg7*7),method='BASELINE',model_version=None,
                    horizon_days=7,forecast_as_of=stamp(),quality_flags=['automl_unavailable'])

def train():
    # Latest labels stop seven days before inference; chronological holdout, no future leakage.
    rows=list(iris.sql.exec("SELECT CenterId,TO_CHAR(Day,'YYYY-MM-DD'),UsedUnits,DemandUnmet,COALESCE(BloodType,'O-') FROM HemoFlow.ConsumptionDaily ORDER BY CenterId,BloodType,Day"))
    centers={(r[0],r[4]) for r in rows}
    if list(iris.sql.exec('SELECT COUNT(*) FROM HemoFlow.DemandFeature'))[0][0]:
        iris.sql.exec('DELETE FROM HemoFlow.DemandFeature')
    for center_id,blood_type in centers:
        daily=[r for r in rows if r[0]==center_id and r[4]==blood_type]
        for i in range(28,len(daily)-7):
            if len(daily)-42<=i<len(daily)-35:continue # seven-day embargo between overlapping labels
            window=daily[i-28:i]; future=daily[i:i+7]
            # Censored labels are excluded instead of being called true demand.
            if any(r[3] for r in window+future): continue
            day=date(str(daily[i][1])+'T00:00:00Z')
            iris.sql.exec('''INSERT INTO HemoFlow.DemandFeature
                (CenterId,Day,Avg7,Avg28,DayOfWeek,MonthNumber,Target7d,Split,BloodType)
                VALUES(?,TO_DATE(?,'YYYY-MM-DD'),?,?,?,?,?,?,?)''',center_id,str(daily[i][1]),sum(r[2] for r in window[-7:])/7,
                sum(r[2] for r in window)/28,day.weekday(),day.month,sum(r[2] for r in future),
                'TRAIN' if i<len(daily)-35 else 'VALIDATION',blood_type)
    exists=list(iris.sql.exec("SELECT MODEL_NAME FROM INFORMATION_SCHEMA.ML_MODELS WHERE MODEL_NAME='Demand7dMulti'"))
    if not exists:
        iris.sql.exec('''CREATE MODEL Demand7dMulti PREDICTING (Target7d DOUBLE) WITH
            (Avg7 DOUBLE,Avg28 DOUBLE,DayOfWeek INTEGER,MonthNumber INTEGER)
            FROM HemoFlow.DemandFeature''')
    iris.sql.exec("TRAIN MODEL Demand7dMulti FROM HemoFlow.DemandFeature WHERE Split='TRAIN' USING {\"seed\":42}")
    iris.sql.exec("VALIDATE MODEL Demand7dMulti FROM HemoFlow.DemandFeature WHERE Split='VALIDATION'")
    evaluations=list(iris.sql.exec("SELECT Target7d,PREDICT(Demand7dMulti),Avg7*7 FROM HemoFlow.DemandFeature WHERE Split='VALIDATION'"))
    require(evaluations,'Empty validation set')
    record=dict(version=stamp(),model_name='Demand7dMulti',provider='%AutoML',mae=sum(abs(r[0]-r[1]) for r in evaluations)/len(evaluations),
                baseline_mae=sum(abs(r[0]-r[2]) for r in evaluations)/len(evaluations),validation_rows=len(evaluations))
    repo.put('SystemConfig',dict(id='forecast_model',value=record))
    return record

TOOL_NAMES=('forecast_demand','query_network_inventory','search_campaign_experience','list_campaign_partners','get_active_campaigns')

def record_campaign(row):
    """Index completed outcomes idempotently; no invented attendance or yield."""
    require(row['status']=='COMPLETED','Only completed campaigns can be indexed')
    if list(iris.sql.exec('SELECT ExternalId FROM HemoFlow.CampaignExperience WHERE ExternalId=?',row['id'])):return
    partner=repo.get('Partner',row['partner_id'])
    group=row.get('blood_type','O-')
    summary=f"{partner['type']} blood donation campaign for {group} red blood cells in {partner['region']}: {row['released_usable']} units released and {row['used_before_expiry']} used before expiry."
    metrics={k:row.get(k) for k in ('invited','attended','collected','released_usable','used_before_expiry')}
    metrics.update(period=row.get('updated_at',stamp())[:10],blood_type=group,synthetic=bool(row.get('demo_run_id')))
    iris.sql.exec('''INSERT INTO HemoFlow.CampaignExperience
        (ExternalId,PartnerId,PartnerType,Region,Summary,ReleasedUsable,Metrics,Embedding,EmbeddingModel,ContentHash)
        VALUES(?,?,?,?,?,?,?,TO_VECTOR(?,DOUBLE),?,?)''',row['id'],partner['id'],partner['type'],partner['region'],summary,
        row['released_usable'],dumps(metrics),embedding(summary),setting('HEMOFLOW_EMBEDDING_MODEL','BAAI/bge-small-en-v1.5'),hashlib.sha256(summary.encode()).hexdigest())

def read_tool(name,request_id,phase='PREFETCH'):
    runtime=iris.cls('HemoFlow.Runtime')
    require(runtime.Lock('evidence:'+request_id),'Evidence busy',409)
    try:return _read_tool(name,request_id,phase)
    finally:runtime.Unlock('evidence:'+request_id)

def _read_tool(name,request_id,phase):
    require(name in TOOL_NAMES,'Tool not allowed',403)
    c=repo.get('DecisionContext',request_id)
    require(date(c['expires_at'])>now(),'Expired tool context',409)
    require(time.time()<c.get('deadline_epoch',float('inf')),'Decision deadline expired',409)
    require(c.get('tool_count',0)<15,'Tool budget exhausted',409)
    start=time.monotonic()
    if name=='forecast_demand': result=forecast(c['center_id'],c.get('blood_type','O-'))
    elif name=='query_network_inventory':
        result=[federation.inventory(row['id'],c['center_id'],c['need_by'],c['correlation_id'],c.get('blood_type','O-')) for row in repo.all('NetworkCenter') if row['id'] in c.get('allowed_centers',[r['id'] for r in repo.all('NetworkCenter')])]
    elif name=='search_campaign_experience': result=search('blood donation campaign red blood cells '+c.get('blood_type','O-')+' shortage',c['region'])
    elif name=='list_campaign_partners': result=[r for r in repo.all('Partner',scope=c['center_id']) if r['region']==c['region']]
    else: result=[r for r in repo.all('Campaign',scope=c['center_id']) if r['status']=='CONFIRMED' and matches(r,c.get('blood_type','O-'))]
    fields={'forecast_demand':'forecast','query_network_inventory':'network','search_campaign_experience':'similar_campaigns',
            'list_campaign_partners':'partners','get_active_campaigns':'active_campaigns'}
    latest=repo.get('DecisionContext',request_id)
    latest[fields[name]]=result
    if name=='query_network_inventory':
        observed=latest.setdefault('inventory_observations',{})
        for row in result:
            if row['status']=='AVAILABLE':
                values=observed.setdefault(row['center_id'],[])
                if row['observed_at'] not in values:values.append(row['observed_at'])
    if phase=='AGENT':
        latest['tool_count']=latest.get('tool_count',0)+1
        latest['evidence_version']=latest.get('evidence_version',0)+1
        evidence='TOOL:'+request_id+':'+name+':'+str(latest['evidence_version'])
        latest.setdefault('observations',{})[name]=dict(evidence_id=evidence,observed_at=stamp(),result_hash=hashlib.sha256(dumps(result).encode()).hexdigest())
        latest['evidence_ids']=[v['evidence_id'] for v in latest['observations'].values()]
    else:evidence='TOOL:'+request_id+':'+name
    repo.put('DecisionContext',latest)
    repo.audit('EventAudit',c['correlation_id'],'AI_TOOL' if phase=='AGENT' else 'TOOL_PREFETCH',tool=name,request_id=request_id,
               evidence_id=evidence,latency_ms=round((time.monotonic()-start)*1000))
    return dumps(dict(result=result,evidence_id=evidence,evidence_version=latest.get('evidence_version',0))) if phase=='AGENT' else dumps(result)

def prepare(c):
    c['forecast']=json.loads(read_tool('forecast_demand',c['id']))
    c['network']=json.loads(read_tool('query_network_inventory',c['id']))
    c['partners']=json.loads(read_tool('list_campaign_partners',c['id']))
    c['active_campaigns']=json.loads(read_tool('get_active_campaigns',c['id']))
    c['similar_campaigns']=json.loads(read_tool('search_campaign_experience',c['id']))
    c['evidence_ids']=['TOOL:'+c['id']+':'+name for name in TOOL_NAMES]
    # Inventory API's own expiry buckets distinguish usable and transferable quantities.
    c['confirmed_receipts']=[]
    c['inventory_observations']={r['center_id']:[r['observed_at']] for r in c['network'] if r['status']=='AVAILABLE'}
    repo.put('DecisionContext',c)
    return c

def finalize_agent(raw,identity):
    result=json.loads(raw)
    called={r.get('tool') for r in repo.all('EventAudit',correlation=identity) if r.get('request_id')==identity and r.get('event')=='AI_TOOL'}
    require(set(TOOL_NAMES)<=called,'Agent skipped required evidence tools',503)
    result.update(provider='openai',tools_called=sorted(called),evidence_version=repo.get('DecisionContext',identity)['catalog']['evidence_version'])
    input_price=setting('HEMOFLOW_INPUT_USD_PER_MILLION');output_price=setting('HEMOFLOW_OUTPUT_USD_PER_MILLION')
    usage=result.get('usage') or {};stats=result.get('stats') or {}
    incoming=stats.get('total_prompt_tokens',usage.get('prompt_tokens',usage.get('input_tokens')))
    outgoing=stats.get('total_completion_tokens',usage.get('completion_tokens',usage.get('output_tokens')))
    result['estimated_usd']=None
    if input_price and output_price and incoming is not None and outgoing is not None:
        result['estimated_usd']=(incoming*float(input_price)+outgoing*float(output_price))/1_000_000
    return dumps(result)


def catalog(identity):
    c=repo.get('DecisionContext',identity)
    require(time.time()<c['deadline_epoch'],'Decision deadline expired',409)
    require(set(TOOL_NAMES)<=set(c['observations']),'Missing required tools',503)
    allowed=policy.candidates(c)
    require(allowed,'No safe decision: data quality, stock or timing requires operational review',409)
    c['catalog']=dict(candidates=allowed,evidence_version=c['evidence_version'])
    repo.put('DecisionContext',c)
    return dumps(dict(requestId=identity,json_schema=policy.SCHEMA,**c['catalog']))
