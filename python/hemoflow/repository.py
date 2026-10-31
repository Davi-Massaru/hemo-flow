"""One IRIS persistent class per entity. Remote inventories never enter this store."""
import uuid
import iris
from .common import dumps, stamp, Problem, checked

ENTITIES = {'NetworkCenter','Partner','DonorContact','Transfer','Campaign',
            'InvitationLedger','DecisionAudit','EventAudit','SystemConfig','User',
            'Command','DemoRun','Outbox','WorkflowLink','PendingInvitation','DecisionContext'}

def table(kind):
    if kind not in ENTITIES:
        raise ValueError('Unknown entity')
    return 'HemoFlow."' + kind + '"'

def get(kind, key, required=True):
    import json
    rows = list(iris.sql.exec('SELECT Payload FROM '+table(kind)+' WHERE ExternalId=?', key))
    if not rows:
        if required: raise Problem(404, kind+' not found')
        return None
    return json.loads(rows[0][0])

def all(kind, scope=None, state=None, limit=500, correlation=None):
    import json
    sql = 'SELECT TOP '+str(min(int(limit),1000))+' Payload FROM '+table(kind)
    filters, args = [], []
    if scope is not None: filters.append('Scope=?'); args.append(scope)
    if state is not None: filters.append('State=?'); args.append(state)
    if correlation is not None: filters.append('CorrelationId=?'); args.append(correlation)
    if filters: sql += ' WHERE '+' AND '.join(filters)
    sql += ' ORDER BY CreatedAt DESC, ExternalId'
    return [json.loads(row[0]) for row in iris.sql.exec(sql,*args)]

def put(kind, value, create=False):
    key = value.setdefault('id', str(uuid.uuid4()))
    old = get(kind,key,False)
    if create and old:
        raise Problem(409,'Duplicate '+kind)
    obj = iris.cls('HemoFlow.'+kind)._OpenId(key) if old else iris.cls('HemoFlow.'+kind)._New()
    value.setdefault('created_at', stamp())
    value['updated_at'] = stamp()
    obj.ExternalId, obj.Payload = key, dumps(value)
    obj.Scope, obj.State = value.get('scope',''), value.get('status','')
    obj.CorrelationId = value.get('correlation_id','')
    obj.CreatedAt = value['created_at']
    if kind in ('PendingInvitation','DecisionContext'):
        obj.ExpiresAt = value['expires_at']
    checked(obj._Save())
    return value

def delete(kind,key):
    checked(iris.cls('HemoFlow.'+kind)._DeleteId(key))

def audit(kind, correlation, event, actor='system', **data):
    return put(kind,dict(id=str(uuid.uuid4()),correlation_id=correlation,
                         event=event,actor_id=actor,**data),create=True)

def config(key, default=None):
    row = get('SystemConfig',key,False)
    return row['value'] if row else default
