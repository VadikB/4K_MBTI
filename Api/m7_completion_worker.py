from __future__ import annotations
import logging,os,threading
from Api.database import get_connection
from Api.m7_completion import expire_due_cycles

logger=logging.getLogger(__name__);_stop=threading.Event();_thread=None

def _sweep_interval_seconds():
    """Keep production cadence stable; shorten only an explicitly isolated stand."""
    if os.getenv('AGENT4K_ISOLATED_STAND')!='1':return 30.0
    raw=os.getenv('M7_COMPLETION_SWEEP_SECONDS')
    if raw is None:return 30.0
    try:value=float(raw)
    except ValueError:return 30.0
    return value if 0.1<=value<=30.0 else 30.0

def sweep_once():
    with get_connection() as connection:
        result=expire_due_cycles(connection);connection.commit();return result

def _loop():
    while not _stop.wait(_sweep_interval_seconds()):
        try:sweep_once()
        except Exception:logger.exception('M7 completion expiry sweep failed')

def start():
    global _thread
    if _thread and _thread.is_alive():return
    _stop.clear()
    try:sweep_once()
    except Exception:logger.exception('M7 completion startup sweep failed')
    _thread=threading.Thread(target=_loop,name='m7-completion-worker',daemon=True);_thread.start()

def stop():
    _stop.set()
    if _thread:_thread.join(timeout=5)
