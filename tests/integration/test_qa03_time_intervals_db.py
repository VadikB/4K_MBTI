"""Persisted timing only; synthetic admitted fixture, no provider/mail/full Cycle."""
import pytest

from Api.m5_cycle_runtime import begin_blocking_wait, read_cycle, transition_session
from tests.integration.test_m7_cycle_planner_db import active_cycle, db  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('interval_type', ['authorized_pause', 'blocking_system_wait'])
def test_allowed_wait_closes_collecting_without_spending_budget_or_extending_calendar(db, interval_type):
    with db() as connection:
        plan, _shown = active_cycle(connection)
        cycle_id = str(plan['cycle_id'])
        initial = read_cycle(connection, cycle_id)
        session = initial['sessions'][0]
        if interval_type == 'authorized_pause':
            transition_session(connection, session_id=str(session['session_id']), action='pause', reason='between_situations')
        else:
            begin_blocking_wait(connection, cycle_db_id=initial['id'], session_db_id=session['id'],
                                operation_ref='qa03-wait', reason='qa03-preparation')
        first = read_cycle(connection, cycle_id)
        intervals = connection.execute(
            'SELECT interval_type,started_at,ended_at FROM m5_cycle_time_intervals WHERE cycle_db_id=%s ORDER BY started_at',
            (initial['id'],),
        ).fetchall()
        assert any(row['interval_type'] == 'collecting' for row in intervals)
        assert all(row['ended_at'] is not None for row in intervals if row['interval_type'] == 'collecting')
        assert [row['interval_type'] for row in intervals if row['ended_at'] is None] == [interval_type]
        # Simulate a long already elapsed wait only in this isolated transaction.
        # Moving the excluded interval must never reduce the server's budget.
        connection.execute("UPDATE m5_cycle_time_intervals SET started_at=started_at-INTERVAL '20 minutes' "
                           'WHERE cycle_db_id=%s AND ended_at IS NULL', (initial['id'],))
        before = connection.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        connection.execute('SELECT pg_sleep(0.02)')
        after = connection.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        second = read_cycle(connection, cycle_id)
        assert first['remaining_seconds'] == second['remaining_seconds']
        assert first['consumed_seconds'] == second['consumed_seconds']
        assert initial['calendar_deadline'] == first['calendar_deadline'] == second['calendar_deadline']
        assert second['calendar_deadline'] - after < first['calendar_deadline'] - before
        assert first['time_budget_seconds'] == second['time_budget_seconds'] == initial['time_budget_seconds']
