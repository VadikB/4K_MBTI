"""Participant-safe explanations; technical stubs, not a product E2E."""
import pytest

from Api import acquaintance


class Connection:
    def __init__(self):
        self.result = None
        self.legacy_queries = 0

    def execute(self, sql, params=()):
        if 'FROM organization_memberships' in sql:
            self.result = [{'id': 10, 'name': 'Synthetic organization', 'role': 'member'}]
        elif 'to_regclass' in sql:
            self.result = None
        elif 'SELECT DISTINCT assignment_ref FROM (' in sql:
            self.result = [{'assignment_ref': 'specialist-pilot'}]
        elif 'FROM assessment_organization_context_versions' in sql:
            self.legacy_queries += 1
            self.result = None
        else:
            raise AssertionError('Unexpected SQL: ' + sql)
        return self

    def fetchall(self):
        return self.result

    def fetchone(self):
        return self.result


@pytest.mark.parametrize('missing,label', [('full_name', 'ФИО')])
def test_missing_participant_field_is_not_generic_organization_wait(monkeypatch, missing, label):
    monkeypatch.setattr(acquaintance, 'assignment_readiness', lambda *a, **kw: {
        'status': 'ready', 'assignment_ref': 'specialist-pilot', 'questionnaire_revision_id': 11,
        'briefing': {'participant_question_schema': acquaintance.PARTICIPANT_QUESTION_SCHEMA}})
    monkeypatch.setattr(acquaintance, '_participant_fields', lambda *a, **kw: [
        {'key': key, 'value': None if key == missing else 'Synthetic'} for key in ('full_name', 'email', 'position')])
    result = acquaintance.early_readiness(Connection(), user_id=1)
    assert result['reason'] == 'participant_fields:' + missing
    assert label.lower() in result['message'].lower()
    assert 'ещё готовит данные' not in result['message']


def test_exact_assignment_questionnaire_blocker_does_not_fall_into_legacy(monkeypatch):
    monkeypatch.setattr(acquaintance, 'assignment_readiness', lambda *a, **kw: {
        'status': 'draft', 'reason': 'confirmed_questionnaire', 'missing': ['confirmation']})
    connection = Connection()
    result = acquaintance.early_readiness(connection, user_id=1)
    assert result['reason'] == 'confirmed_questionnaire'
    assert result['assignment_ref'] == 'specialist-pilot'
    assert 'анкет' in result['message'].lower()
    assert connection.legacy_queries == 0


def test_read_state_preserves_known_early_reason(monkeypatch):
    monkeypatch.setattr(acquaintance, 'early_readiness', lambda *a, **kw: {
        'status': 'waiting_for_organization', 'reason': 'participant_fields:position'})
    monkeypatch.setattr(acquaintance, '_onboarding_progress', lambda *a, **kw: {})
    monkeypatch.setattr(acquaintance, '_competency_explanation', lambda *a, **kw: {})
    result = acquaintance.read_state(None, user_id=1)
    assert result['late_readiness']['reason'] == result['readiness']['reason']
