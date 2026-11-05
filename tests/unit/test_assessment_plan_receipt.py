"""No provider: preserve M7 diagnosis, never decide plan admissibility here."""
import copy
import json
import subprocess
from pathlib import Path

import pytest

from Api.m5_case_runtime import checksum

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('failed', [False, True])
def test_start_readback_failure_preserves_other_evidence_and_hides_exception(monkeypatch, failed):
    from tests.assessment_first_case_evidence import start_readiness_receipt
    class SavepointConnection:
        def __init__(self):
            self.commands = []
        def execute(self, sql):
            self.commands.append(sql)
    connection = SavepointConnection()
    def read(*args, **kwargs):
        if failed:
            raise RuntimeError('sensitive diagnostic text must not be exported')
        return {'can_start': True, 'reasons': []}
    monkeypatch.setattr('Api.assessment_start_readiness.read', read)
    result = start_readiness_receipt(connection, cycle_id='synthetic-cycle', user_id=99)
    assert result['can_start'] is not failed
    assert connection.commands[0].startswith('SAVEPOINT ')
    assert connection.commands[-1].startswith('RELEASE SAVEPOINT ')
    assert any(command.startswith('ROLLBACK TO') for command in connection.commands) is failed
    if failed:
        assert result['availability'] == 'UNKNOWN'
        assert result['reasons'] == ['START_READBACK_UNAVAILABLE']
    assert 'sensitive' not in str(result)


def source(status='LIMITED'):
    content = {
        'schema_version': 1, 'status': status,
        'goal': {'kind': 'skills', 'selected_skills': ['K1']},
        'full_target_set': [{'indicator_id': 'K1.I01', 'm2_version': 'v1.1',
                             'skill_id': 'K1.S1', 'component_id': 'K1.S1.C1'}],
        'planned_target_set': [{'indicator_id': 'K1.I01', 'm2_version': 'v1.1'}],
        'uncovered_target_ids': ['K1.I01'] if status != 'READY' else [],
        'route': [] if status == 'NO_ROUTE' else [{'case_id': 'CASE.SPEC.02',
            'case_version': '0.6', 'purpose_target_ids': ['K1.I02'], 'conditional': True}],
        'catalog': [{'case_id': 'CASE.SPEC.01', 'case_version': '0.6', 'eligible': False,
                     'reasons': ['QA_EVIDENCE_MISSING_OR_FAIL:case_dialogue']}],
        'reserves': [], 'known_limitations': ['Conditional opportunity, not Evidence'],
        'time_budget_seconds': 3600, 'calendar_window_seconds': 259200,
        'algorithm_version': 'm7-greedy-coverage/1',
    }
    return {'id': 'plan-id', 'status': status, 'revision_id': 'revision-id',
            'revision_no': 2, 'content_checksum': checksum(content), 'content_json': content}


class Connection:
    def __init__(self, row):
        self.row = row

    def execute(self, sql, params):
        assert params == (17,)
        assert 'content_json' in sql and 'ORDER BY r.revision_no DESC' in sql
        assert all(word not in sql.upper() for word in ('INSERT', 'UPDATE', 'DELETE'))
        return self

    def fetchone(self):
        return self.row


@pytest.mark.parametrize('status', ['READY', 'LIMITED', 'NO_ROUTE'])
def test_plan_export_preserves_status_gaps_catalog_reasons_and_source_hash(status):
    from tests.assessment_first_case_evidence import plan_receipt
    row = source(status)
    before = copy.deepcopy(row)
    result = plan_receipt(Connection(row), cycle_db_id=17)
    assert row == before
    assert result['status'] == status
    assert result['revision_id'] == 'revision-id' and result['revision_no'] == 2
    assert result['content_checksum'] == result['content_recomputed_checksum'] == row['content_checksum']
    assert result['content_checksum_matches'] is True
    assert result['diagnostics_availability'] == 'PRESENT'
    assert result['missing_diagnostic_fields'] == []
    assert result['status_matches_revision'] is True
    assert result['diagnostics']['uncovered_target_ids'] == row['content_json']['uncovered_target_ids']
    assert result['diagnostics']['catalog'][0]['reasons'] == ['QA_EVIDENCE_MISSING_OR_FAIL:case_dialogue']
    assert result['diagnostics']['route'] == row['content_json']['route']
    assert result['diagnostics_checksum'] == checksum(result['diagnostics'])


