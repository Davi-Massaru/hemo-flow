"""Preserve every application entity before initial storage correction. No delete."""
import sys,json,pathlib,hashlib
sys.path.insert(0,'/opt/hemoflow/python')
from hemoflow import repository as repo
path=pathlib.Path('/durable/hemoflow-before-storage.json')
if path.exists():
    print('SNAPSHOT_ALREADY_PRESENT',hashlib.sha256(path.read_bytes()).hexdigest())
else:
    records={kind:repo.all(kind,limit=1000) for kind in sorted(repo.ENTITIES)}
    with path.open('x') as output: json.dump(records,output,ensure_ascii=False)
    path.chmod(0o600)
    print('SNAPSHOT_SAVED', {kind:len(rows) for kind,rows in records.items()},hashlib.sha256(path.read_bytes()).hexdigest())
