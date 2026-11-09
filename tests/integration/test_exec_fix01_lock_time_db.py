"""Admission observes wall time after a real PG lock wait, not transaction NOW."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
import pytest
from Api import m7_clarification
from tests.integration.test_exec_fix01_clarification_db import current, database, _resolve, _request

pytestmark=pytest.mark.integration


def test_answer_waiting_on_cycle_cannot_use_pre_expiry_transaction_time(current):
    request=_request(_resolve(current))
    locked, started=Event(), Event()
    def boundary():
        with current['factory']() as c:
            c.execute('SELECT id FROM m5_cycles WHERE id=%s FOR UPDATE',(current['cycle_db'],))
            c.execute("UPDATE m5_cycle_time_intervals SET ended_at=started_at WHERE cycle_db_id=%s AND interval_type='collecting'",(current['cycle_db'],))
            c.execute("""UPDATE m5_cycle_time_intervals SET started_at=clock_timestamp()-INTERVAL '7199 seconds',ended_at=NULL
                WHERE id=(SELECT MAX(id) FROM m5_cycle_time_intervals WHERE cycle_db_id=%s AND interval_type='collecting')""",(current['cycle_db'],))
            locked.set();assert started.wait(timeout=5)
            time.sleep(1.2)
            c.commit()
    def answer():
        assert locked.wait(timeout=5)
        with current['factory']() as c:
            c.execute('SELECT NOW()')
            started.set()
            with pytest.raises(ValueError,match='TIME|CLOSED'):
                m7_clarification.answer(c,**request)
            c.rollback()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(boundary);b=pool.submit(answer)
        a.result(timeout=10);b.result(timeout=10)
    with current['factory']() as c:
        assert not c.execute('SELECT 1 FROM m7_clarification_responses').fetchone()
        assert not c.execute('SELECT 1 FROM m5_cycle_time_intervals WHERE ended_at<started_at').fetchone()
