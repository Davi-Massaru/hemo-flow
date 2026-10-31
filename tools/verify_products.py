"""Read-only validation of seeded product histories and real AutoML inference."""
import sys,json,pathlib
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow import intelligence,repository as repo,demo
from hemoflow.products import BLOOD_TYPES
from hemoflow.common import enable_iris_demo_clock
enable_iris_demo_clock()
results=[]
for center in repo.all('NetworkCenter'):
    for group in BLOOD_TYPES:
        try:
            result=intelligence.forecast(center['id'],group)
            results.append(dict(center=center['id'],blood_type=group,**result))
        except Exception as error:
            results.append(dict(center=center['id'],blood_type=group,error=str(error)))
evidence=pathlib.Path('/durable/hemoflow-evidence');evidence.mkdir(exist_ok=True)
(evidence/'product-forecasts.json').write_text(json.dumps(results,indent=2))
print('PRODUCT_FORECASTS',json.dumps(results))
assert len(results)==24 and all(r.get('method')=='INTEGRATEDML' for r in results)
assert demo.install(repo.get('User','admin'))['status']=='ALREADY_LOADED'
print('PRODUCT_FORECASTS_AND_SEED_IDEMPOTENCY_OK')
