import json, urllib.request, urllib.error
from . import repository as repo
from .common import dumps, require, Problem, stamp
from .settings import setting, demo
from .fhir import availability_input, parse_availability

def call(target,payload):
    import iris, uuid
    payload.setdefault('correlation_id',str(uuid.uuid4()))
    return json.loads(iris.cls('HemoFlow.Runtime').Submit(dumps(payload),target))

def center(identity): return repo.get('NetworkCenter',identity)

def exchange(identity,path,body,headers=None):
    result=call('FHIRTransferOperation',dict(center_id=identity,path=path,body=body,headers=headers or {}))
    if not result.get('ok'):raise Problem(result.get('status',503),result.get('error','FHIR operation unavailable'))
    return result['result']

def http(identity,path,payload,headers=None):
    registered=center(identity)
    endpoint=registered['endpoint'].rstrip('/')+path
    require(endpoint.startswith('https://') or (demo() and endpoint.startswith('http://')),'TLS required')
    auth=setting('HEMOFLOW_CENTER_TOKEN')
    require(auth,'Center credential missing',503)
    req=urllib.request.Request(endpoint,dumps(payload).encode(),headers={
        'Authorization':'Bearer '+auth,'Content-Type':'application/fhir+json',
        **({'X-Demo-Run':registered['demo_run_id']} if registered.get('demo_run_id') else {}),**(headers or {})},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=6) as response:
            raw=response.read(65537)
            require(len(raw)<=65536,'Remote response too large',503)
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise Problem(409 if exc.code==409 else 503,'Remote institution rejected or unavailable') from exc
    except (OSError,ValueError) as exc:
        raise Problem(503,'Remote institution unavailable') from exc

def inventory(identity,requester,need_by,correlation,blood_type='O-'):
    registered=center(identity)
    try:
        response=call('FederatedInventoryOperation',dict(endpoint=registered['endpoint'].rstrip('/')+'/fhir/$inventory-availability',
            body=availability_input(requester,need_by,blood_type),correlation_id=correlation))
        return parse_availability(response,identity,blood_type)
    except Exception:
        # Keep missing data missing. Never fabricate an empty stock.
        return dict(center_id=identity,blood_type=blood_type,status='UNAVAILABLE',observed_at=stamp())
