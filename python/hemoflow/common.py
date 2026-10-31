import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENT, BLOOD = 'RED_BLOOD_CELLS', 'O-'
_clock_offset=None

def now():
    actual=datetime.now(timezone.utc)
    return actual+timedelta(seconds=float(_clock_offset())) if _clock_offset else actual

def set_clock(provider):
    global _clock_offset
    _clock_offset=provider

def enable_iris_demo_clock():
    from .settings import demo
    if demo():
        from . import repository
        set_clock(lambda:repository.config('demo_clock_offset',0))

def stamp(value=None):
    return (value or now()).astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')

def date(value):
    result = datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:
        raise Problem(422, 'UTC timestamp required')
    return result.astimezone(timezone.utc)

def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

class Problem(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)

def require(condition, message, status=422):
    if not condition:
        raise Problem(status, message)

def checked(status):
    if status != 1:
        import iris
        raise RuntimeError(iris.system.Status.GetErrorText(status))
