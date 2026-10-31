import sys, json, traceback
sys.path.insert(0,'/opt/hemoflow/python')
import iris
report={}
queries={
 'hosts':'SELECT TOP 12 * FROM Ens_Util.Log ORDER BY ID DESC',
 'workflow_columns':"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='EnsLib_Workflow' AND TABLE_NAME='TaskResponse'",
 'ml_models':'SELECT * FROM INFORMATION_SCHEMA.ML_MODELS',
 'vector':"SELECT VECTOR_COSINE(TO_VECTOR('1,0',DOUBLE),TO_VECTOR('1,0',DOUBLE))",
 'ttl_classes':"SELECT Name FROM %Dictionary.ClassDefinition WHERE Super='HemoFlow.Expirable'",
}
for name,query in queries.items():
    try: report[name]=[list(row) for row in iris.sql.exec(query)]
    except Exception as exc: report[name]=str(exc)
print(json.dumps(report,default=str,indent=2))
from hemoflow.provision import install
try: install(); print('PROVISION_OK')
except Exception as exc: print('PROVISION_ERROR',str(exc))
try:
    from hemoflow import federation
    from hemoflow.fhir import availability_input
    from hemoflow.common import stamp,now
    from datetime import timedelta
    body=availability_input('HEMO-A',stamp(now()+timedelta(days=7)))
    print('PEX_RESULT', federation.call('FederatedInventoryOperation',dict(endpoint='http://center-b:8080/fhir/$inventory-availability',body=body)))
except Exception as exc: print('PEX_ERROR',str(exc))
