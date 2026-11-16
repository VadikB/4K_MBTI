"""Real owner HTTP/bootstrap/projection with SELECT-only synthetic storage."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import routes, assessment_start_readiness, m7_return_integration
from Api.m5_case_runtime import checksum
from Api.schemas import UserResponse

pytestmark = pytest.mark.e2e


class Result:
    def __init__(self, rows): self.rows = rows
    def fetchall(self): return self.rows
    def fetchone(self): return self.rows[0] if self.rows else None


class ReadOnlyStorage:
    def __init__(self):
        self.cycle_id, self.revision_id = str(uuid4()), str(uuid4())
        self.route = [{'case_id': f'saved-{n}', 'case_version': '1'} for n in range(1, 9)]
        self.cycle = dict(id=1, cycle_id=self.cycle_id, status='active', started_at=datetime(2026, 11, 16, tzinfo=timezone.utc),
            collection_closed_at=None, personalized_profile_id=4, assignment_id=91, profile_ref_json={'checksum': 'saved-profile'},
            assessment_title='Synthetic assessment', organization_name='Synthetic organization', completed_cases=0)
        self.positions = [self.position(n) for n in range(1, 4)]
        self.statements = []
        self.cycles = [self.cycle]

    def position(self, n, state=None):
        return dict(position_no=n, plan_revision_id=self.revision_id, case_id=f'saved-{n}', case_version='1',
            state=state or ('completed' if n < 3 else 'in_progress'),
            as_status='closed' if n < 3 else 'active', started_at=datetime(2026, 11, 16, tzinfo=timezone.utc))

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        assert sql.strip().startswith('SELECT'), sql
        assert 'FOR UPDATE' not in sql and 'FOR SHARE' not in sql
        if 'FROM users u' in sql: return Result([{'id': 8}])
        if 'COUNT(position.id)' in sql:
            assert params[0] == 8
            assert 'organization_memberships' in sql and 'c.owner_user_id=%s' in sql
            return Result(self.cycles)
        if 'FROM m7_cycle_plans p JOIN m5_cycles' in sql:
            assert str(params[0]) in {str(c['cycle_id']) for c in self.cycles}
            content = {'route': deepcopy(self.route)}
            return Result([dict(cycle_db_id=1, profile_ref_json=self.cycle['profile_ref_json'], revision_id=self.revision_id,
                content_json=content, content_checksum=checksum(content))])
        if 'FROM m7_route_positions p' in sql:
            assert params == (1,)
            return Result(self.positions)
        raise AssertionError(sql)


@pytest.fixture
def cabinet(monkeypatch):
    db = ReadOnlyStorage()
    user = UserResponse(id=8, email='synthetic@example.test', full_name='Synthetic', role_id=None, job_description=None, raw_duties=None, created_at=datetime(2026, 11, 16))
    model = {'readiness': {'status': 'ready', 'organization_id': 10, 'organization_name': 'Synthetic', 'assignment_ref': 'saved'},
             'state': {'status': 'answers_confirmed'}, 'onboarding': {'status': 'completed'},
             'assignment_id': 91, 'assessment_name': 'Synthetic assignment',
             'mandatory_complete': True, 'late_readiness': {'status': 'ready_to_prepare', 'personalized_profile_id': 4}}
    admission = {'can_start': True, 'plan_revision_id': db.revision_id, 'reasons': []}
    returning = {'allowed_action': 'connected'}
    history = []
    @contextmanager
    def connection(): yield db
    monkeypatch.setattr(routes, 'get_connection', connection)
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token', lambda token: user if token == 'owner' else None)
    monkeypatch.setattr(routes, '_user_response_from_row', lambda _row: user)
    monkeypatch.setattr(routes, '_is_admin_user', lambda *_args: False)
    monkeypatch.setattr(routes.participant_profile, 'readiness', lambda *_args, **_kwargs:
        {'id': 4, 'status': 'ready', 'assessment_configuration_id': 5, 'message': ''})
    monkeypatch.setattr(routes.acquaintance, 'read_state', lambda *_args, **_kwargs: model)
    monkeypatch.setattr(routes.m8_results, 'list_owned_cycles', lambda *_args: history)
    monkeypatch.setattr(routes.m8_results, 'list_owned_reports', lambda *_args: [])
    monkeypatch.setattr(routes.m7_completion, 'read_status', lambda *_args: {'calendar_deadline': None})
    monkeypatch.setattr(assessment_start_readiness, 'read', lambda *_args, **_kwargs: admission)
    monkeypatch.setattr(m7_return_integration, 'read_return_state', lambda *_args, **_kwargs: returning)
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        client.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
        yield client, db, model, admission, returning, history


def dashboard(cabinet):
    response = cabinet[0].get('/users/8/session-bootstrap')
    assert response.status_code == 200, response.text
    return response.json()['dashboard']


def test_full_plan_eight_not_materialized_one_and_read_entry_has_no_writes(cabinet):
    _client, db, *_ = cabinet
    db.cycle.update(status='prepared', started_at=None)
    db.positions = [db.position(1, 'not_presented')]
    db.positions[0].update(started_at=None, as_status='admitted')
    for _ in range(2):
        card = dashboard(cabinet)['current_assessments'][0]
        assert card['planned_total'] == card['total_cases'] == 8
        assert card['current_position_no'] is None
        assert card['journey_state'] == 'ready'
        assert card['action'] == 'open_readiness'
    assert db.cycle['started_at'] is None
    assert len(db.positions) == 1


def test_closed_cycle_card_uses_saved_program_name(cabinet):
    _client, db, _model, _admission, _returning, history = cabinet
    db.cycle.update(status='calculated', collection_closed_at=datetime(2026, 11, 15, tzinfo=timezone.utc),
                    assessment_title='Current renamed program')
    history.append({'cycle_id': db.cycle_id, 'program_name': 'Saved program at completion',
                    'status': 'report_ready', 'report_id': str(uuid4())})
    card = dashboard(cabinet)['completed_assessments'][0]
    assert card['title'] == 'Saved program at completion'
    assert card['action'] == 'open_report'


def test_presented_three_of_eight_is_independent_of_completed_and_catalogue(cabinet):
    _client, db, *_ = cabinet
    for completed in (0, 2, None):
        db.cycle['completed_cases'] = completed
        card = dashboard(cabinet)['current_assessments'][0]
        assert (card['current_position_no'], card['planned_total']) == (3, 8)
        assert card['plan_revision_id'] == db.revision_id
    # There is no catalogue query or generated AS to obtain the denominator.
    assert len(db.positions) == 3


def test_between_positions_does_not_present_admitted_next_as(cabinet):
    _client, db, *_ = cabinet
    db.positions[2].update(state='completed', as_status='closed')
    next_position = db.position(4, 'not_presented'); next_position.update(started_at=None, as_status='admitted')
    db.positions.append(next_position)
    card = dashboard(cabinet)['current_assessments'][0]
    assert card['journey_state'] == 'between_situations'
    assert card['current_position_no'] is None
    assert card['last_completed_position_no'] == 3


def test_other_plan_revision_does_not_invent_current_position(cabinet):
    _client, db, *_ = cabinet
    for row in db.positions: row['plan_revision_id'] = str(uuid4())
    card = dashboard(cabinet)['current_assessments'][0]
    assert card['current_position_no'] is None
    assert card['last_completed_position_no'] is None
    assert card['planned_total'] == 8


@pytest.mark.parametrize('job,expected', [('queued', 'preparing'), ('running', 'preparing'), ('failed', 'preparation_failed')])
def test_preparation_and_confirmed_failure_are_distinct(cabinet, job, expected):
    _client, db, model, admission, *_ = cabinet
    db.cycle.update(status='prepared', started_at=None)
    admission.update(can_start=False, reasons=['AS_PLAN_REVISION_MISMATCH'])
    model['preparation_operation'] = {'status': job}
    card = dashboard(cabinet)['current_assessments'][0]
    assert card['journey_state'] == expected
    assert 'заблокирован' not in card['status_label']
    assert card['action'] == 'open_readiness'


def test_return_is_read_only_and_retains_explicit_continue_route(cabinet):
    cabinet[4]['allowed_action'] = 'continue_current'
    card = dashboard(cabinet)['current_assessments'][0]
    assert card['journey_state'] == 'return_required'
    assert card['action'] == 'continue'
    assert card['current_position_no'] == 3


def test_closed_cycle_uses_one_owned_history_entry_and_new_assignment_is_visible(cabinet):
    _client, db, model, _admission, _returning, history = cabinet
    db.cycle.update(status='calculated', collection_closed_at=datetime(2026, 11, 16, tzinfo=timezone.utc))
    history.append({'cycle_id': db.cycle_id, 'status': 'report_ready', 'report_id': 'saved-report'})
    result = dashboard(cabinet)
    assert result['current_assessments'] == []
    assert len(result['completed_assessments']) == 1
    assert result['completed_assessments'][0]['action'] == 'open_report'
    model['assignment_id'] = 92
    result = dashboard(cabinet)
    assert len(result['current_assessments']) == 1
    assert result['current_assessments'][0]['journey_state'] == 'preparing'
    assert len(result['completed_assessments']) == 1


def test_owner_bootstrap_rejects_missing_and_foreign_identity(cabinet):
    client, *_ = cabinet
    assert client.get('/users/9/session-bootstrap').status_code == 403
    client.cookies.clear()
    assert client.get('/users/8/session-bootstrap').status_code == 401


def test_confirmed_readiness_error_is_visible_and_unknown_read_is_not_a_block(cabinet):
    _client, db, _model, admission, *_ = cabinet
    db.cycle.update(status='prepared', started_at=None)
    admission.update(can_start=False, reasons=['CHECKSUM_MISMATCH'])
    assert dashboard(cabinet)['current_assessments'][0]['journey_state'] == 'readiness_error'
    admission['reasons'] = []
    assert dashboard(cabinet)['current_assessments'][0]['journey_state'] == 'not_ready'


def test_no_cycle_preparation_uses_saved_job_and_missing_organization_data(cabinet):
    _client, db, model, *_ = cabinet
    db.cycles = []
    model['preparation_operation'] = {'status': 'failed'}
    assert dashboard(cabinet)['current_assessments'][0]['journey_state'] == 'preparation_failed'
    model['late_readiness']['status'] = 'waiting_for_assessment_data'
    assert dashboard(cabinet)['current_assessments'][0]['journey_state'] == 'organization_preparing'
    model['readiness'].update(status='waiting_for_assignment')
    assert dashboard(cabinet)['current_assessments'][0]['journey_state'] == 'unassigned'
    model['readiness']['organization_id'] = None
    assert dashboard(cabinet)['current_assessments'] == []


def test_unknown_current_as_is_not_mislabelled_as_a_break(cabinet):
    _client, db, *_ = cabinet
    db.positions[2]['plan_revision_id'] = str(uuid4())
    card = dashboard(cabinet)['current_assessments'][0]
    assert card['last_completed_position_no'] == 2
    assert card['current_position_no'] is None
    assert card['between_situations'] is False
    assert card['journey_state'] == 'active'


def test_confirmed_runtime_failure_remains_visible_in_the_active_cycle(cabinet):
    _client, db, _model, _admission, _returning, history = cabinet
    history.append({'cycle_id': db.cycle_id, 'status': 'failed', 'processing_status': 'failed'})
    card = dashboard(cabinet)['current_assessments'][0]
    assert card['journey_state'] == 'runtime_error'
    assert card['action'] == 'continue'
    assert card['current_position_no'] == 3
    assert dashboard(cabinet)['completed_assessments'] == []


def test_released_unmanaged_entry_keeps_its_existing_action(cabinet, monkeypatch):
    _client, db, model, *_ = cabinet
    db.cycles = []
    model['assignment_id'] = None
    monkeypatch.setattr(routes.assessment_assignment_sources, 'has_managed_assignment', lambda *_a, **_kw: False)
    card = dashboard(cabinet)['current_assessments'][0]
    assert card['journey_state'] == 'acquaintance'  # No saved plan: never claim start readiness.
    assert card['action'] == 'open_legacy_acquaintance'
    assert card['planned_total'] is None
    monkeypatch.setattr(routes.assessment_assignment_sources, 'has_managed_assignment', lambda *_a, **_kw: True)
    assert dashboard(cabinet)['current_assessments'][0]['action'] == 'open_readiness'


def test_unmanaged_entry_keeps_existing_m4_gate_when_profile_is_not_ready(cabinet, monkeypatch):
    _client, db, model, *_ = cabinet
    db.cycles = []
    model['assignment_id'] = None
    monkeypatch.setattr(routes.assessment_assignment_sources, 'has_managed_assignment', lambda *_a, **_kw: False)
    monkeypatch.setattr(routes.participant_profile, 'readiness', lambda *_a, **_kw:
        {'status': 'not_ready', 'id': None, 'message': 'Synthetic profile needs confirmation'})
    card = dashboard(cabinet)['current_assessments'][0]
    assert card['journey_state'] == 'acquaintance'
    assert card['action'] == 'start'  # Existing guarded entry, not a server-start command.
    assert card['button_label'] == 'Продолжить знакомство'
    model['mandatory_complete'] = False
    assert dashboard(cabinet)['current_assessments'][0]['action'] == 'acquaintance'


@pytest.mark.parametrize('scene', ['active', 'preparing', 'prepared_preparing', 'ready', 'return', 'result'])
def test_cabinet_copy_matches_exact_v10_without_changing_actions(cabinet, scene):
    import json
    from pathlib import Path
    expected = json.loads((Path(__file__).parents[1] / 'fixtures/postw02-reference-copy.json').read_text())['scenes']
    _client, db, model, _admission, returning, history = cabinet
    if scene == 'preparing':
        db.cycles = []
        model['preparation_operation'] = {'status': 'queued'}
    elif scene in {'ready', 'prepared_preparing'}:
        db.cycle.update(status='prepared', started_at=None)
        if scene == 'prepared_preparing': model['preparation_operation'] = {'status': 'queued'}
    elif scene == 'return':
        returning['allowed_action'] = 'continue_current'
    elif scene == 'result':
        db.cycle.update(status='calculated', collection_closed_at=datetime(2026, 10, 17, tzinfo=timezone.utc))
        history.append({'cycle_id': db.cycle_id, 'status': 'report_ready', 'report_id': 'saved-report'})
    result = dashboard(cabinet)
    card = (result['completed_assessments'] if scene == 'result' else result['current_assessments'])[0]
    assert {key: card[key] for key in ('status_label', 'description', 'button_label')} == expected['preparing' if scene == 'prepared_preparing' else scene]
    expected_action = 'open_report' if scene == 'result' else 'continue' if scene in {'active', 'return'} else 'open_readiness'
    assert card['action'] == expected_action
