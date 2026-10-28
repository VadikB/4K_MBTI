from contextlib import contextmanager
from types import SimpleNamespace

from Api import web_session_service as sessions


def test_session_lookup_never_executes_schema_ddl(monkeypatch):
    statements = []
    class Connection:
        def execute(self, sql, _params=()):
            statements.append(sql)
            return SimpleNamespace(fetchone=lambda: None)
    @contextmanager
    def get_connection(): yield Connection()
    monkeypatch.setattr(sessions, 'get_connection', get_connection)
    def forbidden(): raise AssertionError('DDL in request path')
    monkeypatch.setattr(sessions.web_session_service, 'ensure_schema', forbidden)
    assert sessions.web_session_service.get_user_by_token('synthetic-token') is None
    assert len(statements) == 1
    assert 'expires_at > NOW()' in statements[0]
    assert "updated_at > NOW() - INTERVAL '24 hours'" in statements[0]
