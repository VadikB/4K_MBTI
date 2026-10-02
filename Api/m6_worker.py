"""Одна попытка durable request; повтор вызова восстанавливает истёкший lease."""
from Api.assessment_configuration import definition_checksum
from Api.m6_repository import claim, finish
from Api.m6_evidence_service import evaluate


def run_request(request_id, *, connection_factory=None, gateway=None):
    if connection_factory is None:
        from Api.database import get_connection
        connection_factory=get_connection
    with connection_factory() as connection:
        job=claim(connection,request_id)
        connection.commit()
    if job is None: return
    trace={}
    try:
        if definition_checksum(job['input_json'])!=job['input_hash']:
            raise ValueError('CHECKSUM_MISMATCH')
        output,trace=evaluate(job['input_json'],job['mechanism_json'],job['mechanism_hash'],gateway=gateway)
    except Exception as exc:
        output=None; trace=getattr(exc,'ai_trace',{})
        error=type(exc).__name__  # no provider text / raw input in status response
    else:
        error=None
    with connection_factory() as connection:
        finish(connection,job,output,trace,error)
        connection.commit()


# Only explicitly enqueued, synthetic-confirmed QA requests are polled.
import logging
import threading

_stop = threading.Event()
_thread = None
_lock = threading.Lock()


def recover_pending(connection_factory=None):
    if connection_factory is None:
        from Api.database import get_connection
        connection_factory=get_connection
    with connection_factory() as connection:
        row=connection.execute("""SELECT id FROM m6_processing_requests
            WHERE status='queued' OR (status='running' AND lease_expires_at<=NOW())
            ORDER BY created_at LIMIT 1""").fetchone()
    if row:
        run_request(row['id'],connection_factory=connection_factory)
    return bool(row)


def _poll():
    while not _stop.is_set():
        try:
            if recover_pending(): continue
        except Exception as exc:
            logging.getLogger(__name__).warning('M6 worker technical failure: %s',type(exc).__name__)
        _stop.wait(2)


def start():
    global _thread
    with _lock:
        if _thread and _thread.is_alive():return
        _stop.clear()
        _thread=threading.Thread(target=_poll,name='m6-evidence-worker',daemon=True)
        _thread.start()


def stop():
    _stop.set()
    if _thread:_thread.join(timeout=5)
