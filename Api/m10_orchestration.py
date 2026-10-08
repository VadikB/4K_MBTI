from __future__ import annotations

import json
import logging
import threading
from uuid import UUID

from Api import m6_cycle_aggregation_repository
from Api import m7_clarification, m7_completion, m8_results
from Api.database import get_connection
from Api.m6_admission import VERSION as ADMISSION_VERSION
from Api.m6_assessment_package import load_mechanism as load_assessment_mechanism
from Api.m10_input_resolver import resolve
from Api.m10_product_queue import enqueue_assessment, enqueue_evidence
from Api.m6_package import load_mechanism as load_evidence_mechanism

logger = logging.getLogger(__name__)
PROCESSING_CONTRACT_VERSION = "m10-processing-recovery/1.0.0"
_stop = threading.Event()
_thread = None


def ensure_schema(connection) -> None:
    # The frozen M6 QA package keeps its synthetic-only enqueue contract intact.
    # Product requests are enabled here as a separate adapter-owned migration.
    connection.execute("ALTER TABLE IF EXISTS m6_processing_requests DROP CONSTRAINT IF EXISTS m6_processing_requests_synthetic_confirmed_check")
    connection.execute("ALTER TABLE IF EXISTS m6_assessment_requests DROP CONSTRAINT IF EXISTS m6_assessment_requests_synthetic_confirmed_check")
    connection.execute("""CREATE TABLE IF NOT EXISTS m10_pipeline_runs(
        cycle_db_id BIGINT PRIMARY KEY REFERENCES m5_cycles(id), status TEXT NOT NULL,
        stage TEXT NOT NULL, error_code TEXT, latest_calculation_id UUID,
        latest_results_revision_id UUID, latest_report_id UUID,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m10_pipeline_revisions(
        id BIGSERIAL PRIMARY KEY, cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id), revision_no INTEGER NOT NULL,
        status TEXT NOT NULL, stage TEXT NOT NULL, error_code TEXT, calculation_id UUID,
        results_revision_id UUID, report_id UUID, contract_version TEXT NOT NULL,
        origin TEXT NOT NULL, created_by BIGINT REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(cycle_db_id,revision_no))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m10_processing_recoveries(
        id UUID PRIMARY KEY, cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),
        idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL, status TEXT NOT NULL,
        frozen_input_json JSONB NOT NULL, frozen_input_checksum TEXT NOT NULL,
        source_pipeline_revision_no INTEGER NOT NULL, mechanism_version TEXT NOT NULL,
        created_by BIGINT NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, calculation_id UUID,
        results_revision_id UUID, report_id UUID, error_code TEXT,
        UNIQUE(created_by,idempotency_key))""")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_m10_processing_history_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'M10 processing history is immutable'; END; $$ LANGUAGE plpgsql""")
    connection.execute("DROP TRIGGER IF EXISTS immutable_m10_pipeline_revisions ON m10_pipeline_revisions")
    connection.execute("CREATE TRIGGER immutable_m10_pipeline_revisions BEFORE UPDATE OR DELETE ON m10_pipeline_revisions "
                       "FOR EACH ROW EXECUTE FUNCTION prevent_m10_processing_history_change()")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_finished_m10_recovery_change() RETURNS trigger AS $$
        BEGIN IF TG_OP='DELETE' OR OLD.status IN ('succeeded','failed') THEN
          RAISE EXCEPTION 'Finished M10 recovery is immutable'; END IF;
          IF NEW.cycle_db_id IS DISTINCT FROM OLD.cycle_db_id
             OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
             OR NEW.request_hash IS DISTINCT FROM OLD.request_hash
             OR NEW.frozen_input_json IS DISTINCT FROM OLD.frozen_input_json
             OR NEW.frozen_input_checksum IS DISTINCT FROM OLD.frozen_input_checksum
             OR NEW.source_pipeline_revision_no IS DISTINCT FROM OLD.source_pipeline_revision_no
             OR NEW.mechanism_version IS DISTINCT FROM OLD.mechanism_version
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'M10 recovery frozen input is immutable'; END IF;
          RETURN NEW; END; $$ LANGUAGE plpgsql""")
    connection.execute("DROP TRIGGER IF EXISTS immutable_m10_processing_recoveries ON m10_processing_recoveries")
    connection.execute("""CREATE TRIGGER immutable_m10_processing_recoveries BEFORE UPDATE OR DELETE
        ON m10_processing_recoveries FOR EACH ROW EXECUTE FUNCTION prevent_finished_m10_recovery_change()""")


