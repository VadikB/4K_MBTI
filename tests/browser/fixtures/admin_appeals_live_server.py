"""Disposable Admin 03 HTTP/PG browser check. Never targets an existing app DB."""
import os
import re
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from Api import acquaintance, routes
from Api.database import ensure_appeals_schema

ROOT = Path(__file__).resolve().parents[3]
DB_URL = os.environ['TEST_DATABASE_URL']
if not any(marker in conninfo_to_dict(DB_URL).get('dbname', '').lower() for marker in ('test', 'pytest')):
    raise RuntimeError('Only an isolated test/pytest database is allowed')
SCHEMA = 'admin03_live_' + uuid4().hex

def connect():
    connection = psycopg.connect(DB_URL, row_factory=dict_row)
    connection.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(SCHEMA)))
    return connection

with psycopg.connect(DB_URL, row_factory=dict_row) as connection:
    connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(SCHEMA)))
    connection.commit()
with connect() as connection:
    connection.execute('CREATE TABLE users(id BIGINT PRIMARY KEY)')
    connection.execute('CREATE TABLE organizations(id BIGINT PRIMARY KEY)')
    connection.execute('CREATE TABLE organization_memberships(organization_id BIGINT,user_id BIGINT,role TEXT)')
    connection.execute('INSERT INTO users VALUES(1),(2),(3)')
    connection.execute('INSERT INTO organizations VALUES(10)')
    connection.execute("INSERT INTO organization_memberships VALUES(10,1,'member'),(10,2,'admin'),(10,3,'member')")
    ensure_appeals_schema(connection)
    connection.commit()

@contextmanager
def get_connection():
    with connect() as connection:
        yield connection

routes.get_connection = get_connection
routes.web_session_service.get_user_by_token = lambda token: (
    SimpleNamespace(id={'participant': 1, 'admin': 2, 'other': 3}[token], email=f'{token}@example.test')
    if token in ('participant', 'admin', 'other') else None
)
routes._require_organization_admin = lambda _connection, user, organization_id: (
    SimpleNamespace(is_superadmin=False) if user and user.id == 2 and organization_id == 10
    else (_ for _ in ()).throw(HTTPException(status_code=403))
)
acquaintance.early_readiness = lambda *_args, **_kwargs: {
    'status': 'ready', 'organization_id': 10, 'assignment_ref': 'program-a',
    'assignment_id': 11, 'questionnaire_revision_id': 3,
}

app = FastAPI()
app.include_router(routes.router)
app.mount('/web', StaticFiles(directory=ROOT / 'web'), name='web')

@app.get('/', response_class=HTMLResponse)
def index():
    html = (ROOT / 'web/index.html').read_text()
    return re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S | re.I)

@app.get('/__evidence')
def evidence():
    with connect() as connection:
        issue = connection.execute('SELECT id,status,claimed_by_user_id,scope_key FROM participant_data_issue_reports').fetchone()
        reply = connection.execute('SELECT issue_id,author_user_id,message FROM participant_data_issue_replies').fetchone()
        return {'issue': dict(issue) if issue else None, 'reply': dict(reply) if reply else None}

if __name__ == '__main__':
    try:
        uvicorn.run(app, host='127.0.0.1', port=int(os.environ['ADMIN03_TEST_PORT']), log_level='warning')
    finally:
        with psycopg.connect(DB_URL) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(SCHEMA)))
            connection.commit()
