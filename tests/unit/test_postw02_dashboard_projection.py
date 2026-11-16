"""Unresolvable persisted provenance must remain unknown, without AS-count fallback."""
from uuid import uuid4

import pytest

from Api import participant_dashboard as projection


@pytest.mark.parametrize('change', ['cycle', 'profile', 'route', 'checksum'])
def test_untrusted_saved_plan_never_becomes_a_materialized_total(monkeypatch, change):
    cycle = {'id': 1, 'cycle_id': str(uuid4()), 'profile_ref_json': {'checksum': 'saved'}}
    saved = {'cycle_db_id': 1, 'profile_ref_json': cycle['profile_ref_json'],
             'revision_id': str(uuid4()), 'content_json': {'route': [{'case_id': 'saved'}] * 8}}
    if change == 'cycle': saved['cycle_db_id'] = 2
    if change == 'profile': saved['profile_ref_json'] = {'checksum': 'other'}
    if change == 'route': saved['content_json']['route'] = None
    def read(*_args):
        if change == 'checksum': raise ValueError('CHECKSUM_MISMATCH')
        return saved
    monkeypatch.setattr(projection.m7_planning_repository, 'read_plan', read)
    class NoQueries:
        def execute(self, *_args): raise AssertionError('No catalogue/AS queries for an untrusted plan')
    result = projection.cycle_progress(NoQueries(), cycle)
    assert result['planned_total'] is None
    assert result['current_position_no'] is None
    assert result['plan_revision_id'] is None
