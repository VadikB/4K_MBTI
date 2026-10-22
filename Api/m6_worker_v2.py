"""Dispatcher preserving legacy 1.0.0 and executing current M6 mechanisms."""
import logging
import threading

from Api.assessment_configuration import definition_checksum
from Api.m6_repository import claim, finish
from Api.m6_evidence_service_v2 import evaluate

_stop = threading.Event()
_thread = None
_lock = threading.Lock()


def run_request(request_id, *, connection_factory=None, gateway=None):
    if connection_factory is None:
        from Api.database import get_connection
        connection_factory = get_connection
    with connection_factory() as connection:
        job = claim(connection, request_id)
        connection.commit()
    if job is None:
        return
    trace = {}
    try:
        if definition_checksum(job["input_json"]) != job["input_hash"]:
            raise ValueError("CHECKSUM_MISMATCH")
        output, trace = evaluate(job["input_json"], job["mechanism_json"], job["mechanism_hash"], gateway=gateway)
    except Exception as exc:
        output = None
        trace = getattr(exc, "ai_trace", {})
        error = type(exc).__name__
    else:
        error = None
    with connection_factory() as connection:
        finish(connection, job, output, trace, error)
        connection.commit()


def recover_pending(connection_factory=None):
    if connection_factory is None:
        from Api.database import get_connection
        connection_factory = get_connection
    with connection_factory() as connection:
        evidence = connection.execute("""SELECT id,mechanism_json->>'ref' AS mechanism_ref
            FROM m6_processing_requests WHERE status='queued' OR
            (status='running' AND lease_expires_at<=NOW()) ORDER BY created_at LIMIT 1""").fetchone()
        assessment = connection.execute("""SELECT id,mechanism_json->>'ref' AS mechanism_ref
            FROM m6_assessment_requests WHERE status='queued' OR
            (status='running' AND lease_expires_at<=NOW()) ORDER BY created_at LIMIT 1""").fetchone()
    if evidence:
        if evidence["mechanism_ref"] == "m6_evidence/1.0.1":
            run_request(evidence["id"], connection_factory=connection_factory)
        else:
            from Api.m6_worker import run_request as run_legacy
            run_legacy(evidence["id"], connection_factory=connection_factory)
        return True
    if assessment:
        if assessment["mechanism_ref"] == "m6_indicator_assessment/1.0.1":
            from Api.m6_assessment_worker_v2 import run_request as run_assessment
        else:
            from Api.m6_assessment_worker import run_request as run_assessment
        run_assessment(assessment["id"], connection_factory=connection_factory)
        return True
    return False


def _poll():
    while not _stop.is_set():
        try:
            if recover_pending():
                continue
        except Exception as exc:
            logging.getLogger(__name__).warning("M6 worker technical failure: %s", type(exc).__name__)
        _stop.wait(2)


def start():
    global _thread
    with _lock:
        if _thread and _thread.is_alive():
            return
        _stop.clear()
        _thread = threading.Thread(target=_poll, name="m6-current-worker", daemon=True)
        _thread.start()


def stop():
    _stop.set()
    if _thread:
        _thread.join(timeout=5)
