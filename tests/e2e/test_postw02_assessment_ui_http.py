"""Owner runtime/return share POSTW02-01 progress; controlled storage, no provider/DB."""
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import routes, m10_product_flow, m7_return_integration, m7_route_replacement
from Api import participant_dashboard, m7_planning_repository

pytestmark = pytest.mark.e2e


class Result:
    def __init__(self, rows=()): self.rows = list(rows)
    def fetchone(self): return self.rows[0] if self.rows else None
    def fetchall(self): return self.rows


@pytest.fixture
def runtime(monkeypatch):
    cycle_id, as_id, revision = str(uuid4()), str(uuid4()), str(uuid4())
    now = datetime(2026, 11, 16, tzinfo=timezone.utc)
    cycle = dict(id=1, cycle_id=cycle_id, profile_ref_json={'saved': 'profile'}, owner_user_id=8, status='active')
    situation = dict(id=3, assessment_situation_id=as_id, status='active', started_at=now,
                     snapshot_json={'participant_payload': {'title': 'Synthetic'}}, scenario_ended_at=None, closed_at=None)
    saved = dict(cycle_db_id=1, revision_id=revision, profile_ref_json=cycle['profile_ref_json'],
                 content_json={'route': [{'case_id': f'saved-{n}', 'case_version': '1'} for n in range(1, 9)]})
    position = dict(position_no=3, state='in_progress', plan_revision_id=revision,
                    case_id='saved-3', case_version='1', as_status='active', started_at=now)
    queries = []
    class Storage:
        blocking = True
        def execute(self, sql, params=()):
            queries.append(sql)
            assert sql.strip().startswith('SELECT') and 'FOR UPDATE' not in sql
            if 'profile_ref_json FROM m5_cycles' in sql: return Result([cycle])
            if 'FROM m5_assessment_situations WHERE cycle_db_id' in sql: return Result([situation])
            if 'p.state IN(' in sql: return Result([situation])
            if 'p.case_id,p.case_version' in sql: return Result([position])
            if 'FROM m5_cycle_time_intervals' in sql: return Result([{'value': 1}]) if self.blocking else Result()
            if 'FROM m7_return_absence_events' in sql: return Result([dict(id=uuid4(), recognized_at=now)])
            if any(table in sql for table in ['m7_clarification_decisions', 'm10_pipeline_runs', 'm7_continuation_intents', 'm5_turn_operations']): return Result()
            raise AssertionError(sql)
    db = Storage()
    db.situation_id = as_id
    db.situation = situation
    @contextmanager
    def connection(): yield db
    monkeypatch.setattr(routes, 'get_connection', connection)
    monkeypatch.setattr(routes, '_m7_owned_cycle', lambda *_: type('Owner', (), {'id': 8})())
    monkeypatch.setattr(routes, '_m7_require_explicit_return', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(m7_planning_repository, 'read_plan', lambda *_: saved)
    monkeypatch.setattr(m10_product_flow.m7_cycle_planner, 'read_plan', lambda *_: {'plan': saved['content_json']})
    monkeypatch.setattr(m10_product_flow.m7_completion, 'read_status', lambda *_: {'collection_status': 'active', 'remaining_seconds': 123})
    monkeypatch.setattr(m10_product_flow.m5_scenario_runtime, 'trace', lambda *_: {'assessment_situation_id': as_id, 'status': 'active', 'turns': [], 'events': []})
    monkeypatch.setattr(m7_route_replacement, 'replacement_metadata', lambda *_: {'positions': [], 'progress': {'total_positions': 1, 'completed_positions': 0}})
    monkeypatch.setattr(m7_return_integration, 'replacement_metadata', m7_route_replacement.replacement_metadata)
    monkeypatch.setattr(m7_return_integration, '_context', lambda *_: (cycle, {'id': 2}, {'id': 7, 'position_no': 3}, situation))
    monkeypatch.setattr(m7_return_integration, '_saved_policy', lambda *_: m7_return_integration.load_policy(usage_scope='assessment'))
    monkeypatch.setattr(m7_return_integration, 'read_cycle', lambda *_: {'remaining_seconds': 123, 'calendar_deadline': None})
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        yield client, db, cycle, position, saved, queries


def test_runtime_and_return_use_same_validated_plan_not_materialized_count(runtime):
    client, db, cycle, _position, _saved, queries = runtime
    expected = participant_dashboard.cycle_progress(db, cycle)
    for suffix in [f'/assessment/cycles/{cycle["cycle_id"]}/runtime', f'/assessment/m7/cycles/{cycle["cycle_id"]}/return-state']:
        response = client.get('/users' + suffix)
        assert response.status_code == 200, response.text
        value = response.json()
        assert value['participant_progress'] == expected
        assert value['participant_progress']['planned_total'] == 8
        assert value['participant_progress']['current_position_no'] == 3
        if suffix.endswith('/runtime'):
            assert value['blocking_system_wait'] is True
            assert value['route']['progress']['total_positions'] == 8
        else:
            assert value['allowed_action'] == 'continue_current'
            assert value['progress']['total_positions'] == 8
    assert all(query.strip().startswith('SELECT') for query in queries)


def test_unpresented_or_untrusted_position_stays_unknown_and_blocking_wait_is_server_fact(runtime):
    client, db, cycle, position, saved, _queries = runtime
    position['started_at'] = None
    db.blocking = False
    url = f'/users/assessment/cycles/{cycle["cycle_id"]}/runtime'
    value = client.get(url).json()
    assert value['participant_progress']['current_position_no'] is None
    assert value['participant_progress']['planned_total'] == 8
    assert value['blocking_system_wait'] is False
    saved['profile_ref_json'] = {'other': 'profile'}
    value = client.get(url).json()
    assert value['participant_progress']['planned_total'] is None
    assert value['route']['progress']['total_positions'] is None


def test_paused_between_situations_with_false_blocking_is_a_successful_known_time_read(runtime, monkeypatch):
    client, db, cycle, _position, _saved, _queries = runtime
    cycle['status'] = 'paused'
    db.blocking = False
    # Retain the production HTTP route and production runtime projection.
    execute = db.execute
    def closed_as(sql, params=()):
        if "s.status='closed'" in sql:
            return Result([{'position_no': 3, 'assessment_situation_id': db.situation_id}])
        result = execute(sql, params)
        if 'FROM m5_assessment_situations WHERE cycle_db_id' in sql or 'p.state IN(' in sql:
            for row in result.rows:
                row['status'] = 'closed'
        return result
    monkeypatch.setattr(db, 'execute', closed_as)
    monkeypatch.setattr(m10_product_flow.m7_completion, 'read_status', lambda *_: {
        'collection_status': 'paused', 'remaining_seconds': 123,
    })
    monkeypatch.setattr(m10_product_flow, '_next_operation', lambda *_: None)
    response = client.get(f'/users/assessment/cycles/{cycle["cycle_id"]}/runtime')
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['between_situations'] is True
    assert value['current_situation'] is None
    assert value['status'] == {'collection_status': 'paused', 'remaining_seconds': 123}
    assert value['blocking_system_wait'] is False


@pytest.mark.parametrize(("characters", "expected"), [
    ([], "written"),
    ([{"character_id": "synthetic", "closed_card": "Not participant data"}], "dialogue"),
    (None, None),
])
def test_public_response_format_precedes_turns_and_never_returns_the_roster(runtime, characters, expected):
    client, db, cycle, _position, _saved, _queries = runtime
    db.situation["scenario_characters"] = characters
    response = client.get(f'/users/assessment/cycles/{cycle["cycle_id"]}/runtime')
    assert response.status_code == 200, response.text
    assert response.json()["current_situation"]["response_format"] == expected
    assert response.json()["trace"]["turns"] == []
    assert "scenario_characters" not in response.text and "closed_card" not in response.text