def test_unknown_sensitive_fields_are_not_exported_even_nested():
    from tests.assessment_first_case_evidence import plan_receipt
    row = source()
    row['content_json']['profile'] = {'email': 'must-not-export'}
    row['content_json']['catalog'][0]['raw_prompt'] = 'must-not-export'
    row['content_json']['full_target_set'][0]['professional_answers'] = 'must-not-export'
    row['content_checksum'] = checksum(row['content_json'])
    result = plan_receipt(Connection(row), cycle_db_id=17)
    assert 'must-not-export' not in json.dumps(result)
    assert result['snapshot_export'] == 'ALLOWLISTED_DIAGNOSTIC_PROJECTION'
    assert result['content_checksum_matches'] is True
    assert result['diagnostics_checksum'] != result['content_checksum']


def test_absent_plan_is_explicit_unknown_not_empty_trusted_plan():
    from tests.assessment_first_case_evidence import plan_receipt
    assert plan_receipt(Connection(None), cycle_db_id=17) is None


def test_corrupt_source_hash_is_preserved_not_replaced_with_new_hash():
    from tests.assessment_first_case_evidence import plan_receipt
    row = source()
    row['content_checksum'] = '0' * 64
    result = plan_receipt(Connection(row), cycle_db_id=17)
    assert result['content_checksum'] == '0' * 64
    assert result['content_checksum_matches'] is False
    assert result['content_recomputed_checksum'] == checksum(row['content_json'])


def test_plan_diagnosis_survives_durable_export_before_source_cleanup(tmp_path):
    from tests.assessment_first_case_evidence import plan_receipt
    connection = Connection(source())
    receipt = {'preparation_operation': {'status': 'completed', 'operation_id': 'synthetic'},
               'plan': plan_receipt(connection, cycle_db_id=17)}
    file = tmp_path / 'failure-receipt.json'
    saved = subprocess.run(['node', str(ROOT / 'tests/browser/fixtures/receipt-file.mjs'), str(file)],
                           input=json.dumps(receipt), text=True, capture_output=True, check=True)
    assert len(json.loads(saved.stdout)['sha256']) == 64
    connection.row = None  # synthetic cleanup, not a real product DB or human review
    assert json.loads(file.read_text()) == receipt
    assert file.stat().st_mode & 0o777 == 0o600
    assert receipt['plan']['diagnostics']['uncovered_target_ids'] == ['K1.I01']


@pytest.mark.parametrize('content, availability', [(None, 'UNKNOWN'), ({'status': 'READY'}, 'PARTIAL')])
def test_missing_snapshot_diagnostics_are_explicit(content, availability):
    from tests.assessment_first_case_evidence import plan_receipt
    row = source()
    row['content_json'] = content
    result = plan_receipt(Connection(row), cycle_db_id=17)
    assert result['diagnostics_availability'] == availability
    assert 'uncovered_target_ids' in result['missing_diagnostic_fields']
    assert result['status_matches_revision'] is False


def test_wrongly_shaped_leaf_never_exports_nested_sensitive_payload():
    from tests.assessment_first_case_evidence import plan_receipt
    row = source()
    row['content_json']['catalog'][0]['reasons'] = [{'secret': 'must-not-export'}]
    result = plan_receipt(Connection(row), cycle_db_id=17)
    assert result['diagnostics']['catalog'][0]['reasons'] == [None]
    assert 'must-not-export' not in json.dumps(result)
