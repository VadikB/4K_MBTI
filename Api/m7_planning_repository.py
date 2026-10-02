from __future__ import annotations

import json
from uuid import UUID, uuid4

from Api.m5_case_runtime import checksum


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_cycle_plans (
        id UUID PRIMARY KEY, cycle_db_id BIGINT NOT NULL UNIQUE REFERENCES m5_cycles(id),
        profile_ref_json JSONB NOT NULL, full_target_set_json JSONB NOT NULL,
        planned_target_set_json JSONB NOT NULL, observation_requirements_json JSONB NOT NULL,
        rules_json JSONB NOT NULL, rules_checksum TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('READY','LIMITED','NO_ROUTE')),
        created_by BIGINT NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(id,cycle_db_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_plan_revisions (
        id UUID PRIMARY KEY, plan_id UUID NOT NULL, cycle_db_id BIGINT NOT NULL, revision_no INTEGER NOT NULL,
        content_json JSONB NOT NULL, content_checksum TEXT NOT NULL, reason TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        FOREIGN KEY(plan_id,cycle_db_id) REFERENCES m7_cycle_plans(id,cycle_db_id),
        UNIQUE(plan_id,revision_no), UNIQUE(id,cycle_db_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_plan_request_keys (
        created_by BIGINT NOT NULL, key TEXT NOT NULL, request_hash TEXT NOT NULL, plan_id UUID NOT NULL REFERENCES m7_cycle_plans(id),
        PRIMARY KEY(created_by,key))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_next_as_requests (
        cycle_db_id BIGINT NOT NULL, key TEXT NOT NULL, request_hash TEXT NOT NULL, decision_id UUID NOT NULL,
        PRIMARY KEY(cycle_db_id,key))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_route_decisions (
        id UUID PRIMARY KEY, cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),
        session_db_id BIGINT NOT NULL REFERENCES m5_cycle_sessions(id), plan_revision_id UUID NOT NULL,
        revision_no INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL CHECK(status IN ('SELECTED','WAITING_CURRENT_AS','NO_ADMISSIBLE_CASE','OUT_OF_TIME','COLLECTION_CLOSED')),
        trigger_json JSONB NOT NULL, facts_json JSONB NOT NULL, considered_json JSONB NOT NULL,
        selected_case_id TEXT, selected_case_version TEXT, expected_targets_json JSONB NOT NULL,
        explanation_json JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        FOREIGN KEY(plan_revision_id,cycle_db_id) REFERENCES m7_plan_revisions(id,cycle_db_id))""")
    connection.execute("""DO $$ BEGIN
        ALTER TABLE m7_next_as_requests ADD CONSTRAINT fk_m7_next_decision
            FOREIGN KEY(decision_id) REFERENCES m7_route_decisions(id);
        EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_route_assignments (
        decision_id UUID PRIMARY KEY REFERENCES m7_route_decisions(id),
        assessment_situation_db_id BIGINT NOT NULL UNIQUE REFERENCES m5_assessment_situations(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), presented_at TIMESTAMPTZ)""")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_m7_planning_history_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'M7 planning history is immutable'; END; $$ LANGUAGE plpgsql""")
    for table in ("m7_cycle_plans", "m7_plan_revisions", "m7_route_decisions"):
        connection.execute(f"DROP TRIGGER IF EXISTS immutable_m7_planning ON {table}")
        connection.execute(f"CREATE TRIGGER immutable_m7_planning BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION prevent_m7_planning_history_change()")


def save_plan(connection, *, cycle: dict, profile_ref: dict, full_targets: list, planned_targets: list,
              requirements: list, rules: dict, content: dict, created_by: int, key: str, request_hash: str) -> dict:
    existing = connection.execute("SELECT p.* FROM m7_plan_request_keys k JOIN m7_cycle_plans p ON p.id=k.plan_id WHERE k.created_by=%s AND k.key=%s",
                                  (created_by,key)).fetchone()
    if existing:
        saved_hash = connection.execute("SELECT request_hash FROM m7_plan_request_keys WHERE created_by=%s AND key=%s",(created_by,key)).fetchone()["request_hash"]
        if saved_hash != request_hash: raise ValueError("IDEMPOTENCY_CONFLICT")
        return dict(existing)
    plan_id, revision_id = uuid4(), uuid4()
    row=connection.execute("""INSERT INTO m7_cycle_plans
        (id,cycle_db_id,profile_ref_json,full_target_set_json,planned_target_set_json,observation_requirements_json,
         rules_json,rules_checksum,status,created_by) VALUES (%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s) RETURNING *""",
        (plan_id,cycle["id"],json.dumps(profile_ref),json.dumps(full_targets),json.dumps(planned_targets),json.dumps(requirements),
         json.dumps(rules),rules["snapshot_checksum"],content["status"],created_by)).fetchone()
    connection.execute("INSERT INTO m7_plan_revisions VALUES (%s,%s,%s,1,%s::jsonb,%s,'initial_plan',NOW())",
                       (revision_id,plan_id,cycle["id"],json.dumps(content,ensure_ascii=False),checksum(content)))
    connection.execute("INSERT INTO m7_plan_request_keys VALUES (%s,%s,%s,%s)",(created_by,key,request_hash,plan_id))
    return dict(row)


def read_plan(connection, cycle_id: str) -> dict:
    row=connection.execute("""SELECT p.*,c.cycle_id,c.status AS cycle_status,c.time_budget_seconds,c.calendar_window_seconds,
        r.id AS revision_id,r.revision_no,r.content_json,r.content_checksum
        FROM m7_cycle_plans p JOIN m5_cycles c ON c.id=p.cycle_db_id
        JOIN LATERAL (SELECT * FROM m7_plan_revisions WHERE plan_id=p.id ORDER BY revision_no DESC LIMIT 1) r ON TRUE
        WHERE c.cycle_id=%s""",(UUID(cycle_id),)).fetchone()
    if not row: raise ValueError("M7_PLAN_NOT_FOUND")
    if checksum(row["content_json"]) != row["content_checksum"]: raise ValueError("CHECKSUM_MISMATCH")
    return dict(row)


def existing_next(connection, cycle_db_id: int, key: str, request_hash: str):
    row=connection.execute("SELECT * FROM m7_next_as_requests WHERE cycle_db_id=%s AND key=%s",(cycle_db_id,key)).fetchone()
    if not row:return None
    if row["request_hash"] != request_hash: raise ValueError("IDEMPOTENCY_CONFLICT")
    return read_decision(connection,row["decision_id"])


def save_decision(connection, *, plan: dict, session_db_id: int, key: str, request_hash: str, decision: dict) -> dict:
    decision_id=uuid4()
    row=connection.execute("""INSERT INTO m7_route_decisions
        (id,cycle_db_id,session_db_id,plan_revision_id,status,trigger_json,facts_json,considered_json,
         selected_case_id,selected_case_version,expected_targets_json,explanation_json)
        VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb) RETURNING *""",
        (decision_id,plan["cycle_db_id"],session_db_id,plan["revision_id"],decision["status"],json.dumps(decision["trigger"]),
         json.dumps(decision["facts"]),json.dumps(decision["considered"]),decision.get("selected_case_id"),
         decision.get("selected_case_version"),json.dumps(decision.get("expected_targets",[])),json.dumps(decision["explanation"]))).fetchone()
    connection.execute("INSERT INTO m7_next_as_requests VALUES (%s,%s,%s,%s)",(plan["cycle_db_id"],key,request_hash,decision_id))
    return dict(row)


def attach_prepared_as(connection, decision_id, as_db_id: int) -> None:
    connection.execute("INSERT INTO m7_route_assignments(decision_id,assessment_situation_db_id) VALUES (%s,%s)",(decision_id,as_db_id))


def read_decision(connection, decision_id) -> dict:
    row=connection.execute("""SELECT d.*,a.assessment_situation_db_id AS assigned_as_db_id,a.presented_at AS assignment_presented_at,
        s.assessment_situation_id,s.status AS assessment_situation_status
        FROM m7_route_decisions d LEFT JOIN m7_route_assignments a ON a.decision_id=d.id
        LEFT JOIN m5_assessment_situations s ON s.id=a.assessment_situation_db_id WHERE d.id=%s""",(UUID(str(decision_id)),)).fetchone()
    if not row: raise ValueError("M7_DECISION_NOT_FOUND")
    return dict(row)
