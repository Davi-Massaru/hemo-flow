"""English presentation resources. Never translate persisted IDs or API values."""
import json
from .common import ROOT

STRINGS = json.loads((ROOT / 'web/static/locales/en.json').read_text(encoding='utf-8'))

def t(key, **values):
    return STRINGS.get(key, key).format(**values) if values else STRINGS.get(key, key)

def label(value):
    return STRINGS.get('status.' + str(value), STRINGS.get('legacy.' + str(value), value))

def display_name(value):
    return STRINGS.get('demo.' + str(value), value)
