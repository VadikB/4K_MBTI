from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import m8_report_access, routes


pytestmark = pytest.mark.integration


def test_current_organization_administrators_read_reports_and_revocation_is_immediate(test_database_url, monkeypatch):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m8_access_pytest_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY,full_name TEXT,email TEXT)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY,is_active BOOLEAN)")
        connection.execute("CREATE TABLE organization_memberships(organization_id BIGINT,user_id BIGINT,role TEXT)")
        connection.execute("CREATE TABLE questionnaire_response_revisions(id BIGINT PRIMARY KEY)")
        connection.execute("""CREATE TABLE participant_acquaintance_confirmations(
            id BIGINT PRIMARY KEY,user_id BIGINT,organization_id BIGINT,assignment_ref TEXT,
            questionnaire_revision_id BIGINT,personalized_profile_id BIGINT,confirmed_at TIMESTAMPTZ DEFAULT NOW())""")
        connection.execute("CREATE TABLE m5_cycles(id BIGINT PRIMARY KEY,cycle_id UUID,owner_user_id BIGINT,organization_id BIGINT)")
        connection.execute("CREATE TABLE m8_results(id UUID PRIMARY KEY,cycle_db_id BIGINT)")
        connection.execute("CREATE TABLE m8_result_revisions(id UUID PRIMARY KEY,results_id UUID,revision_no INTEGER)")
        connection.execute("CREATE TABLE m8_reports(id UUID PRIMARY KEY,result_revision_id UUID,revision_no INTEGER,audience TEXT,created_at TIMESTAMPTZ DEFAULT NOW())")
        m8_report_access.ensure_schema(connection)
        connection.execute("INSERT INTO users VALUES(10,'Участник','owner@example.test'),(20,'A','a@example.test'),(21,'B','b@example.test'),(22,'Новый','new@example.test'),(23,'Чужой','foreign@example.test')")
        connection.execute("INSERT INTO organizations VALUES(1,TRUE),(2,TRUE)")
        connection.execute("INSERT INTO organization_memberships VALUES(1,10,'member'),(1,20,'admin'),(1,21,'admin'),(2,23,'admin')")
        connection.execute("INSERT INTO questionnaire_response_revisions VALUES(100)")
        access = m8_report_access.create_revision(connection, questionnaire_revision_id=100, organization_id=1,
            assignment_ref="assignment-a", source_author="Заказчик", confirmed_by=20)
        connection.execute("INSERT INTO m8_report_access_recipients VALUES(%s,20)", (access['id'],))
        connection.execute("INSERT INTO participant_acquaintance_confirmations VALUES(1,10,1,'assignment-a',100,500,NOW())")
        cycle_id, result_id, result_revision_id, report_id = uuid4(), uuid4(), uuid4(), uuid4()
        connection.execute("INSERT INTO m5_cycles VALUES(1,%s,10,1)", (cycle_id,))
        frozen = m8_report_access.freeze_for_cycle(connection, cycle_db_id=1, personalized_profile_id=500,
            participant_user_id=10, organization_id=1)
        assert frozen["access_revision_id"] == access["id"]
        connection.execute("INSERT INTO m8_cycle_report_recipients VALUES(1,20)")
        connection.execute("INSERT INTO m8_results VALUES(%s,1)", (result_id,))
        connection.execute("INSERT INTO m8_result_revisions VALUES(%s,%s,1)", (result_revision_id, result_id))
        connection.execute("INSERT INTO m8_reports VALUES(%s,%s,1,'assessee',NOW())", (report_id, result_revision_id))
        assert m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=20)
        assert m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=21)
        assert not m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=10)
        assert not m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=23)
        assert {item['report_id'] for item in m8_report_access.list_customer_reports(connection, user_id=21)} == {str(report_id)}
        assert m8_report_access.list_customer_reports(connection, user_id=23) == []
        connection.execute("INSERT INTO organization_memberships VALUES(1,22,'admin')")
        assert m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=22)
        connection.execute("DELETE FROM organization_memberships WHERE organization_id=1 AND user_id=20")
        assert not m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=20)
        old_cycle, old_results, old_revision, old_report = uuid4(), uuid4(), uuid4(), uuid4()
        connection.execute("INSERT INTO m5_cycles VALUES(2,%s,10,1)", (old_cycle,))
        connection.execute("INSERT INTO m8_results VALUES(%s,2)", (old_results,))
        connection.execute("INSERT INTO m8_result_revisions VALUES(%s,%s,1)", (old_revision, old_results))
        connection.execute("INSERT INTO m8_reports VALUES(%s,%s,1,'assessee',NOW())", (old_report, old_revision))
        connection.execute("INSERT INTO organization_memberships VALUES(1,20,'admin')")
        assert m8_report_access.customer_can_read_report(connection, report_id=str(old_report), user_id=20)
        assert {item['report_id'] for item in m8_report_access.list_customer_reports(connection, user_id=20)} == {str(report_id), str(old_report)}
        class TestConnection:
            def execute(self, *args, **kwargs):
                return connection.execute(*args, **kwargs)
            def commit(self):
                pass
        @contextmanager
        def test_connection():
            yield TestConnection()
        monkeypatch.setattr(routes, 'get_connection', test_connection)
        monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
                            lambda token: SimpleNamespace(id={'a': 20, 'b': 21, 'new': 22, 'foreign': 23}.get(token))
                            if token in {'a', 'b', 'new', 'foreign'} else None)
        report = {'id': str(report_id), 'audience': 'assessee', 'c67': {'skills': [], 'limitations': []}}
        monkeypatch.setattr(routes.m8_results, 'read_report', lambda *_: report)
        monkeypatch.setattr(routes.m8_results, 'render_pdf', lambda *_: b'%PDF-synthetic')
        app = FastAPI(); app.include_router(routes.router)
        with TestClient(app) as client:
            url = f'/users/admin/m8-access/reports/{report_id}'
            assert client.get('/users/admin/m8-access/reports').status_code == 401
            for token in ('a', 'b', 'new'):
                client.cookies.set(routes.SESSION_COOKIE_NAME, token)
                assert client.get('/users/admin/m8-access/reports').status_code == 200
                assert client.get(url).json()['audience'] == 'customer'
                assert client.get(url + '/pdf').content == b'%PDF-synthetic'
            client.cookies.set(routes.SESSION_COOKIE_NAME, 'foreign')
            assert client.get('/users/admin/m8-access/reports').json()['items'] == []
            assert client.get(url).status_code == 403
            assert client.get(url + '/pdf').status_code == 403
        connection.rollback()


def test_customer_projection_excludes_raw_and_service_material():
    report = {"id": str(uuid4()), "audience": "assessee", "c67": {
        "contract": "C-67", "cycle_id": str(uuid4()), "skills": [{"skill_id": "S1", "components": ["hidden"]}],
        "limitations": ["Ограничение"], "descriptive": {"status": "ready", "summary": ["Факт"]},
        "provenance": {"sources": ["hidden"]}, "admission_summary": [{"joint": "hidden"}],
        "profile_ref": {"secret": "hidden"}, "assessment_situations": [{"dialogue": "hidden"}],
    }}
    projected = m8_report_access.customer_projection(report)
    assert projected["audience"] == "customer"
    assert projected["c67"]["skills"] == [{"skill_id": "S1"}]
    assert projected["c67"]["descriptive"]["summary"] == ["Факт"]
    for key in ("provenance", "admission_summary", "profile_ref", "assessment_situations"):
        assert key not in projected["c67"]
