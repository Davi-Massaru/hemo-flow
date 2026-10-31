import sys,json
sys.path.insert(0,'/opt/hemoflow/python')
import iris
from hemoflow import repository as repo
key='f2c10268-80ee-4eb7-ba93-eb9eb91f4e08'
rows=repo.all('EventAudit',correlation=key)
print('CORRELATED',[(r.get('event'),r.get('tool'),r.get('request_id')) for r in rows])
for r in repo.all('EventAudit',limit=1000):
 if r.get('event')=='AI_TOOL' and (r.get('request_id')==key or r.get('correlation_id')==key): print('TOOL',r)
print('CONTEXT',repo.get('DecisionContext',key,False) is not None)
