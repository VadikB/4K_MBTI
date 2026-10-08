"""No schema fixtures: exercise the same CLI as the documented stand, twice."""
import os
from pathlib import Path
import subprocess
import sys
import pytest

pytestmark=pytest.mark.integration


def test_port_probe_rejects_live_listener_and_allows_closed_connection():
    import socket
    from scripts.test_stand import check_port
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        listener.bind(('127.0.0.1',0));listener.listen(1)
        port=listener.getsockname()[1]
        with pytest.raises(OSError):
            check_port(port)
        with socket.create_connection(('127.0.0.1',port)) as client:
            connection,_=listener.accept()
            connection.close()
            assert client.recv(1)==b''
    check_port(port)


def test_two_empty_database_application_starts_and_owner_http_reports(tmp_path):
    # This is deliberately FAIL, not skip, when explicitly running integration without its DB.
    url=os.getenv('TEST_DATABASE_URL')
    assert url,'TEST_DATABASE_URL required for clean bootstrap regression'
    env={**os.environ,'STAND_ADMIN_URL':url}
    for index in range(2):
        result=subprocess.run([sys.executable,'scripts/test_stand_check.py','--directory',str(tmp_path/str(index)),
            '--port',str(18730+index)],env=env,capture_output=True,text=True,timeout=240)
        if result.returncode:
            logs='\n'.join(p.read_text()[-5000:] for p in (tmp_path/str(index)).glob('*.log'))
            pytest.fail(result.stdout+result.stderr+logs)
        assert (tmp_path/str(index)/'report.pdf').read_bytes().startswith(b'%PDF')


def test_bootstrap_rejects_unknown_state_and_detects_structural_drift(tmp_path):
    import json
    import psycopg
    url=os.getenv('TEST_DATABASE_URL')
    assert url,'TEST_DATABASE_URL required'
    env={**os.environ,'STAND_ADMIN_URL':url}
    state_path=tmp_path/'negative.json'
    def run(action,ok=True):
        result=subprocess.run([sys.executable,'scripts/test_stand.py',action,'--state',str(state_path)],env=env,capture_output=True,text=True,timeout=60)
        assert (result.returncode==0)==ok,result.stdout+result.stderr
    run('create')
    state=json.loads(state_path.read_text());params={**state['connection'],'dbname':state['database']}
    try:
        # The real entrypoint must fail without its mandatory schema.
        run('serve',False)
        with psycopg.connect(**params) as c:
            assert c.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0]==0
            c.execute('CREATE TABLE unknown_test_object(id INTEGER)')
        run('bootstrap',False)
        with psycopg.connect(**params) as c:
            assert c.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0]==1
            c.execute('DROP TABLE unknown_test_object')
        run('bootstrap')
        with psycopg.connect(**params) as c:
            c.execute('ALTER TABLE users ADD COLUMN unexpected_test_field TEXT')
        run('bootstrap',False)
        run('serve',False)
        # Ownership marker is checked before any destructive statement.
        original=state['owner_marker'];state['owner_marker']='foreign'
        state_path.write_text(json.dumps(state));run('destroy',False)
        state['owner_marker']=original;state_path.write_text(json.dumps(state))
    finally:
        run('destroy')
