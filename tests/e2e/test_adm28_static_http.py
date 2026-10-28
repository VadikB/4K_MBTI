"""Exercise the actual middleware functions without importing DB startup code."""
import ast
import logging
import threading
import traceback
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from starlette.concurrency import run_in_threadpool

pytestmark = pytest.mark.e2e


def middleware_app(resolve_user):
    app = FastAPI()
    names = {'_resolve_request_user', '_is_static_request_path', '_should_persist_request_audit',
             'disable_browser_cache', 'log_unhandled_exceptions'}
    source = ast.parse(Path('main.py').read_text())
    nodes = [node for node in source.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    namespace = dict(app=app, Request=Request, perf_counter=perf_counter, run_in_threadpool=run_in_threadpool,
                     web_session_service=SimpleNamespace(get_user_by_token=resolve_user),
                     settings=SimpleNamespace(audit_logs_to_db=True), traceback=traceback,
                     FastAPIHTTPException=HTTPException, logger=logging.getLogger('synthetic.static'))
    def audit(**kwargs):
        assert not kwargs['request_path'].startswith(('/web/', '/favicons/'))
        assert kwargs['request_path'] != '/'
    namespace['write_system_log'] = audit
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'main.py', 'exec'), namespace)
    app.mount('/web', StaticFiles(directory='web'))
    app.mount('/favicons', StaticFiles(directory='web/favicons'))
    @app.get('/')
    def root(): return FileResponse('web/index.html')
    @app.get('/users/synthetic-protected')
    def protected(request: Request):
        if namespace['_resolve_request_user'](request) is None: raise HTTPException(401, 'Session required')
        return {'ok': True}
    return app


@pytest.mark.parametrize('path', ['/', '/web/dist/main.js', '/web/styles/base.css',
                                 '/web/assets/fonts/onest/Onest-Variable.woff', '/favicons/favicon.ico', '/web/missing-file'])
def test_public_assets_with_cookie_do_not_resolve_user_or_audit_database(path):
    def unavailable_database(_token): raise AssertionError('Public asset attempted session lookup')
    with TestClient(middleware_app(unavailable_database)) as client:
        client.cookies.set('agent4k_session_token', 'synthetic-unreachable-session')
        response = client.get(path)
        assert response.status_code == (404 if 'missing' in path else 200)


def test_protected_requests_resolve_session_in_threadpool_and_reject_expired_session():
    threads = []
    def expired(_token):
        threads.append(threading.get_ident())
        return None
    with TestClient(middleware_app(expired)) as client:
        client.cookies.set('agent4k_session_token', 'synthetic-expired-session')
        response = client.get('/users/synthetic-protected')
        assert response.status_code == 401
        # The two middleware layers share the request-scoped result.
        assert len(threads) == 1
