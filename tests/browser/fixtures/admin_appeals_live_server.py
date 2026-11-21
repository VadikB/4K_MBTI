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
    connection.execute('CREATE TABLE users(id BIGINT PRIMARY KEY,full_name TEXT)')
    connection.execute('CREATE TABLE organizations(id BIGINT PRIMARY KEY)')
    connection.execute('CREATE TABLE organization_memberships(organization_id BIGINT,user_id BIGINT,role TEXT)')
    connection.execute("INSERT INTO users VALUES(1,'Тестовый участник'),(2,'Тестовый администратор'),(3,'Другой участник'),(4,'Другой администратор')")
    connection.execute('INSERT INTO organizations VALUES(10),(20)')
    connection.execute("INSERT INTO organization_memberships VALUES(10,1,'member'),(10,2,'admin'),(10,3,'member'),(20,4,'admin')")
    connection.execute("CREATE TABLE organization_assessment_assignments(id BIGINT,recipient_user_id BIGINT,status TEXT,revoked_at TIMESTAMP)")
    connection.execute("INSERT INTO organization_assessment_assignments VALUES(11,1,'active',NULL)")
    ensure_appeals_schema(connection)
    connection.commit()

@contextmanager
def get_connection():
    with connect() as connection:
        yield connection

routes.get_connection = get_connection
session_users = {'participant': 1, 'participant-reentry': 1, 'admin': 2, 'other': 3, 'foreign-admin': 4}
routes.web_session_service.get_user_by_token = lambda token: (
    SimpleNamespace(id=session_users[token], email=f'user-{session_users[token]}@example.test')
    if token in session_users else None
)

def admin_scope(_connection, user):
    organization_id = {2: 10, 4: 20}.get(user.id) if user else None
    if organization_id is None:
        raise HTTPException(status_code=403)
    return routes.AdminScope(organization_ids=(organization_id,), actor_user_id=user.id)

routes._get_admin_scope_or_403 = admin_scope
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
