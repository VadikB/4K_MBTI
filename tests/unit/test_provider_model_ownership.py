"""Offline ownership checks; no developer dotenv, database, mail or provider IO."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from Api.llm.provider_contract import load_provider_contract
from scripts import assessment_first_case as runner

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


class UnitPortProbe:
    """Port availability is outside model-ownership units; no socket is opened."""
    def __enter__(self): return self
    def __exit__(self, *_args): return None
    def setsockopt(self, *_args): pass
    def bind(self, *_args): pass


@pytest.mark.parametrize("legacy", [None, "", "deepseek-chat", "synthetic-env-model"])
def test_fresh_process_defaults_and_new_m6_snapshots_use_contract_not_env(legacy):
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ}
    env.update(PYTHON_DOTENV_DISABLED="1", DB_POOL_MIN_SIZE="0", PYTHONPATH=str(ROOT))
    if legacy is not None:
        env["DEEPSEEK_MODEL"] = legacy
    script = """
from Api.config import settings
from Api.llm.deepseek_gateway import DeepSeekGateway
from Api.llm.provider_contract import load_provider_contract
from Api.m6_package import load_mechanism as evidence
from Api.m6_assessment_package import load_mechanism as assessment
c = load_provider_contract()
assert settings.deepseek_model == c['model']
assert DeepSeekGateway(api_keys=[]).model == c['model']
assert evidence('m6_evidence/1.0.0')['operation']['model'] == c['model']
assert assessment('m6_indicator_assessment/1.0.0')['operation']['model'] == c['model']
print('CONTRACT_MODEL_PASS')
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "CONTRACT_MODEL_PASS"


def test_explicit_frozen_operation_model_is_not_replaced_by_current_default(monkeypatch):
    from Api.llm.deepseek_gateway import DeepSeekGateway
    monkeypatch.setenv("DEEPSEEK_MODEL", "untrusted-ambient-value")
    gateway = DeepSeekGateway(api_keys=[], model="synthetic-frozen-model")
    assert gateway.model == "synthetic-frozen-model"
    assert gateway.preflight()["model_source"] == "explicit_operation"


def test_missing_contract_has_no_legacy_env_fallback(monkeypatch):
    from Api.config import settings
    from Api.llm import provider_contract
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    def missing(*_args, **_kwargs):
        raise FileNotFoundError("synthetic missing contract")
    monkeypatch.setattr(provider_contract, "load_provider_contract", missing)
    with pytest.raises(FileNotFoundError):
        _ = settings.deepseek_model


@pytest.mark.parametrize("legacy", [None, "deepseek-chat", "must-not-export-env-value"])
def test_machine_preflight_requires_credentials_and_contract_not_env_model(monkeypatch, legacy):
    monkeypatch.setenv("STAND_ADMIN_URL", "postgresql://u@localhost/postgres")
    monkeypatch.setenv("DEEPSEEK_API_KEYS", "must-not-export-key")
    if legacy is None:
        monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    else:
        monkeypatch.setenv("DEEPSEEK_MODEL", legacy)
    monkeypatch.setattr(runner.Path, "is_file", lambda _self: True)
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "/synthetic/node")
    monkeypatch.setattr(runner.socket, "socket", UnitPortProbe)
    value = runner.preflight(0, sys.executable)
    assert value["status"] == "READY"
    contract = load_provider_contract()
    assert value["provider"]["model"] == contract["model"]
    assert value["provider"]["model_source"] == "provider_contract"
    assert value["provider"]["contract_checksum"] == contract["checksum"]
    assert value["provider"]["legacy_env_model_present"] is (legacy is not None)
    assert "must-not-export" not in json.dumps(value)


