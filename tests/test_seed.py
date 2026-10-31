from datetime import timedelta
import pytest
from werkzeug.security import check_password_hash
from hemoflow import demo
from hemoflow.common import Problem,dumps

def test_seed_manifest_and_demo_password_are_reproducible():
    anchor='2026-10-29T00:00:00Z'
    assert dumps(demo.manifests(anchor))==dumps(demo.manifests(anchor))
    assert demo.password_hash('gestor-a')==demo.password_hash('gestor-a')
    assert check_password_hash(demo.password_hash('gestor-a'),demo.PASSWORD)
    assert len(demo.manifests(anchor))==3

def test_demo_maintenance_disabled_outside_demo(monkeypatch):
    monkeypatch.setattr(demo,'demo_enabled',lambda:False)
    with pytest.raises(Problem) as failure:demo.guard(dict(role='admin'))
    assert failure.value.status==403
