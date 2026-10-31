"""Environment wins over .env. Never log secrets or return them to the browser."""
import os
from .common import ROOT

def setting(name,default=''):
    if name in os.environ: return os.environ[name]
    path=ROOT/'.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line: continue
            key,value=line.split('=',1)
            if key.strip()==name: return value.strip().strip('"').strip("'")
    return default

def demo(): return setting('HEMOFLOW_DEMO')=='1'
