from __future__ import annotations

import json
from copy import deepcopy
from uuid import UUID


ACCESS_CONTRACT_VERSION = "m8-report-access/1.0.0"


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_report_access_revisions (
        id BIGSERIAL PRIMARY KEY,
        organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
        assignment_ref TEXT NOT NULL,
        questionnaire_revision_id BIGINT NOT NULL REFERENCES questionnaire_response_revisions(id) ON DELETE RESTRICT,
        revision_no INTEGER NOT NULL,
        participant_required BOOLEAN NOT NULL DEFAULT TRUE CHECK (participant_required),
        customer_enabled BOOLEAN NOT NULL,
        source_author TEXT NOT NULL,
        confirmed_by_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        confirmed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        contract_version TEXT NOT NULL,
        UNIQUE(organization_id,assignment_ref,revision_no), UNIQUE(questionnaire_revision_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_report_access_recipients (
        access_revision_id BIGINT NOT NULL REFERENCES m8_report_access_revisions(id) ON DELETE RESTRICT,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        PRIMARY KEY(access_revision_id,user_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_cycle_report_access (
        cycle_db_id BIGINT PRIMARY KEY REFERENCES m5_cycles(id) ON DELETE RESTRICT,
        access_revision_id BIGINT REFERENCES m8_report_access_revisions(id) ON DELETE RESTRICT,
        participant_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
        assignment_ref TEXT,
        frozen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        contract_version TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_cycle_report_recipients (
        cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id) ON DELETE RESTRICT,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        PRIMARY KEY(cycle_db_id,user_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_report_access_events (
        id BIGSERIAL PRIMARY KEY,
        report_id UUID NOT NULL REFERENCES m8_reports(id) ON DELETE RESTRICT,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        channel TEXT NOT NULL CHECK (channel IN ('api','pdf')),
        accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        contract_version TEXT NOT NULL)""")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_m8_report_access_history_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'M8 report access history is immutable'; END; $$ LANGUAGE plpgsql""")
    for table in ("m8_report_access_revisions", "m8_report_access_recipients",
                  "m8_cycle_report_access", "m8_cycle_report_recipients", "m8_report_access_events"):
        trigger = f"immutable_{table}"
        connection.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        connection.execute(f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
                           "FOR EACH ROW EXECUTE FUNCTION prevent_m8_report_access_history_change()")


def create_revision(connection, *, questionnaire_revision_id: int, organization_id: int,
                    assignment_ref: str, recipient_user_ids: list[int], source_author: str,
                    confirmed_by: int) -> dict:
    recipients = sorted(set(int(value) for value in recipient_user_ids))
    if recipients:
        rows = connection.execute("""SELECT om.user_id FROM organization_memberships om
            JOIN organizations o ON o.id=om.organization_id
            WHERE om.organization_id=%s AND om.role='admin' AND o.is_active=TRUE
              AND om.user_id=ANY(%s)""", (organization_id, recipients)).fetchall()
        if {int(row["user_id"]) for row in rows} != set(recipients):
            raise ValueError("REPORT_RECIPIENT_SCOPE_CONFLICT")
    revision_no = connection.execute("""SELECT COALESCE(MAX(revision_no),0)+1 AS value
        FROM m8_report_access_revisions WHERE organization_id=%s AND assignment_ref=%s""",
        (organization_id, assignment_ref)).fetchone()["value"]
    row = connection.execute("""INSERT INTO m8_report_access_revisions(
        organization_id,assignment_ref,questionnaire_revision_id,revision_no,customer_enabled,
        source_author,confirmed_by_user_id,contract_version)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
        (organization_id, assignment_ref, questionnaire_revision_id, revision_no, bool(recipients),
         source_author, confirmed_by, ACCESS_CONTRACT_VERSION)).fetchone()
    for user_id in recipients:
        connection.execute("INSERT INTO m8_report_access_recipients(access_revision_id,user_id) VALUES(%s,%s)",
                           (row["id"], user_id))
    return {**dict(row), "recipient_user_ids": recipients}


def freeze_for_cycle(connection, *, cycle_db_id: int, personalized_profile_id: int,
                     participant_user_id: int, organization_id: int) -> dict:
    confirmation = connection.execute("""SELECT assignment_ref,questionnaire_revision_id
        FROM participant_acquaintance_confirmations
        WHERE personalized_profile_id=%s AND user_id=%s AND organization_id=%s
        ORDER BY confirmed_at DESC,id DESC LIMIT 1""",
        (personalized_profile_id, participant_user_id, organization_id)).fetchone()
    access = None
    if confirmation and confirmation.get("questionnaire_revision_id"):
        access = connection.execute("""SELECT * FROM m8_report_access_revisions
            WHERE questionnaire_revision_id=%s""", (confirmation["questionnaire_revision_id"],)).fetchone()
    row = connection.execute("""INSERT INTO m8_cycle_report_access(
        cycle_db_id,access_revision_id,participant_user_id,organization_id,assignment_ref,contract_version)
        VALUES(%s,%s,%s,%s,%s,%s) RETURNING *""",
        (cycle_db_id, access["id"] if access else None, participant_user_id, organization_id,
         confirmation["assignment_ref"] if confirmation else None, ACCESS_CONTRACT_VERSION)).fetchone()
    if access and access["customer_enabled"]:
        recipients = connection.execute("SELECT user_id FROM m8_report_access_recipients WHERE access_revision_id=%s",
                                        (access["id"],)).fetchall()
        for recipient in recipients:
            connection.execute("INSERT INTO m8_cycle_report_recipients(cycle_db_id,user_id) VALUES(%s,%s)",
                               (cycle_db_id, recipient["user_id"]))
    return dict(row)


def customer_can_read_report(connection, *, report_id: str, user_id: int) -> bool:
    row = connection.execute("""SELECT 1 FROM m8_reports p
        JOIN m8_result_revisions rr ON rr.id=p.result_revision_id
        JOIN m8_results r ON r.id=rr.results_id
        JOIN m8_cycle_report_access access ON access.cycle_db_id=r.cycle_db_id
        JOIN m8_cycle_report_recipients recipient ON recipient.cycle_db_id=r.cycle_db_id
        JOIN organization_memberships membership ON membership.organization_id=access.organization_id
            AND membership.user_id=recipient.user_id AND membership.role='admin'
        JOIN organizations organization ON organization.id=access.organization_id AND organization.is_active=TRUE
        WHERE p.id=%s AND p.audience='assessee' AND recipient.user_id=%s""",
        (UUID(str(report_id)), user_id)).fetchone()
    return bool(row)


def record_access(connection, *, report_id: str, user_id: int, channel: str) -> None:
    if channel not in {"api", "pdf"}:
        raise ValueError("REPORT_ACCESS_CHANNEL_INVALID")
    connection.execute("""INSERT INTO m8_report_access_events(report_id,user_id,channel,contract_version)
        VALUES(%s,%s,%s,%s)""", (UUID(str(report_id)), user_id, channel, ACCESS_CONTRACT_VERSION))


def list_customer_reports(connection, *, user_id: int) -> list[dict]:
    rows = connection.execute("""SELECT DISTINCT ON (r.cycle_db_id)
        p.id AS report_id,p.revision_no,p.created_at,c.cycle_id,c.owner_user_id,
        u.full_name,u.email,rr.revision_no AS results_revision_no
        FROM m8_cycle_report_recipients recipient
        JOIN m8_cycle_report_access access ON access.cycle_db_id=recipient.cycle_db_id
        JOIN organization_memberships membership ON membership.organization_id=access.organization_id
            AND membership.user_id=recipient.user_id AND membership.role='admin'
        JOIN organizations organization ON organization.id=access.organization_id AND organization.is_active=TRUE
        JOIN m5_cycles c ON c.id=access.cycle_db_id
        JOIN users u ON u.id=c.owner_user_id
        JOIN m8_results r ON r.cycle_db_id=c.id
        JOIN m8_result_revisions rr ON rr.results_id=r.id
        JOIN m8_reports p ON p.result_revision_id=rr.id AND p.audience='assessee'
        WHERE recipient.user_id=%s
        ORDER BY r.cycle_db_id,rr.revision_no DESC,p.revision_no DESC""", (user_id,)).fetchall()
    return [{key: (str(value) if key in {"report_id", "cycle_id"} else value)
             for key, value in dict(row).items()} for row in rows]


def customer_projection(report: dict) -> dict:
    source = report["c67"]
    allowed = ("schema_version", "contract", "message_version", "results_id", "results_revision_id",
               "results_revision_no", "cycle_id", "report_id", "report_revision_no", "template_version",
               "skills", "competencies", "coverage", "confidence", "reliability", "limitations",
               "partial_result", "processing", "descriptive", "report_mechanism", "test_result")
    c67 = {key: deepcopy(source[key]) for key in allowed if key in source}
    c67["audience"] = "customer"
    c67["disclosure"] = "summary_with_coverage"
    for skill in c67.get("skills", []):
        skill.pop("components", None)
    return {**report, "audience": "customer", "c67": c67}
