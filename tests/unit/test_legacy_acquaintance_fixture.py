"""Component-only substitution must fail outside its explicit owned boundary."""
from types import SimpleNamespace
import json
import pytest
from tests.legacy_acquaintance_fixture import legacy_readiness


def test_legacy_boundary_refuses_non_stand_and_preserves_managed_assignment(monkeypatch,tmp_path):
    monkeypatch.delenv('AGENT4K_ISOLATED_STAND',raising=False)
    with pytest.raises(ValueError,match='OWNED_STAND_REQUIRED'):
        legacy_readiness(None,user_id=1)
    monkeypatch.setenv('AGENT4K_ISOLATED_STAND','1')
    state=tmp_path/'state.json'
    state.write_text(json.dumps({'gateway':1,'database':'product4k_pytest_synthetic','owner_marker':'stand-10.2:synthetic'}))
    monkeypatch.setenv('STAND_STATE',str(state))
    monkeypatch.setenv('DB_NAME','product4k_pytest_synthetic')
    monkeypatch.setenv('AGENT4K_STAND_MARKER','stand-10.2:synthetic')
    connection=SimpleNamespace(execute=lambda *a: SimpleNamespace(fetchone=lambda:{'present':1}))
    actual={'status':'waiting_for_assignment'}
    monkeypatch.setattr('tests.legacy_acquaintance_fixture._actual_readiness',lambda c,**k: actual)
    assert legacy_readiness(connection,user_id=1) is actual
    state.write_text(json.dumps({'gateway':1,'provider_mode':'real'}))
    with pytest.raises(ValueError,match='DISABLED_PROVIDER_OWNED_STAND_REQUIRED'):
        legacy_readiness(None,user_id=1)
