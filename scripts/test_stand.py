"""Disposable localhost PostgreSQL stand. Never reads the developer .env."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import socket
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def check_port(port):
    with socket.socket() as probe:
        # Match uvicorn's restart semantics: TIME_WAIT is not a live server.
        probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        probe.bind(('127.0.0.1',port))
        probe.listen(1)


def admin_params(url):
    from psycopg.conninfo import conninfo_to_dict
    if not url:
        raise ValueError('STAND_ADMIN_URL is required; no DB_NAME/.env fallback')
    p=conninfo_to_dict(url)
    if p.get('host') not in ('127.0.0.1','localhost') or p.get('dbname') not in ('postgres','agent4k_pytest','task11_pytest'):
        raise ValueError('Stand requires an explicitly selected localhost maintenance/test database')
    if set(p)-{'host','port','dbname','user','password','connect_timeout'} or not p.get('user'):
        raise ValueError('Explicit user and plain localhost connection parameters are required')
    p.setdefault('connect_timeout','5')
    return p


def environment(state):
    p=state['connection']
    env={k:os.environ[k] for k in ('PATH','HOME','TMPDIR','SYSTEMROOT') if k in os.environ}
    env.update(AGENT4K_ISOLATED_STAND='1',DB_HOST=p['host'],DB_PORT=str(p.get('port',5432)),
        DB_NAME=state['database'],DB_USER=p['user'],DB_PASSWORD=p.get('password',''),DB_POOL_MIN_SIZE='0',
        DB_POOL_TIMEOUT_SECONDS='3',AGENT4K_BROWSER_TEST_GATEWAY=str(state['gateway']),
        APP_BASE_URL=f"http://127.0.0.1:{state['port']}",AUTH_MAGIC_LINK_DEV_MODE='false',
        AUTH_SESSION_SECURE_COOKIE='false',LOG_TO_STDOUT='true',LOG_TO_FILE='false',
        PYTHONPATH=str(ROOT),STAND_STATE=str(state['state_path']),
        AGENT4K_STAND_MARKER=state['owner_marker'],STAND_ADMIN_URL=os.environ['STAND_ADMIN_URL'])
    if state.get('browser_scenario') == 'acceptance-v1':
        env['AGENT4K_BROWSER_SCENARIO']='acceptance-v1'
    return env


def owned(state):
    import psycopg
    from psycopg.conninfo import make_conninfo
    p=admin_params(os.getenv('STAND_ADMIN_URL'))
    if {k:p.get(k,'') for k in ('host','port','user')}!={k:state['connection'].get(k,'') for k in ('host','port','user')}:
        raise ValueError('STAND_TARGET_MISMATCH')
    if state['database']!='product4k_pytest_'+state['run_id']:
        raise ValueError('STAND_NAME_MISMATCH')
    c=psycopg.connect(make_conninfo(**p),autocommit=True)
    row=c.execute('SELECT shobj_description(oid,\'pg_database\') FROM pg_database WHERE datname=%s',(state['database'],)).fetchone()
    if not row or row[0]!=state['owner_marker']:
        c.close();raise ValueError('STAND_NOT_OWNED')
    return c


def prepare():
    from Api.database import get_connection,ensure_core_schema
    from Api.schema_bootstrap import bootstrap_base,check_schema,fingerprint
    from Api.m5_generation_lab import ensure_lab_schema
    from Api.web_session_service import web_session_service
    from Api.auth_service import auth_service
    with get_connection() as c:
        bootstrap_base(c)
        saved=c.execute('SELECT schema_hash FROM app_bootstrap').fetchone()['schema_hash']
        if saved:check_schema(c)
        c.commit()
    ensure_core_schema()
    with get_connection() as c:
        ensure_lab_schema(c);c.commit()
    web_session_service.ensure_schema();auth_service.ensure_schema()
    from Api.agent import interviewer_agent
    interviewer_agent._ensure_session_schema()
    with get_connection() as c:
        c.execute('UPDATE app_bootstrap SET schema_hash=%s',(fingerprint(c),));c.commit()
    print('bootstrap ready')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['create','bootstrap','seed','serve','smoke','destroy','_bootstrap','_seed'])
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--port',type=int,default=18520)
    parser.add_argument('--gateway',choices=['0','1'],default='0')
    args=parser.parse_args();path=args.state.resolve()
    if args.action.startswith('_'):
        if os.getenv('AGENT4K_ISOLATED_STAND')!='1':raise ValueError('ISOLATED_STAND_REQUIRED')
        with owned(json.loads(path.read_text())):
            pass
        if args.action=='_bootstrap':prepare()
        else:
            from scripts.test_stand_seed import seed
            seed(json.loads(path.read_text()))
        return
    if args.action=='create':
        import psycopg
        from psycopg import sql
        p=admin_params(os.getenv('STAND_ADMIN_URL'))
        if path.exists():raise ValueError('State exists; use bootstrap/serve or a new state path')
        p.setdefault('user',os.getenv('USER',''))
        run=uuid4().hex;name='product4k_pytest_'+run;marker='stand-10.2:'+secrets.token_hex(24)
        path.parent.mkdir(parents=True,exist_ok=True)
        state={'run_id':run,'database':name,'owner_marker':marker,'connection':p,'state_path':str(path),
            'port':args.port,'gateway':int(args.gateway),'password':secrets.token_urlsafe(22)+'A1!'}
        with psycopg.connect(**p,autocommit=True) as c:
            c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            c.execute(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(name),sql.Literal(marker)))
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:json.dump(state,f)
        with psycopg.connect(**{**p,'dbname':name}) as empty:
            count=empty.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0]
            if count:raise ValueError('CREATED_DATABASE_NOT_EMPTY')
        print('Created empty owned stand:',name,'application_tables=0')
        return
    state=json.loads(path.read_text())
    with owned(state) as c:
        if args.action=='destroy':
            from psycopg import sql
            # No FORCE: active app connections must be stopped first.
            c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(state['database'])))
            path.unlink();print('Owned stand removed');return
    env=environment(state)
    if args.action in ('bootstrap','seed'):
        subprocess.run([sys.executable,__file__,'_'+args.action,'--state',str(path)],env=env,cwd=ROOT,check=True)
    elif args.action=='serve':
        check_port(state['port'])
        os.execve(sys.executable,[sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port',str(state['port']),'--no-access-log'],env)
    elif args.action=='smoke':
        subprocess.run([sys.executable,str(ROOT/'scripts/test_stand_smoke.py'),'--state',str(path)],env=env,cwd=ROOT,check=True)


if __name__=='__main__':
    main()
