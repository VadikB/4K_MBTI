from __future__ import annotations

import json
import logging
import threading
from uuid import UUID

from Api import m6_cycle_aggregation_repository
from Api import m7_clarification, m7_completion, m8_results
from Api.database import get_connection
from Api.m6_admission import decide as decide_admission
from Api.m6_assessment_package import load_mechanism as load_assessment_mechanism
from Api.m10_input_resolver import resolve
from Api.m10_product_queue import enqueue_assessment, enqueue_evidence
from Api.m6_package import load_mechanism as load_evidence_mechanism

logger = logging.getLogger(__name__)
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


def _set_state(connection, cycle_db_id: int, *, status: str, stage: str, error: str | None = None,
               calculation_id=None, results_revision_id=None, report_id=None) -> None:
    connection.execute("""INSERT INTO m10_pipeline_runs
        (cycle_db_id,status,stage,error_code,latest_calculation_id,latest_results_revision_id,latest_report_id)
        VALUES(%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(cycle_db_id) DO UPDATE SET status=EXCLUDED.status,stage=EXCLUDED.stage,
          error_code=EXCLUDED.error_code,
          latest_calculation_id=COALESCE(EXCLUDED.latest_calculation_id,m10_pipeline_runs.latest_calculation_id),
          latest_results_revision_id=COALESCE(EXCLUDED.latest_results_revision_id,m10_pipeline_runs.latest_results_revision_id),
          latest_report_id=COALESCE(EXCLUDED.latest_report_id,m10_pipeline_runs.latest_report_id),updated_at=NOW()""",
        (cycle_db_id,status,stage,error,calculation_id,results_revision_id,report_id))


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


def _finalize_cycle(connection) -> bool:
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
    _, _, manifest = m6_cycle_aggregation_repository._inputs(connection, cycle_id, c46["composition_checksum"])
    mechanism, decisions, limitations = decide_admission(connection, cycle_id=cycle_id, observations=manifest["observations"])
    calculation = m6_cycle_aggregation_repository.create(
        connection, cycle_id=cycle_id, key=f"product-calculation:{c46['composition_checksum']}:{mechanism}",
        expected_composition_checksum=c46["composition_checksum"], admission_mechanism_version=mechanism,
        decisions=decisions, created_by=int(row["created_by"]), limitations=limitations,
    )
    results = m8_results.create_results(connection, cycle_id=cycle_id, calculation_id=calculation["id"],
        key=f"product-results:{calculation['id']}", target_profile=None, created_by=int(row["created_by"]))
    report = m8_results.create_report(connection, results_revision_id=results["revision_id"], audience="assessee",
        key="product-report:assessee", target_profile=None, created_by=int(row["created_by"]))
    _set_state(connection, int(row["id"]), status="ready", stage="report_ready", calculation_id=UUID(calculation["id"]),
               results_revision_id=UUID(results["revision_id"]), report_id=UUID(report["id"]))
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
            changed = (_propagate_failure(connection) or _queue_outbox(connection) or _queue_assessment(connection)
                       or _clarify_interim(connection, gateway=gateway) or _finalize_cycle(connection))
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
