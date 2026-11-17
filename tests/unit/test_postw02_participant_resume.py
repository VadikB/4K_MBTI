from copy import deepcopy
from uuid import uuid4

import pytest
from Api import m7_completion, m7_return_integration
from Api.m5_case_runtime import checksum

pytestmark = pytest.mark.unit


class Rows:
    def __init__(self, rows): self.rows = rows
    def fetchone(self): return deepcopy(self.rows[0]) if self.rows else None
    def fetchall(self): return deepcopy(self.rows)


class SavedPause:
    def __init__(self, *, resume_session):
        self.cycle = {'id': 1, 'cycle_id': str(uuid4()), 'owner_user_id': 7,
                      'status': 'paused' if resume_session else 'active'}
        self.session = {'id': 2, 'session_id': str(uuid4()), 'status': self.cycle['status']}
        self.situation = {'id': 3, 'assessment_situation_id': str(uuid4()), 'status': 'paused'}
        self.current = True
        self.intervals = [{'interval_type': 'authorized_pause' if resume_session else 'collecting', 'reason': 'old_pause'}]
        self.event = {'event_type': 'interaction_paused',
                      'cause_json': {'from': 'active', 'to': 'paused', 'reason': 'old_pause'}}
        self.command = {'request_checksum': checksum({'action': 'pause', 'reason': 'old_pause'}),
                        'result_json': {'assessment_situation_id': self.situation['assessment_situation_id']}}

    def execute(self, sql, params=None):
        assert sql.lstrip().startswith('SELECT'), 'resume admission must not mutate timing or materials'
        if 'm7_route_positions' in sql: return Rows([{'value': 1}] if self.current else [])
        if 'm5_cycle_time_intervals' in sql: return Rows(self.intervals)
        if 'm7_completion_commands' in sql: return Rows([self.command] if self.command else [])
        if 'm5_scenario_events' in sql: return Rows([self.event] if self.event else [])
        raise AssertionError(sql)

    def check(self, resume_session):
        m7_completion.assert_participant_resume(self, cycle=self.cycle, session=self.session,
                                               situation=self.situation, resume_session=resume_session)


@pytest.fixture
def limits(monkeypatch):
    monkeypatch.setattr(m7_completion, '_effective_limit', lambda *a: (None, None))
    monkeypatch.setattr(m7_return_integration, 'reconcile_presence', lambda *a, **k: None)


@pytest.mark.parametrize('resume_session', [True, False])
def test_saved_pause_can_recover_without_policy_permission_field(limits, resume_session):
    saved = SavedPause(resume_session=resume_session)
    before = deepcopy(saved.__dict__)
    saved.check(resume_session)
    assert saved.__dict__ == before


@pytest.mark.parametrize('resume_session', [True, False])
@pytest.mark.parametrize('defect', ['closed', 'no_current', 'no_event', 'untrusted_reason', 'between', 'blocking_wait', 'wrong_session'])
def test_unsafe_saved_pause_does_not_admit_resume(limits, resume_session, defect):
    saved = SavedPause(resume_session=resume_session)
    if defect=='closed': saved.situation['status']='closed'
    if defect=='no_current': saved.current=False
    if defect=='no_event': saved.event=None
    if defect=='untrusted_reason': saved.event['cause_json']['reason']=None
    if defect=='between': saved.event['cause_json']['reason']='between_situations'
    if defect=='blocking_wait': saved.intervals.append({'interval_type': 'blocking_system_wait', 'reason': 'system'})
    if defect=='wrong_session': saved.session['status']='interrupted'
    with pytest.raises(ValueError, match='M7_PARTICIPANT_RESUME_NOT_ALLOWED'):
        saved.check(resume_session)


@pytest.mark.parametrize('defect', ['missing_receipt', 'checksum', 'different_as'])
def test_cycle_resume_requires_saved_pause_command(limits, defect):
    saved = SavedPause(resume_session=True)
    if defect=='missing_receipt': saved.command=None
    if defect=='checksum': saved.command['request_checksum']='wrong'
    if defect=='different_as': saved.command['result_json']['assessment_situation_id']=str(uuid4())
    with pytest.raises(ValueError, match='M7_PARTICIPANT_RESUME_NOT_ALLOWED'):
        saved.check(True)


@pytest.mark.parametrize('resume_session', [True, False])
def test_resume_requires_explicit_return_before_or_after_expired_lease(limits, monkeypatch, resume_session):
    saved = SavedPause(resume_session=resume_session)
    calls=[]
    def reconcile(c, **kwargs):
        calls.append(kwargs)
        return {'status': 'recognized'}
    monkeypatch.setattr(m7_return_integration, 'reconcile_presence', reconcile)
    with pytest.raises(ValueError, match='M7_RETURN_EXPLICIT_CONTINUE_REQUIRED'):
        saved.check(resume_session)
    assert calls == [{'cycle_id': saved.cycle['cycle_id'], 'owner_user_id': 7}]


@pytest.mark.parametrize('resume_session', [True, False])
@pytest.mark.parametrize('limit', ['time_budget', 'calendar_deadline'])
def test_saved_pause_cannot_restore_expired_budget_or_deadline(limits, monkeypatch, resume_session, limit):
    monkeypatch.setattr(m7_completion, '_effective_limit', lambda *a: (limit, 'boundary'))
    with pytest.raises(ValueError, match='M7_TIME_LIMIT_REACHED'):
        SavedPause(resume_session=resume_session).check(resume_session)


def test_paused_session_with_open_clarification_uses_saved_pause_receipt(limits):
    saved = SavedPause(resume_session=True)
    saved.situation['status']='scenario_ended'
    saved.command['result_json']['assessment_situation_id']=None
    saved.event=None  # scenario_end is preserved; it is not an interaction pause.
    saved.check(True)
