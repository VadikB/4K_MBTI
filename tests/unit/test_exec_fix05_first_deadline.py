"""First reached boundary, independently of delayed observation or UI projection."""
from datetime import datetime, timedelta, timezone

import pytest

from Api import m7_completion


@pytest.mark.parametrize('budget_offset,calendar_offset,expected', [
    (-5, -1, 'time_budget'),
    (-1, -5, 'calendar_deadline'),
    (-5, 60, 'time_budget'),
    (60, -5, 'calendar_deadline'),
    (60, 60, None),
    (-5, -5, 'calendar_deadline'),
    (0, 0, 'calendar_deadline'),
    (0, 60, 'time_budget'),
    (-.000001, 0, 'time_budget'),
])
def test_first_reached_limit_with_open_fractional_interval(budget_offset, calendar_offset, expected):
    observed = datetime(2026, 11, 11, tzinfo=timezone.utc)
    budget_at = observed + timedelta(seconds=budget_offset)
    calendar_at = observed + timedelta(seconds=calendar_offset)
    # 3599.8 + 3600.2 seconds, separated by an excluded pause/wait gap.
    second_start = budget_at - timedelta(seconds=3600.2)
    first_start = second_start - timedelta(seconds=3609.8)

    class Result:
        def __init__(self, value): self.value = value
        def fetchone(self): return self.value
        def fetchall(self): return self.value

    class Connection:
        def execute(self, query, params=None):
            if query == 'SELECT clock_timestamp() AS value':
                return Result({'value': observed})
            assert "interval_type='collecting'" in query
            assert 'ORDER BY started_at,id' in query
            assert params == (observed, 1)
            return Result([
                {'started_at': first_start, 'ended_at': first_start + timedelta(seconds=3599.8)},
                {'started_at': second_start, 'ended_at': observed},
            ])

    result = m7_completion._effective_limit(Connection(), {
        'id': 1, 'started_at': calendar_at - timedelta(seconds=259200),
        'calendar_window_seconds': 259200, 'time_budget_seconds': 7200,
    })
    expected_at = {'time_budget': budget_at, 'calendar_deadline': calendar_at, None: None}[expected]
    assert result == (expected, expected_at)


def test_unstarted_cycle_has_no_reached_limit():
    class Result:
        def fetchone(self): return {'value': datetime.now(timezone.utc)}
        def fetchall(self): return []

    class Connection:
        def execute(self, *_args): return Result()

    assert m7_completion._effective_limit(Connection(), {
        'id': 1, 'started_at': None, 'calendar_window_seconds': 259200, 'time_budget_seconds': 7200,
    }) == (None, None)
