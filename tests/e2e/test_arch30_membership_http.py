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
        normalized = " ".join(query.split())
        self.rowcount = self.delete_rowcount if (
            "DELETE FROM organization_memberships" in normalized
            or "UPDATE organization_memberships SET is_participant=FALSE" in normalized
        ) else 0
        return self

    def fetchone(self):
        return {"id": 3, "code": "synthetic-org", "is_active": False}

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


def test_superadmin_conflict_identifies_current_organization_without_transfer(monkeypatch, membership_http):
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
    assert "Управляйте его участием" in response.json()["detail"]
    assert "перенес" not in response.json()["detail"]
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


def test_legacy_member_exclusion_is_gone_without_partial_changes(monkeypatch, membership_http):
    http, connection = membership_http
    monkeypatch.setattr(routes, "_require_organization_admin",
        lambda *_args: AdminScope(is_superadmin=False, organization_ids=(4,)))
    response = http.delete("/users/admin/organizations/4/members",
        params={"email": "person@example.test"})
    assert response.status_code == 410
    assert response.json()["detail"] == "MEMBER_EXCLUSION_REMOVED_USE_ACCOUNT_PURGE"
    assert connection.queries == []
    assert not connection.committed


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


def test_admin_authority_is_removed_without_erasing_participation(monkeypatch, membership_http):
    http, connection = membership_http
    monkeypatch.setattr(routes, "_require_superadmin", lambda *_args: None)

    response = http.delete(
        "/users/admin/organizations/4/admins",
        params={"email": "person@example.test"},
    )

    assert response.status_code == 200
    assert any(
        "SET role='member'" in query and "is_participant=TRUE" in query
        for query, _params in connection.queries
    )
    assert any(
        "role='admin' AND is_participant=FALSE" in query
        for query, _params in connection.queries
    )


def test_removed_transfer_endpoint_is_gone_for_superadmin(monkeypatch, membership_http):
    http, _connection = membership_http
    monkeypatch.setattr(routes, "_require_superadmin", lambda *_args: None)

    response = http.post(
        "/users/admin/users/7/transfer-organization",
        json={
            "expected_source_organization_id": 3,
            "target_organization_id": 4,
            "target_role": "member",
            "operation_id": "transfer-operation-removed",
        },
    )

    assert response.status_code == 410
    assert response.json()["detail"] == "ORGANIZATION_TRANSFER_REMOVED"
    assert not _connection.committed


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
