from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.rows import dict_row

from Api import routes
from Api.org_access import AdminScope


pytestmark = pytest.mark.integration


def _schema(connection, name):
    connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
    connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(name)))


def test_exact_assignment_readback_requires_committed_operation(test_database_url, monkeypatch):
    schema = "adm1c_receipt_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        _schema(connection, schema)
        connection.execute("""CREATE TABLE organization_assessment_assignment_operations(
            organization_id BIGINT,actor_user_id BIGINT,operation_id TEXT,request_fingerprint TEXT,
            PRIMARY KEY(organization_id,actor_user_id,operation_id))""")
        connection.execute("""CREATE TABLE organization_assessment_assignments(
            id BIGSERIAL PRIMARY KEY,organization_id BIGINT,recipient_user_id BIGINT,assignment_ref TEXT,
            status TEXT,revoked_at TIMESTAMP)""")
        connection.execute("""CREATE TABLE organization_invitations(
            id BIGSERIAL PRIMARY KEY,organization_id BIGINT,created_by_user_id BIGINT,purpose TEXT,
            request_id TEXT,assignment_ref TEXT,recipient_email TEXT,expires_at TIMESTAMP,
            delivery_status TEXT,delivery_error TEXT,used_at TIMESTAMP,revoked_at TIMESTAMP)""")
        connection.execute("""INSERT INTO organization_assessment_assignments
            (organization_id,recipient_user_id,assignment_ref,status) VALUES(3,8,'assessment-a','active')""")
        connection.commit()

    @contextmanager
    def get_connection():
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(routes, "_require_organization_admin", lambda *_args: None)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _token: SimpleNamespace(id=18))
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as http:
        stale = http.get("/users/admin/organizations/3/assessment-assignments/operations/missing-op",
                         params={"assignment_ref": "assessment-a", "user_ids": "8"})
        assert stale.status_code == 404

        import hashlib, json
        fingerprint = hashlib.sha256(json.dumps({"assignment_ref": "assessment-a", "user_ids": [8],
            "role_profile_version_id": None}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with get_connection() as connection:
            connection.execute("INSERT INTO organization_assessment_assignment_operations VALUES(3,18,%s,%s)",
                               ("committed-op", fingerprint))
            connection.commit()
        exact = http.get("/users/admin/organizations/3/assessment-assignments/operations/committed-op",
                         params={"assignment_ref": "assessment-a", "user_ids": "8"})
        assert exact.status_code == 200
        assert exact.json()["items"] == [{"user_id": 8, "status": "already_assigned",
                                           "assignment_id": 1, "error": None}]
        with get_connection() as connection:
            connection.execute("""INSERT INTO organization_invitations
                (organization_id,created_by_user_id,purpose,request_id,assignment_ref,recipient_email,
                 expires_at,delivery_status) VALUES(3,18,'personal_registration','invite-op',
                 'assessment-a','person@example.test',NOW()+INTERVAL '1 day','queued')""")
            connection.commit()
        invitation = http.get(
            "/users/admin/organizations/3/personal-invitations/operations/invite-op",
            params={"assignment_ref": "assessment-a"},
        )
        assert invitation.status_code == 200
        assert invitation.json()["items"][0]["email"] == "person@example.test"
        assert invitation.json()["items"][0]["status"] == "queued"

    with psycopg.connect(test_database_url) as connection:
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        connection.commit()


def test_modern_dashboard_counts_cycles_reports_and_closed_period(test_database_url):
    schema = "adm1c_metrics_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        _schema(connection, schema)
        connection.execute("""CREATE TABLE m5_cycles(
            id BIGSERIAL PRIMARY KEY,organization_id BIGINT,usage_scope TEXT,started_at TIMESTAMPTZ,
            collection_closed_at TIMESTAMPTZ)""")
        connection.execute("CREATE TABLE m8_results(id UUID PRIMARY KEY,cycle_db_id BIGINT)")
        connection.execute("CREATE TABLE m8_result_revisions(id UUID PRIMARY KEY,results_id UUID)")
        connection.execute("CREATE TABLE m8_reports(id UUID PRIMARY KEY,result_revision_id UUID,status TEXT)")
        connection.execute("CREATE TABLE m10_pipeline_runs(cycle_db_id BIGINT PRIMARY KEY,status TEXT)")
        cycles = connection.execute("""INSERT INTO m5_cycles(organization_id,usage_scope,started_at,collection_closed_at)
            VALUES(10,'assessment',NOW()-INTERVAL '2 days',NOW()-INTERVAL '1 day'),
                  (10,'assessment',NOW()-INTERVAL '1 day',NOW()),
                  (10,'assessment',NOW(),NULL),
                  (10,'qa',NOW(),NOW()) RETURNING id""").fetchall()
        for index, cycle in enumerate(cycles[:2]):
            result_id, revision_id, report_id = uuid4(), uuid4(), uuid4()
            connection.execute("INSERT INTO m8_results VALUES(%s,%s)", (result_id, cycle["id"]))
            connection.execute("INSERT INTO m8_result_revisions VALUES(%s,%s)", (revision_id, result_id))
            connection.execute("INSERT INTO m8_reports VALUES(%s,%s,'ready')", (report_id, revision_id))
            if index == 1:
                connection.execute("INSERT INTO m10_pipeline_runs VALUES(%s,'failed')", (cycle["id"],))
        connection.commit()
        dashboard = routes._build_admin_dashboard(connection, AdminScope(is_superadmin=True), "30d")
        metrics = {item.label: item.value for item in dashboard.metrics}
        assert metrics == {"Готовых отчётов": "1", "Прохождение оценки": "Завершено 2 из 3"}
        assert dashboard.competency_average == []
        connection.rollback()

    with psycopg.connect(test_database_url) as connection:
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        connection.commit()
