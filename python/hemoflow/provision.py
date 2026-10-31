from werkzeug.security import generate_password_hash
from . import repository as repo
from .settings import setting
from .common import require, checked
import iris

def install():
    from pathlib import Path
    Path('/durable/hemoflow-evidence').mkdir(exist_ok=True)
    # AutoML resolves plugins relative to the active mgr, while durable-sys leaves
    # wheel files in the image. Link only when absent; preserve existing installs.
    source=Path('/usr/irissys/mgr/python/iris_automl')
    target=Path(iris.system.Util.ManagerDirectory())/'python'/'iris_automl'
    if source.exists() and not target.exists():
        target.parent.mkdir(parents=True,exist_ok=True)
        target.symlink_to(source,target_is_directory=True)
    if not repo.get('User','admin',False):
        password=setting('HEMOFLOW_ADMIN_PASSWORD')
        require(len(password)>=16,'Set HEMOFLOW_ADMIN_PASSWORD with at least 16 characters')
        repo.put('User',dict(id='admin',scope='NETWORK',role='admin',name='Administrator',
                            password_hash=generate_password_hash(password)),create=True)
    if repo.config('invite_ttl_hours') is None:
        repo.put('SystemConfig',dict(id='invite_ttl_hours',value=24))
    # Auto-start only the single HemoFlow production.
    checked(iris.cls('Ens.Director').SetAutoStart('HemoFlow.Production'))
