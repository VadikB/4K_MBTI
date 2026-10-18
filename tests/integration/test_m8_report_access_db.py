from __future__ import annotations

import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api import m8_report_access


pytestmark = pytest.mark.integration


def test_selected_customer_access_is_frozen_and_revocation_is_immediate(test_database_url):
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
        connection.execute("INSERT INTO users VALUES(10,'Участник','owner@example.test'),(20,'A','a@example.test'),(21,'B','b@example.test'),(22,'Новый','new@example.test')")
        connection.execute("INSERT INTO organizations VALUES(1,TRUE)")
        connection.execute("INSERT INTO organization_memberships VALUES(1,10,'member'),(1,20,'admin'),(1,21,'admin')")
        connection.execute("INSERT INTO questionnaire_response_revisions VALUES(100)")
        access = m8_report_access.create_revision(connection, questionnaire_revision_id=100, organization_id=1,
            assignment_ref="assignment-a", recipient_user_ids=[20], source_author="Заказчик", confirmed_by=20)
        connection.execute("INSERT INTO participant_acquaintance_confirmations VALUES(1,10,1,'assignment-a',100,500,NOW())")
        cycle_id, result_id, result_revision_id, report_id = uuid4(), uuid4(), uuid4(), uuid4()
        connection.execute("INSERT INTO m5_cycles VALUES(1,%s,10,1)", (cycle_id,))
        frozen = m8_report_access.freeze_for_cycle(connection, cycle_db_id=1, personalized_profile_id=500,
            participant_user_id=10, organization_id=1)
        assert frozen["access_revision_id"] == access["id"]
        connection.execute("INSERT INTO m8_results VALUES(%s,1)", (result_id,))
        connection.execute("INSERT INTO m8_result_revisions VALUES(%s,%s,1)", (result_revision_id, result_id))
        connection.execute("INSERT INTO m8_reports VALUES(%s,%s,1,'assessee',NOW())", (report_id, result_revision_id))
        assert m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=20)
        assert not m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=21)
        connection.execute("INSERT INTO organization_memberships VALUES(1,22,'admin')")
        assert not m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=22)
        connection.execute("DELETE FROM organization_memberships WHERE organization_id=1 AND user_id=20")
        assert not m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=20)
        old_cycle, old_results, old_revision, old_report = uuid4(), uuid4(), uuid4(), uuid4()
        connection.execute("INSERT INTO m5_cycles VALUES(2,%s,10,1)", (old_cycle,))
        connection.execute("INSERT INTO m8_results VALUES(%s,2)", (old_results,))
        connection.execute("INSERT INTO m8_result_revisions VALUES(%s,%s,1)", (old_revision, old_results))
        connection.execute("INSERT INTO m8_reports VALUES(%s,%s,1,'assessee',NOW())", (old_report, old_revision))
        connection.execute("INSERT INTO organization_memberships VALUES(1,20,'admin')")
        assert not m8_report_access.customer_can_read_report(connection, report_id=str(old_report), user_id=20)
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
