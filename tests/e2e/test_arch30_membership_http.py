from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from Api import routes
from Api.org_access import AdminScope
from Api.schemas import AdminOrganizationsResponse


pytestmark = pytest.mark.e2e


class _Connection:
    def __init__(self, *, delete_rowcount=1):
        self.committed = False
        self.queries = []
        self.rowcount = 0
        self.delete_rowcount = delete_rowcount

    def execute(self, query, params=None):
        self.queries.append((" ".join(query.split()), params))
        self.rowcount = self.delete_rowcount if "DELETE FROM organization_memberships" in query else 0
        return self

    def fetchone(self):
        return {"id": 3, "is_active": False}

    def commit(self):
        self.committed = True


@pytest.fixture
def membership_http(monkeypatch):
    connection = _Connection()

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(
        routes.web_session_service,
        "get_user_by_token",
        lambda _token: SimpleNamespace(id=18),
    )
    monkeypatch.setattr(
        routes,
        "_build_admin_organizations",
        lambda _connection, _scope=None: AdminOrganizationsResponse(
            title="Организации", subtitle="", is_superadmin=bool(_scope and _scope.is_superadmin), items=[]
        ),
    )
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as http:
        yield http, connection


def test_org_admin_conflict_is_409_without_foreign_tenant_leak(monkeypatch, membership_http):
    http, connection = membership_http
    monkeypatch.setattr(
        routes,
        "_require_organization_admin",
        lambda *_args: AdminScope(is_superadmin=False, organization_ids=(4,)),
    )

    def attach(_connection, **kwargs):
        routes._reject_foreign_membership(
            {"organization_id": 3, "organization_name": "Секретный заказчик"},
            organization_id=kwargs["organization_id"],
            expose_organization=kwargs["expose_existing_organization"],
        )

    monkeypatch.setattr(routes, "_attach_user_to_organization", attach)
    response = http.post(
        "/users/admin/organizations/4/members",
        json={"email": "person@example.test", "full_name": "Не должно сохраниться",
              "role_description": "Специалист"},
    )

    assert response.status_code == 409
    assert "ORGANIZATION_MEMBERSHIP_CONFLICT" in response.json()["detail"]
    assert "Секретный заказчик" not in response.text
    assert not connection.committed


def test_superadmin_conflict_includes_open_or_transfer_action(monkeypatch, membership_http):
    http, connection = membership_http
    monkeypatch.setattr(
        routes,
        "_require_organization_admin",
        lambda *_args: AdminScope(is_superadmin=True),
    )

    def attach(_connection, **kwargs):
        routes._reject_foreign_membership(
            {"organization_id": 3, "organization_name": "Организация А"},
            organization_id=kwargs["organization_id"],
            expose_organization=kwargs["expose_existing_organization"],
        )

    monkeypatch.setattr(routes, "_attach_user_to_organization", attach)
    response = http.post(
        "/users/admin/organizations/4/members",
        json={"email": "person@example.test", "full_name": "Участник",
              "role_description": "Специалист"},
    )

    assert response.status_code == 409
    assert "Организация А" in response.json()["detail"]
    assert "перенесите пользователя" in response.json()["detail"]
    assert not connection.committed


def test_member_requires_full_name_and_position_before_database_write(membership_http):
    http, connection = membership_http
    response = http.post(
        "/users/admin/organizations/4/members",
        json={"email": "person@example.test", "full_name": " ", "role_description": " "},
    )
    assert response.status_code == 422
    assert connection.queries == []


def test_member_csv_skips_rows_without_name_or_position(monkeypatch, membership_http):
    http, connection = membership_http
    monkeypatch.setattr(
        routes,
        "_require_organization_admin",
        lambda *_args: AdminScope(is_superadmin=False, organization_ids=(4,)),
    )
    attached = []
    monkeypatch.setattr(routes, "_attach_user_to_organization", lambda *_args, **kwargs: attached.append(kwargs))

    response = http.post(
        "/users/admin/organizations/4/members/import",
        json={"csv_text": (
            "email,full_name,role_description\n"
            "missing-name@example.test,,Специалист\n"
            "missing-position@example.test,Иван Иванов,  \n"
        )},
    )

    assert response.status_code == 200
    assert response.json()["imported_count"] == 0
    assert response.json()["skipped_count"] == 2
    assert response.json()["errors"] == [
        "Строка 2: не указаны обязательные поля: ФИО",
        "Строка 3: не указаны обязательные поля: должность",
    ]
    assert attached == []
    assert connection.committed


def test_member_removal_reports_and_audits_affected_rows(monkeypatch, membership_http):
    http, connection = membership_http
    monkeypatch.setattr(
        routes,
        "_require_organization_admin",
        lambda *_args: AdminScope(is_superadmin=False, organization_ids=(4,)),
    )

    response = http.delete(
        "/users/admin/organizations/4/members",
        params={"email": "person@example.test"},
    )

    assert response.status_code == 200
    assert response.json()["membership_action"] == {
        "target_user_id": 3,
        "organization_id": 4,
        "relationship_type": "member",
        "result": "removed",
        "affected_rows": 1,
    }
    assert any(
        "INSERT INTO organization_membership_action_audit" in query
        and params == (18, 3, 4, "removed", 1)
        for query, params in connection.queries
    )
    assert connection.committed

    connection.delete_rowcount = 0
    repeated = http.delete(
        "/users/admin/organizations/4/members",
        params={"email": "person@example.test"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["membership_action"]["result"] == "already_absent"
    assert repeated.json()["membership_action"]["affected_rows"] == 0
    assert any(
        "INSERT INTO organization_membership_action_audit" in query
        and params == (18, 3, 4, "already_absent", 0)
        for query, params in connection.queries
    )


def test_organization_admin_cannot_call_superadmin_transfer(monkeypatch, membership_http):
    http, connection = membership_http

    def reject_transfer(*_args):
        raise routes.HTTPException(status_code=403, detail="Superadmin access required")

    monkeypatch.setattr(routes, "_require_superadmin", reject_transfer)
    response = http.post(
        "/users/admin/users/7/transfer-organization",
        json={
            "expected_source_organization_id": 3,
            "target_organization_id": 4,
            "target_role": "member",
            "operation_id": "transfer-operation-1",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Superadmin access required"
    assert not connection.committed


def test_superadmin_can_explicitly_restore_deactivated_organization(monkeypatch, membership_http):
    http, connection = membership_http
    monkeypatch.setattr(routes, "_require_superadmin", lambda *_args: None)

    response = http.post("/users/admin/organizations/3/restore")

    assert response.status_code == 200
    assert connection.committed
    assert any(
        "SET is_active = TRUE" in query and params == (3,)
        for query, params in connection.queries
    )
