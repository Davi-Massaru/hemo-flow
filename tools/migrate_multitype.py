"""Resumable demo upgrade; backups and ownership checks are in demo.upgrade."""
import json,traceback
from pathlib import Path
from hemoflow import demo,repository
try:
    result=demo.install(repository.get('User','admin'))
    Path('/durable/hemoflow-evidence/multitype-migration.json').write_text(json.dumps(result))
    print('MULTITYPE_MIGRATION',json.dumps(result))
except Exception:
    Path('/durable/hemoflow-evidence/multitype-migration-error.txt').write_text(traceback.format_exc())
    print('MULTITYPE_MIGRATION_FAILED')