def _set_state(connection, cycle_db_id: int, *, status: str, stage: str, error: str | None = None,
               calculation_id=None, results_revision_id=None, report_id=None,
               origin: str = "orchestration", created_by: int | None = None) -> None:
    connection.execute("SELECT id FROM m5_cycles WHERE id=%s FOR UPDATE", (cycle_db_id,)).fetchone()
    connection.execute("""INSERT INTO m10_pipeline_runs
        (cycle_db_id,status,stage,error_code,latest_calculation_id,latest_results_revision_id,latest_report_id)
        VALUES(%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(cycle_db_id) DO UPDATE SET status=EXCLUDED.status,stage=EXCLUDED.stage,
          error_code=EXCLUDED.error_code,
          latest_calculation_id=COALESCE(EXCLUDED.latest_calculation_id,m10_pipeline_runs.latest_calculation_id),
          latest_results_revision_id=COALESCE(EXCLUDED.latest_results_revision_id,m10_pipeline_runs.latest_results_revision_id),
          latest_report_id=COALESCE(EXCLUDED.latest_report_id,m10_pipeline_runs.latest_report_id),updated_at=NOW()""",
        (cycle_db_id,status,stage,error,calculation_id,results_revision_id,report_id))
    revision_no = connection.execute(
        "SELECT COALESCE(MAX(revision_no),0)+1 AS n FROM m10_pipeline_revisions WHERE cycle_db_id=%s",
        (cycle_db_id,),
    ).fetchone()["n"]
    connection.execute("""INSERT INTO m10_pipeline_revisions
        (cycle_db_id,revision_no,status,stage,error_code,calculation_id,results_revision_id,report_id,
         contract_version,origin,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (cycle_db_id, revision_no, status, stage, error, calculation_id, results_revision_id,
         report_id, PROCESSING_CONTRACT_VERSION, origin, created_by))


def _processing_failure(calculation: dict) -> dict | None:
    failed = [decision for decision in calculation["c56"].get("admissions", [])
              if decision.get("processing_status") == "failed"]
    if not failed:
        return None
    codes = sorted({item.get("reason_code") or item.get("joint", {}).get("reason_code")
                    or "M6_ADMISSION_PROCESSING_FAILED" for item in failed})
    return {"code": "M6_ADMISSION_PROCESSING_FAILED", "reason_codes": codes,
            "indicator_ids": sorted(item["indicator_id"] for item in failed)}


def enqueue_handoff(connection, *, handoff_id: str, created_by: int) -> dict:
    as_db_id, material = resolve(connection, handoff_id)
    request = enqueue_evidence(
        connection, as_db_id=as_db_id, handoff_id=handoff_id, key=f"product-evidence:{handoff_id}",
        material=material, mechanism=load_evidence_mechanism("m6_evidence/1.0.0"), created_by=created_by,
    )
    cycle = connection.execute("SELECT cycle_db_id FROM m5_assessment_situations WHERE id=%s", (as_db_id,)).fetchone()
    _set_state(connection, int(cycle["cycle_db_id"]), status="processing", stage="evidence_queued")
    return dict(request)


def _queue_outbox(connection) -> bool:
    row = connection.execute("""SELECT o.*,c.created_by,c.id AS cycle_db_id FROM m7_finalization_outbox o
        JOIN m5_assessment_situations s ON s.id=o.assessment_situation_db_id
        JOIN m5_cycles c ON c.id=s.cycle_db_id
        WHERE o.status='pending' AND c.usage_scope='assessment' ORDER BY o.created_at
        FOR UPDATE OF o SKIP LOCKED LIMIT 1""").fetchone()
    if not row:
        return False
    try:
        request = enqueue_handoff(connection, handoff_id=str(row["handoff_id"]), created_by=int(row["created_by"]))
    except Exception as exc:
        connection.execute("UPDATE m7_finalization_outbox SET status='failed' WHERE assessment_situation_db_id=%s",
                           (row["assessment_situation_db_id"],))
        _set_state(connection, int(row["cycle_db_id"]), status="failed", stage="evidence_enqueue", error=type(exc).__name__)
        raise
    connection.execute("UPDATE m7_finalization_outbox SET status='queued',m6_request_id=%s WHERE assessment_situation_db_id=%s",
                       (request["id"], row["assessment_situation_db_id"]))
    return True


def _queue_assessment(connection) -> bool:
    row = connection.execute("""SELECT a.id,a.as_db_id,r.created_by,s.cycle_db_id FROM m6_analysis_revisions a
        JOIN m6_processing_requests r ON r.id=a.request_id
        JOIN m5_assessment_situations s ON s.id=a.as_db_id JOIN m5_cycles c ON c.id=s.cycle_db_id
        WHERE c.usage_scope='assessment' AND NOT EXISTS(
          SELECT 1 FROM m6_assessment_requests q WHERE q.evidence_revision_id=a.id)
        ORDER BY a.created_at FOR UPDATE OF s SKIP LOCKED LIMIT 1""").fetchone()
    if not row:
        return False
    request = enqueue_assessment(
        connection, evidence_revision_id=str(row["id"]), key=f"product-assessment:{row['id']}",
        mechanism=load_assessment_mechanism("m6_indicator_assessment/1.0.0"), created_by=int(row["created_by"]),
    )
    _set_state(connection, int(row["cycle_db_id"]), status="processing", stage="assessment_queued")
    return bool(request)


def _clarify_interim(connection, gateway=None) -> bool:
    if gateway is None:
        from Api.m10_test_gateway import acceptance_fixture, BrowserAcceptanceGateway
        if acceptance_fixture():
            gateway=BrowserAcceptanceGateway()
    row = connection.execute("""SELECT c.id,c.as_db_id,s.cycle_db_id,cy.created_by FROM m6_c54_revisions c
        JOIN m5_assessment_situations s ON s.id=c.as_db_id JOIN m5_cycles cy ON cy.id=s.cycle_db_id
        WHERE c.mode='interim' AND cy.usage_scope='assessment' AND NOT EXISTS(
          SELECT 1 FROM m7_clarification_decisions d WHERE d.c54_revision_id=c.id)
        ORDER BY c.created_at FOR UPDATE OF s SKIP LOCKED LIMIT 1""").fetchone()
    if not row:
        return False
    decision = m7_clarification.decide(connection, c54_revision_id=str(row["id"]),
        key=f"product-clarification:{row['id']}", created_by=int(row["created_by"]), gateway=gateway)
    if decision["status"] == "ASK":
        m7_clarification.present(connection, decision_id=str(decision["id"]), expected_c54_revision_id=str(row["id"]))
    stage = "clarification_waiting" if decision["status"] == "ASK" else "clarification_resolved"
    status = "failed" if decision["status"] == "WAIT_TECHNICAL" else "processing"
    _set_state(connection, int(row["cycle_db_id"]), status=status, stage=stage,
               error="M7_QUESTION_GENERATION_FAILED" if status == "failed" else None)
    return True


def _finalize_cycle(connection, gateway=None) -> bool:
    if gateway is None:
        from Api.m10_test_gateway import enabled, BrowserAcceptanceGateway
        if enabled():
            gateway = BrowserAcceptanceGateway()
    row = connection.execute("""SELECT c.id,c.cycle_id,c.created_by FROM m5_cycles c
        WHERE c.usage_scope='assessment' AND c.status IN('collection_closed','calculation_pending')
          AND NOT EXISTS(SELECT 1 FROM m7_finalization_outbox o JOIN m5_assessment_situations s ON s.id=o.assessment_situation_db_id
              LEFT JOIN m6_processing_requests e ON e.id=o.m6_request_id
              LEFT JOIN m6_analysis_revisions ar ON ar.request_id=e.id
              LEFT JOIN m6_assessment_requests q ON q.evidence_revision_id=ar.id
              WHERE s.cycle_db_id=c.id AND COALESCE(q.status,'missing')<>'succeeded')
        ORDER BY c.updated_at FOR UPDATE OF c SKIP LOCKED LIMIT 1""").fetchone()
    if not row:
        return False
    cycle_id = str(row["cycle_id"])
    c46 = m7_completion.read_c46(connection, cycle_id)
    calculation = m6_cycle_aggregation_repository.create_substantive(
        connection, cycle_id=cycle_id,
        key=f"product-calculation:{c46['composition_checksum']}:{ADMISSION_VERSION}",
        expected_composition_checksum=c46["composition_checksum"],
        created_by=int(row["created_by"]), gateway=gateway,
    )
    results = m8_results.create_results(connection, cycle_id=cycle_id, calculation_id=calculation["id"],
        key=f"product-results:{calculation['id']}", target_profile=None, created_by=int(row["created_by"]))
    report = m8_results.create_report(connection, results_revision_id=results["revision_id"], audience="assessee",
        key="product-report:assessee", target_profile=None, created_by=int(row["created_by"]))
    failure = _processing_failure(calculation)
    _set_state(connection, int(row["id"]), status="failed" if failure else "ready",
               stage="admission_processing_failed" if failure else "report_ready",
               error=failure["code"] if failure else None, calculation_id=UUID(calculation["id"]),
               results_revision_id=UUID(results["revision_id"]), report_id=UUID(report["id"]),
               created_by=int(row["created_by"]))
    return True


def request_processing_recovery(connection, *, cycle_id: str, idempotency_key: str, created_by: int) -> dict:
    from Api.m5_case_runtime import checksum
    from uuid import uuid4
    cycle = connection.execute("""SELECT c.*,p.revision_no AS pipeline_revision_no,p.status AS pipeline_status,
        p.stage AS pipeline_stage FROM m5_cycles c
        JOIN m10_pipeline_runs run ON run.cycle_db_id=c.id
        JOIN m10_pipeline_revisions p ON p.cycle_db_id=c.id
        WHERE c.cycle_id=%s ORDER BY p.revision_no DESC LIMIT 1 FOR UPDATE OF c""", (UUID(cycle_id),)).fetchone()
    prior = connection.execute("SELECT * FROM m10_processing_recoveries WHERE created_by=%s AND idempotency_key=%s",
                               (created_by, idempotency_key)).fetchone()
    if prior:
        if not cycle or int(prior["cycle_db_id"]) != int(cycle["id"]):
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return dict(prior)
    if (not cycle or cycle["pipeline_status"] != "failed"
            or cycle["pipeline_stage"] not in {"admission_processing_failed", "recovery_failed"}):
        raise ValueError("M10_PROCESSING_RECOVERY_NOT_AVAILABLE")
    frozen = {"cycle_id": cycle_id, "catalog_ref": cycle["catalog_ref_json"],
              "profile_ref": cycle["profile_ref_json"], "target_set_checksum": cycle["target_set_checksum"],
              "collection_closed_at": cycle["collection_closed_at"] and cycle["collection_closed_at"].isoformat(),
              "source_pipeline_revision_no": cycle["pipeline_revision_no"]}
    request_hash = checksum(frozen)
    recovery_id = uuid4()
    row = connection.execute("""INSERT INTO m10_processing_recoveries
        (id,cycle_db_id,idempotency_key,request_hash,status,frozen_input_json,frozen_input_checksum,
         source_pipeline_revision_no,mechanism_version,created_by)
        VALUES(%s,%s,%s,%s,'queued',%s::jsonb,%s,%s,%s,%s) RETURNING *""",
        (recovery_id, cycle["id"], idempotency_key, request_hash, json.dumps(frozen), checksum(frozen),
         cycle["pipeline_revision_no"], ADMISSION_VERSION, created_by)).fetchone()
    _set_state(connection, int(cycle["id"]), status="processing", stage="recovery_queued",
               origin="authorized_recovery", created_by=created_by)
    return dict(row)


def _process_recovery(connection, gateway=None) -> bool:
    from Api.m5_case_runtime import checksum
    row = connection.execute("""SELECT r.*,c.cycle_id,c.catalog_ref_json,c.profile_ref_json,c.target_set_checksum,
        c.collection_closed_at FROM m10_processing_recoveries r JOIN m5_cycles c ON c.id=r.cycle_db_id
        WHERE r.status='queued' ORDER BY r.created_at FOR UPDATE OF r SKIP LOCKED LIMIT 1""").fetchone()
    if not row:
        return False
    frozen = dict(row["frozen_input_json"])
    actual = {"cycle_id": str(row["cycle_id"]), "catalog_ref": row["catalog_ref_json"],
              "profile_ref": row["profile_ref_json"], "target_set_checksum": row["target_set_checksum"],
              "collection_closed_at": row["collection_closed_at"] and row["collection_closed_at"].isoformat(),
              "source_pipeline_revision_no": row["source_pipeline_revision_no"]}
    if checksum(frozen) != row["frozen_input_checksum"] or actual != frozen:
        raise ValueError("M10_RECOVERY_FROZEN_INPUT_MISMATCH")
    connection.execute("UPDATE m10_processing_recoveries SET status='running',started_at=NOW() WHERE id=%s", (row["id"],))
    try:
        c46 = m7_completion.read_c46(connection, str(row["cycle_id"]))
        calculation = m6_cycle_aggregation_repository.create_substantive(
            connection, cycle_id=str(row["cycle_id"]),
            key=f"processing-recovery:{row['id']}:{ADMISSION_VERSION}",
            expected_composition_checksum=c46["composition_checksum"], created_by=int(row["created_by"]), gateway=gateway)
        results = m8_results.create_results(connection, cycle_id=str(row["cycle_id"]), calculation_id=calculation["id"],
            key=f"processing-recovery-results:{row['id']}", target_profile=None, created_by=int(row["created_by"]))
        report = m8_results.create_report(connection, results_revision_id=results["revision_id"], audience="assessee",
            key=f"processing-recovery-report:{row['id']}", target_profile=None, created_by=int(row["created_by"]))
        failure = _processing_failure(calculation)
        status = "failed" if failure else "succeeded"
        connection.execute("""UPDATE m10_processing_recoveries SET status=%s,finished_at=NOW(),calculation_id=%s,
            results_revision_id=%s,report_id=%s,error_code=%s WHERE id=%s""",
            (status, calculation["id"], results["revision_id"], report["id"],
             failure["code"] if failure else None, row["id"]))
        _set_state(connection, int(row["cycle_db_id"]), status="failed" if failure else "ready",
                   stage="recovery_failed" if failure else "recovered_report_ready",
                   error=failure["code"] if failure else None, calculation_id=UUID(calculation["id"]),
                   results_revision_id=UUID(results["revision_id"]), report_id=UUID(report["id"]),
                   origin="authorized_recovery", created_by=int(row["created_by"]))
    except Exception as exc:
        connection.execute("""UPDATE m10_processing_recoveries SET status='failed',finished_at=NOW(),error_code=%s
            WHERE id=%s""", (type(exc).__name__, row["id"]))
        _set_state(connection, int(row["cycle_db_id"]), status="failed", stage="recovery_failed",
                   error="M10_PROCESSING_RECOVERY_FAILED", origin="authorized_recovery",
                   created_by=int(row["created_by"]))
    return True


def _propagate_failure(connection) -> bool:
    row = connection.execute("""SELECT c.id,
        CASE WHEN e.status='failed' THEN 'M6_EVIDENCE_FAILED' ELSE 'M6_ASSESSMENT_FAILED' END AS error
        FROM m5_cycles c JOIN m5_assessment_situations s ON s.cycle_db_id=c.id
        LEFT JOIN m6_processing_requests e ON e.as_db_id=s.id
        LEFT JOIN m6_analysis_revisions a ON a.request_id=e.id
        LEFT JOIN m6_assessment_requests q ON q.evidence_revision_id=a.id
        WHERE c.usage_scope='assessment' AND (e.status='failed' OR q.status='failed')
          AND NOT EXISTS(SELECT 1 FROM m10_pipeline_runs p WHERE p.cycle_db_id=c.id AND p.status='failed')
        ORDER BY c.id LIMIT 1""").fetchone()
    if not row:
        return False
    _set_state(connection, int(row["id"]), status="failed", stage="processing_failed", error=row["error"])
    return True


def advance_once(*, gateway=None, connection_factory=None) -> bool:
    factory = connection_factory or get_connection
    with factory() as connection:
        try:
            changed = (_propagate_failure(connection) or _process_recovery(connection, gateway=gateway)
                       or _queue_outbox(connection) or _queue_assessment(connection)
                       or _clarify_interim(connection, gateway=gateway) or _finalize_cycle(connection, gateway=gateway))
            connection.commit()
            return changed
        except Exception:
            connection.rollback()
            raise


def _run_browser_test_gateway_once() -> bool:
    from Api.m10_test_gateway import BrowserAcceptanceGateway, enabled
    if not enabled():
        return False
    with get_connection() as connection:
        evidence = connection.execute("SELECT id FROM m6_processing_requests WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
        assessment = connection.execute("SELECT id FROM m6_assessment_requests WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
    gateway = BrowserAcceptanceGateway()
    if evidence:
        from Api.m6_worker import run_request
        run_request(evidence["id"], gateway=gateway)
        return True
    if assessment:
        from Api.m6_assessment_worker import run_request
        run_request(assessment["id"], gateway=gateway)
        return True
    return False


def _loop() -> None:
    while not _stop.wait(2):
        try:
            while advance_once() or _run_browser_test_gateway_once():
                continue
        except Exception:
            logger.exception("Task 10 product orchestration failed")


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="m10-product-orchestration", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
    if _thread:
        _thread.join(timeout=5)
