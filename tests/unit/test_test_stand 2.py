import pytest
from scripts.test_stand import admin_params,environment,owned
from Api.m10_test_gateway import enabled


@pytest.mark.parametrize('url',['','postgresql://localhost/app_db','postgresql://external.invalid/postgres'])
def test_stand_rejects_unsafe_configuration_before_connect(url):
    with pytest.raises(ValueError):admin_params(url)


def test_stand_does_not_inherit_provider_or_developer_config(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEYS','do-not-copy')
    monkeypatch.setenv('DB_NAME','developer')
    monkeypatch.setenv('STAND_ADMIN_URL','postgresql://u@localhost/postgres')
    env=environment({'connection':{'host':'localhost','user':'u'},'database':'product4k_pytest_abc',
        'gateway':0,'port':18520,'state_path':'/tmp/owned','owner_marker':'stand-10.2:test'})
    assert 'DEEPSEEK_API_KEYS' not in env and env['DB_NAME']=='product4k_pytest_abc'
    assert env['AGENT4K_BROWSER_TEST_GATEWAY']=='0'


def test_test_gateway_never_falls_back(monkeypatch):
    monkeypatch.delenv('AGENT4K_BROWSER_TEST_GATEWAY',raising=False)
    assert enabled() is False
    monkeypatch.setenv('AGENT4K_BROWSER_TEST_GATEWAY','1')
    monkeypatch.delenv('AGENT4K_ISOLATED_STAND',raising=False)
    with pytest.raises(ValueError,match='ISOLATED'):enabled()


def test_foreign_reset_target_rejected_before_connect(monkeypatch):
    monkeypatch.setenv('STAND_ADMIN_URL','postgresql://u@localhost/postgres')
    with pytest.raises(ValueError,match='NAME_MISMATCH'):
        owned({'connection':{'host':'localhost','user':'u'},'database':'other_test','run_id':'abc'})


def test_real_provider_absent_is_explicit_error_in_fresh_process():
    import os,subprocess,sys
    result=subprocess.run([sys.executable,'-c',
        "from Api.llm.deepseek_gateway import DeepSeekGateway; g=DeepSeekGateway(); assert not g.enabled; "
        "g.chat([{'role':'user','content':'synthetic'}])"],
        env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR') } | {'AGENT4K_ISOLATED_STAND':'1','DB_HOST':'127.0.0.1','DB_NAME':'product4k_pytest_unit',
            'DB_USER':'synthetic','AGENT4K_STAND_MARKER':'stand-10.2:unit','DB_POOL_MIN_SIZE':'0'},
        capture_output=True,text=True)
    assert result.returncode!=0
    assert 'RuntimeError' in result.stderr or 'ValueError' in result.stderr
    assert 'Traceback' in result.stderr
