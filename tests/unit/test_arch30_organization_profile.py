from __future__ import annotations

from types import SimpleNamespace

from Api import routes
from Api.org_access import AdminScope
from Api.schemas import AdminOrganizationsResponse, AdminOrganizationUpdateRequest


class _Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self):
        self.update = None
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        if "SELECT id FROM organizations" in query:
            return _Result({"id": 3})
        if "UPDATE organizations" in query:
            self.update = (" ".join(query.split()), params)
            return _Result()
        raise AssertionError(query)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_legacy_profile_is_not_rewritten_by_current_card_update(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(routes, "get_connection", lambda: connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _token: SimpleNamespace(id=18))
    monkeypatch.setattr(
        routes,
        "_require_organization_admin",
        lambda *_args: AdminScope(is_superadmin=True),
    )
    monkeypatch.setattr(
        routes,
        "_build_admin_organizations",
        lambda *_args: AdminOrganizationsResponse(title="Организации", subtitle="", items=[]),
    )

    routes.update_admin_organization(
        3,
        AdminOrganizationUpdateRequest(profile="legacy must stay", industry="ИТ"),
        SimpleNamespace(cookies={routes.SESSION_COOKIE_NAME: "session"}),
    )

    query, params = connection.update
    assert "profile =" not in query
    assert "legacy must stay" not in params
    assert "ИТ" in params
    assert connection.committed and not connection.rolled_back
