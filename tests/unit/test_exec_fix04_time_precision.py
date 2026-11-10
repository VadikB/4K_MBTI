from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from Api import m5_cycle_runtime, m7_completion


class _Result:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value

    def fetchall(self):
        return self.value


class _TimeConnection:
    def __init__(self, cycle, consumed):
        self.cycle = cycle
        self.consumed = consumed

    def execute(self, query, _params):
        if "FROM m5_cycles" in query:
            return _Result(self.cycle)
        if "FROM m5_cycle_sessions" in query:
            return _Result([])
        if "FROM m5_cycle_time_intervals" in query:
            assert "::BIGINT" not in query
            return _Result({"value": self.consumed})
        raise AssertionError(query)


@pytest.mark.parametrize(
    "consumed,allowed,remaining,display_consumed",
    [
        ("7199", True, 1, 7199),
        ("7199.6", True, 1, 7199),
        ("7199.9", True, 1, 7199),
        ("7200", False, 0, 7200),
        ("7200.1", False, 0, 7200),
    ],
)
def test_exact_admission_and_integer_projection(consumed, allowed, remaining, display_consumed):
    cycle = {
        "id": 1, "cycle_id": uuid4(), "status": "active",
        "started_at": datetime.now(timezone.utc),
        "time_budget_seconds": 7200, "calendar_window_seconds": 259200,
    }
    connection = _TimeConnection(cycle, Decimal(consumed))
    assert m5_cycle_runtime._can_continue(connection, cycle) is allowed
    result = m5_cycle_runtime.read_cycle(connection, str(cycle["cycle_id"]))
    assert result["remaining_seconds"] == remaining
    assert result["consumed_seconds"] == display_consumed
    assert isinstance(result["remaining_seconds"], int)


def test_effective_limit_sums_fractional_intervals_without_rounding(monkeypatch):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        {"started_at": start, "ended_at": start + timedelta(seconds=3599.8)},
        {"started_at": start + timedelta(seconds=3600),
         "ended_at": start + timedelta(seconds=7200.3)},
    ]

    class Connection:
        def execute(self, query, _params):
            assert "FROM m5_cycle_time_intervals" in query
            return _Result(rows)

    monkeypatch.setattr(m7_completion, "read_cycle", lambda *_: {
        "calendar_deadline": datetime.now(timezone.utc) + timedelta(days=30), "remaining_seconds": 0,
    })
    kind, effective_at = m7_completion._effective_limit(
        Connection(), {"cycle_id": uuid4(), "id": 1, "time_budget_seconds": 7200}
    )
    assert kind == "time_budget"
    assert effective_at == start + timedelta(seconds=7200.2)


def test_minimum_for_new_question_uses_precise_remaining_time():
    cycle = {"id": 1, "time_budget_seconds": 7200}
    assert m5_cycle_runtime._remaining_collecting_seconds(
        _TimeConnection(cycle, Decimal("7080.0")), cycle
    ) == 120
    assert m5_cycle_runtime._remaining_collecting_seconds(
        _TimeConnection(cycle, Decimal("7080.1")), cycle
    ) < 120
