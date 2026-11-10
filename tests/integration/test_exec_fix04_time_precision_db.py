"""EXEC-FIX-04: deterministic fractional budget checks on an owned PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from time import monotonic, sleep
import pytest

from Api import m10_orchestration, m7_clarification, m7_completion
from Api.m5_cycle_runtime import _can_continue, read_cycle
from tests.integration.test_exec_fix01_clarification_db import (
    _counts, _request, _resolve, current, http,
)
from tests.integration.test_m6_evidence_db import database

pytestmark = pytest.mark.integration


def _set_elapsed(connection, current, durations):
    """Closed measured intervals make subsecond boundaries independent of runner speed."""
    connection.execute(
        "UPDATE m5_cycle_time_intervals SET ended_at=started_at WHERE cycle_db_id=%s",
        (current["cycle_db"],),
    )
    end = connection.execute("SELECT clock_timestamp() AS value").fetchone()["value"] - timedelta(seconds=1)
    start = end - timedelta(seconds=sum(durations))
    for duration in durations:
        stop = start + timedelta(seconds=duration)
        connection.execute(
            """INSERT INTO m5_cycle_time_intervals
               (cycle_db_id,session_db_id,interval_type,started_at,ended_at,reason)
               VALUES(%s,%s,'collecting',%s,%s,'exec_fix04_controlled')""",
            (current["cycle_db"], current["session_db"], start, stop),
        )
        start = stop


def test_fractional_answer_admission_and_multiple_intervals(current):
    decision = _resolve(current)
    cases = [
        ([7199.0], True, 1),
        ([7199.6], True, 1),
        ([7199.9], True, 1),
        ([7200.0], False, 0),
        ([7200.1], False, 0),
        ([3599.8, 3599.8], True, 1),
        ([3599.9, 3600.1], False, 0),
    ]
    for durations, allowed, remaining in cases:
        with current["factory"]() as connection:
            _set_elapsed(connection, current, durations)
            cycle = connection.execute("SELECT * FROM m5_cycles WHERE id=%s", (current["cycle_db"],)).fetchone()
            assert _can_continue(connection, dict(cycle)) is allowed
            state = read_cycle(connection, current["cycle_id"])
            assert state["remaining_seconds"] == remaining
            before = _counts(connection)
            request = _request(decision)
            if allowed:
                result = m7_clarification.answer(connection, **request)
                assert result["response_outcome"] == "answered"
                after = _counts(connection)
                assert after["turns"] == before["turns"] + 1
                assert after["responses"] == before["responses"] + 1
                assert after["handoffs"] == before["handoffs"] + 1
            else:
                with pytest.raises(ValueError, match="M7_TIME_LIMIT_REACHED"):
                    m7_clarification.answer(connection, **request)
                assert _counts(connection) == before
            connection.rollback()


def test_fractional_http_answer_replay_and_expiry(current, http):
    decision = _resolve(current)
    request = _request(decision)
    endpoint = "/users/assessment/m7/clarifications/" + str(decision["id"]) + "/answers"
    with current["factory"]() as connection:
        # The source fixture bootstraps M6 QA tables, while the product HTTP path
        # expects the M10 adapter migration normally applied at app startup.
        m10_orchestration.ensure_schema(connection)
        _set_elapsed(connection, current, [7199.6])
        connection.commit()
    response = http.post(endpoint, json={k: v for k, v in request.items() if k != "decision_id"})
    assert response.status_code == 200, response.text
    with current["factory"]() as connection:
        accepted = m7_clarification.read(connection, str(decision["id"]))
        _set_elapsed(connection, current, [7200.1])
        connection.commit()
        before = _counts(connection)
    replay = http.post(endpoint, json={k: v for k, v in request.items() if k != "decision_id"})
    assert replay.status_code == 200, replay.text
    changed = http.post(endpoint, json={**{k: v for k, v in request.items() if k != "decision_id"}, "content": "changed"})
    assert changed.status_code == 409, changed.text
    with current["factory"]() as connection:
        assert m7_clarification.read(connection, str(decision["id"]))["answer_turn_id"] == accepted["answer_turn_id"]
        assert _counts(connection) == before


def test_fractional_http_new_answer_after_budget_is_rejected(current, http):
    decision = _resolve(current)
    request = _request(decision)
    endpoint = "/users/assessment/m7/clarifications/" + str(decision["id"]) + "/answers"
    with current["factory"]() as connection:
        _set_elapsed(connection, current, [7200.1])
        connection.commit()
        before = _counts(connection)
    response = http.post(endpoint, json={k: v for k, v in request.items() if k != "decision_id"})
    assert response.status_code == 409, response.text
    with current["factory"]() as connection:
        assert _counts(connection) == before


def test_fractional_effective_at_excludes_pause_and_wait(current):
    with current["factory"]() as connection:
        _set_elapsed(connection, current, [3599.8, 3600.3])
        connection.execute(
            """INSERT INTO m5_cycle_time_intervals
               (cycle_db_id,session_db_id,interval_type,started_at,ended_at,reason)
               VALUES(%s,%s,'authorized_pause',clock_timestamp()-INTERVAL '20 seconds',clock_timestamp(),'exec_fix04_pause')""",
            (current["cycle_db"], current["session_db"]),
        )
        connection.execute(
            """INSERT INTO m5_cycle_time_intervals
               (cycle_db_id,session_db_id,interval_type,started_at,ended_at,reason)
               VALUES(%s,%s,'blocking_system_wait',clock_timestamp()-INTERVAL '10 seconds',clock_timestamp(),'exec_fix04_wait')""",
            (current["cycle_db"], current["session_db"]),
        )
        cycle = connection.execute("SELECT * FROM m5_cycles WHERE id=%s", (current["cycle_db"],)).fetchone()
        intervals = connection.execute(
            """SELECT started_at,ended_at FROM m5_cycle_time_intervals
               WHERE cycle_db_id=%s AND reason='exec_fix04_controlled' ORDER BY started_at,id""",
            (current["cycle_db"],),
        ).fetchall()
        kind, effective_at = m7_completion._effective_limit(connection, dict(cycle))
        assert kind == "time_budget"
        assert effective_at == intervals[1]["started_at"] + timedelta(seconds=3600.2)
        connection.rollback()


def test_answer_rechecks_budget_after_waiting_for_cycle_lock(current):
    decision = _resolve(current)
    request = _request(decision)
    with current["factory"]() as connection:
        _set_elapsed(connection, current, [7199.6])
        connection.commit()
        before = _counts(connection)

    def answer_after_lock():
        with current["factory"]() as connection:
            connection.execute("SET application_name='exec_fix04_waiter'")
            connection.execute("SET lock_timeout='10s'")
            try:
                m7_clarification.answer(connection, **request)
            except ValueError as exc:
                return str(exc)
            return "accepted"

    with current["factory"]() as holder:
        holder.execute("SELECT id FROM m5_cycles WHERE id=%s FOR UPDATE", (current["cycle_db"],))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(answer_after_lock)
            deadline = monotonic() + 5
            waiting = None
            while monotonic() < deadline:
                with current["factory"]() as observer:
                    waiting = observer.execute(
                        """SELECT 1 FROM pg_stat_activity
                           WHERE application_name='exec_fix04_waiter' AND wait_event_type='Lock'"""
                    ).fetchone()
                if waiting:
                    break
                sleep(0.05)
            assert waiting, "answer did not reach the Cycle lock"
            _set_elapsed(holder, current, [7200.1])
            holder.commit()
            assert future.result(timeout=10) == "M7_TIME_LIMIT_REACHED"
    with current["factory"]() as connection:
        assert _counts(connection) == before


def test_expiry_worker_agrees_with_exact_readback(current):
    with current["factory"]() as connection:
        _set_elapsed(connection, current, [7199.9])
        assert read_cycle(connection, current["cycle_id"])["remaining_seconds"] == 1
        assert m7_completion.expire_due_cycles(connection) == []
        _set_elapsed(connection, current, [7200.1])
        assert read_cycle(connection, current["cycle_id"])["remaining_seconds"] == 0
        results = m7_completion.expire_due_cycles(connection)
        assert len(results) == 1
        assert connection.execute(
            "SELECT status FROM m5_cycles WHERE id=%s", (current["cycle_db"],)
        ).fetchone()["status"] == "collection_closed"
        connection.rollback()