@pytest.mark.parametrize("invalid", [FileNotFoundError, ValueError])
def test_preflight_contract_failure_is_blocked_without_secret_details(monkeypatch, invalid):
    from Api.llm import provider_contract
    monkeypatch.setenv("DEEPSEEK_API_KEYS", "must-not-export-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "must-not-export-env-value")
    def broken(*_args, **_kwargs):
        raise invalid("must-not-export-error")
    monkeypatch.setattr(provider_contract, "load_provider_contract", broken)
    value = runner.preflight(0, sys.executable)
    check = next(item for item in value["checks"] if item["code"] == "provider_contract")
    assert value["status"] == check["status"] == "BLOCKED"
    assert "must-not-export" not in json.dumps(value)


def test_contract_does_not_replace_missing_credentials(monkeypatch):
    for key in ('DEEPSEEK_API_KEYS', 'DEEPSEEK_API_KEY', 'DEEPSEEK_API_KEY_2', 'DEEPSEEK_API_KEY_3'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('DEEPSEEK_MODEL', 'must-not-export-env-value')
    value = runner.preflight(0, sys.executable)
    checks = {item['code']: item['status'] for item in value['checks']}
    assert value['status'] == checks['real_provider'] == 'BLOCKED'
    assert checks['provider_contract'] == 'READY'
    assert 'must-not-export' not in json.dumps(value)


@pytest.mark.parametrize('file_legacy', [None, 'must-not-export-file-model'])
def test_cli_copies_credentials_only_and_never_forwards_model(tmp_path, monkeypatch, capsys, file_legacy):
    import dotenv
    for key in ('STAND_ADMIN_URL', 'DEEPSEEK_API_KEYS', 'DEEPSEEK_API_KEY',
                'DEEPSEEK_API_KEY_2', 'DEEPSEEK_API_KEY_3', 'DEEPSEEK_BASE_URL',
                'DEEPSEEK_MAX_CONCURRENCY'):
        monkeypatch.setenv(key, '')
    monkeypatch.delenv('DEEPSEEK_MODEL', raising=False)
    values = {'DEEPSEEK_API_KEY_2': 'must-not-export-key', 'DB_USER': 'synthetic',
              'DB_PASSWORD': 'must-not-export-password'}
    if file_legacy is not None:
        values['DEEPSEEK_MODEL'] = file_legacy
    monkeypatch.setattr(dotenv, 'dotenv_values', lambda *_a, **_kw: values)
    monkeypatch.setattr(sys, 'argv', ['assessment_first_case.py', '--env-file', '/synthetic.env',
        '--directory', str(tmp_path), '--check-bootstrap'])
    monkeypatch.setattr(runner.Path, 'is_file', lambda _self: True)
    monkeypatch.setattr(runner.shutil, 'which', lambda _name: '/synthetic/node')
    monkeypatch.setattr(runner.socket, 'socket', UnitPortProbe)
    original = runner.preflight
    # This unit tests CLI plumbing, not actual PG/Chromium/bootstrap or PATH success.
    monkeypatch.setattr(runner, 'preflight', lambda p, py, **kw: original(
        p, py, legacy_model_present=kw['legacy_model_present']))
    monkeypatch.setattr(runner, 'code_identity', lambda: {'scope': 'synthetic-unit'})
    seen = []
    monkeypatch.setattr(runner, 'check_bootstrap', lambda _d, _p, _py, env: seen.append(env))
    monkeypatch.setattr(runner, 'summarize_runs', lambda *_args: {'exit_code': 0})
    assert runner.main() == 0
    assert 'DEEPSEEK_MODEL' not in seen[0]
    assert seen[0]['DEEPSEEK_API_KEY_2'] == values['DEEPSEEK_API_KEY_2']
    actual = json.loads((tmp_path / 'preflight.json').read_bytes())
    assert actual['provider']['model'] == load_provider_contract()['model']
    assert actual['provider']['legacy_env_model_present'] is (file_legacy is not None)
    assert actual['provider']['legacy_env_model_ignored'] is True
    assert 'must-not-export' not in capsys.readouterr().out


@pytest.mark.parametrize("name", [".env.example", ".env.local.example", ".env.production.example", ".env.test.example"])
def test_env_templates_do_not_select_model(name):
    from dotenv import dotenv_values
    assert "DEEPSEEK_MODEL" not in dotenv_values(ROOT / name)
