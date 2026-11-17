"""REPORT-09: immutable correction publication on a real isolated PostgreSQL."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from uuid import uuid4

import pytest

from test_m8_recommendation_basis_db import saved_chain
from test_m6_evidence_db import database  # noqa: F401 - fixture
from Api import m8_report_corrections as corrections, m8_results, m8_report_access
from Api import m6_cycle_aggregation_repository as calculations
from Api.m7_completion import read_c46
from Api.m8_recommendation_basis import resolve
from Api import m8_descriptive_report

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def no_real_description_generation(monkeypatch):
    monkeypatch.setattr(m8_descriptive_report, 'generate', lambda *_args, **_kwargs: {
        'contract_version': 'm8-descriptive-report/1.2.0', 'status': 'failed',
        'failure_reason': 'SYNTHETIC_FIXTURE', 'summary': [], 'claims': [],
    })


def _candidate(connection, results, text):
    resolved = resolve(connection, results)
    projection = next(p for p in resolved['projections'] if p.get('traces'))
    claim = {'kind': 'observation', 'skill_ids': [projection['criterion']['skill_id']],
             'basis_refs': [str(projection['revision_id'])], 'text': text,
             'limitations': [], 'context_refs': []}
    return {'summary': [text], 'claims': [claim]}


class SyntheticValidator:
    enabled = True

    def chat(self, messages, **_kwargs):
        candidate = json.loads(messages[1]['content'])['candidate']
        def decisions(values):
            return [{'index': index, 'decision': 'supported', 'reason_code': 'SYNTHETIC_CHECK'}
                    for index, _ in enumerate(values)]
        return json.dumps({'status': 'accepted', 'claim_decisions': decisions(candidate['claims']),
                           'summary_decisions': decisions(candidate['summary'])})


def test_explanation_correction_is_atomic_and_original_immutable(database):
    factory, results, report = saved_chain(database)
    with factory() as connection:
        corrections.ensure_schema(connection)
        old_c67 = report['c67']
        proposed = _candidate(connection, results, 'Синтетическое уточнение сохранённого наблюдения.')
        connection.rollback()
    with factory() as connection:
        corrections.ensure_schema(connection)
        prepared = corrections.prepare(connection, expected_report_id=report['id'],
            result_revision_id=results['revision_id'], kind='explanation', incident_ref='INC-SYNTHETIC-1',
            participant_reason='Уточнена формулировка наблюдения.', descriptive=proposed, created_by=99,
            validator_gateway=SyntheticValidator())
        assert prepared['changed']
        revised = corrections.publish(connection, candidate_id=prepared['candidate_id'],
            expected_report_id=report['id'], key='synthetic-correction-1', created_by=99)
        assert corrections.publish(connection, candidate_id=prepared['candidate_id'],
            expected_report_id=report['id'], key='synthetic-correction-1', created_by=99)['id'] == revised['id']
        with pytest.raises(ValueError, match='IDEMPOTENCY_CONFLICT'):
            corrections.publish(connection, candidate_id=str(uuid4()),
                expected_report_id=report['id'], key='synthetic-correction-1', created_by=99)
        assert revised['results_revision_id'] == report['results_revision_id']
        assert m8_results.read_report(connection, report['id'])['c67'] == old_c67
        assert m8_results.read_latest_report(connection, report['cycle_id'], 'assessee')['id'] == revised['id']
        assert corrections.public_notice(connection, revised)['reason'] == 'Уточнена формулировка наблюдения.'
        connection.execute("UPDATE m5_cycles SET usage_scope='assessment' WHERE cycle_id=%s", (report['cycle_id'],))
        assert len(m8_results.list_owned_cycles(connection, 99)) == 1
        # A later technical report cannot silently replace the addressed publication.
        later = m8_results.create_report(connection, results_revision_id=results['revision_id'],
            audience='assessee', key='synthetic-later-technical', target_profile=None, created_by=99)
        assert later['id'] != revised['id']
        assert m8_results.read_latest_report(connection, report['cycle_id'], 'assessee')['id'] == revised['id']
        assert m8_results.list_owned_cycles(connection, 99)[0]['report_id'] == revised['id']
        connection.execute('ALTER TABLE organizations ADD COLUMN name TEXT')
        connection.execute("UPDATE organizations SET name='Синтетическая организация'")
        connection.execute("ALTER TABLE organization_memberships ADD COLUMN role TEXT DEFAULT 'admin'")
        page = m8_report_access.page_customer_reports(connection, user_id=99, organization_id=1)
        assert page['items'][0]['report_id'] == revised['id']
        with pytest.raises(ValueError, match='M8_CORRECTION_EXPECTED_STALE'):
            corrections.publish(connection, candidate_id=prepared['candidate_id'],
                expected_report_id=report['id'], key='synthetic-correction-2', created_by=99)
        assert connection.execute('SELECT count(*) AS n FROM m8_report_corrections').fetchone()['n'] == 1
        connection.rollback()


def test_calculation_correction_requires_saved_c56_and_results(database):
    factory, results, report = saved_chain(database)
    with factory() as connection:
        corrections.ensure_schema(connection)
        c46 = read_c46(connection, report['cycle_id'])
        old_calculation = connection.execute("""SELECT c56_json FROM m6_cycle_calculations
            WHERE id=(SELECT calculation_id FROM m8_result_revisions WHERE id=%s)""",
            (results['revision_id'],)).fetchone()
        decisions = deepcopy(old_calculation['c56_json']['admissions'])
        assert decisions
        decisions[0]['numeric_admissible'] = False
        decisions[0]['included_revision_ids'] = []
        calculation = calculations.create(connection, cycle_id=report['cycle_id'], key='synthetic-calc-v2',
            expected_composition_checksum=c46['composition_checksum'],
            admission_mechanism_version='synthetic-correction/1', decisions=decisions, created_by=99,
            limitations=['Исправленный синтетический расчёт'])
        new_results = m8_results.create_results(connection, cycle_id=report['cycle_id'],
            calculation_id=calculation['id'], key='synthetic-results-v2', target_profile=None, created_by=99)
        proposed = _candidate(connection, new_results, 'Синтетическое объяснение исправленного основания.')
        with pytest.raises(ValueError, match='M8_CORRECTION_NEW_RESULTS_REQUIRED'):
            corrections.prepare(connection, expected_report_id=report['id'],
                result_revision_id=results['revision_id'], kind='calculation', incident_ref='INC-SYNTHETIC-2',
                participant_reason='Уточнён расчёт.', descriptive=proposed, created_by=99,
                validator_gateway=SyntheticValidator())
        prepared = corrections.prepare(connection, expected_report_id=report['id'],
            result_revision_id=new_results['revision_id'], kind='calculation', incident_ref='INC-SYNTHETIC-2',
            participant_reason='Уточнён расчёт.', descriptive=proposed, created_by=99,
            validator_gateway=SyntheticValidator())
        revised = corrections.publish(connection, candidate_id=prepared['candidate_id'],
            expected_report_id=report['id'], key='synthetic-correction-calc', created_by=99)
        assert revised['results_revision_id'] == new_results['revision_id']
        assert revised['c67']['provenance']['c56_ref'] == new_results['results']['c56_ref']
        assert m8_results.read_report(connection, report['id'])['results_revision_id'] == results['revision_id']
        connection.rollback()


def test_competing_publications_keep_one_current_revision(database):
    factory, results, report = saved_chain(database)
    with factory() as connection:
        corrections.ensure_schema(connection)
        candidate_ids = []
        for index in (1, 2):
            proposed = _candidate(connection, results, f'Синтетическая корректировка {index} сохранённого наблюдения.')
            item = corrections.prepare(connection, expected_report_id=report['id'],
                result_revision_id=results['revision_id'], kind='explanation',
                incident_ref=f'INC-SYNTHETIC-{index}', participant_reason=f'Уточнение {index}.',
                descriptive=proposed, created_by=99, validator_gateway=SyntheticValidator())
            candidate_ids.append(item['candidate_id'])
        connection.commit()

    def attempt(candidate_id, key):
        try:
            with factory() as connection:
                result = corrections.publish(connection, candidate_id=candidate_id,
                    expected_report_id=report['id'], key=key, created_by=99)
                connection.commit()
                return result['id']
        except ValueError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda args: attempt(*args),
            [(candidate_ids[0], 'race-1'), (candidate_ids[1], 'race-2')]))
    assert outcomes.count('M8_CORRECTION_EXPECTED_STALE') == 1
    with factory() as connection:
        rows = connection.execute('SELECT report_id FROM m8_report_corrections').fetchall()
        assert len(rows) == 1
        assert m8_results.read_latest_report(connection, report['cycle_id'], 'assessee')['id'] == str(rows[0]['report_id'])
        connection.rollback()


def test_failed_pointer_switch_rolls_back_new_report(database):
    factory, results, report = saved_chain(database)
    with factory() as connection:
        corrections.ensure_schema(connection)
        proposed = _candidate(connection, results, 'Синтетическое уточнение перед ошибкой записи.')
        prepared = corrections.prepare(connection, expected_report_id=report['id'],
            result_revision_id=results['revision_id'], kind='explanation', incident_ref='INC-SYNTHETIC-FAIL',
            participant_reason='Уточнение.', descriptive=proposed, created_by=99,
            validator_gateway=SyntheticValidator())
        connection.commit()
    with factory() as connection:
        connection.execute("""CREATE FUNCTION fail_correction_pointer() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'synthetic pointer failure'; END; $$ LANGUAGE plpgsql""")
        connection.execute("""CREATE TRIGGER fail_correction_pointer BEFORE INSERT OR UPDATE ON m8_published_reports
            FOR EACH ROW EXECUTE FUNCTION fail_correction_pointer()""")
        connection.commit()
    with pytest.raises(Exception, match='synthetic pointer failure'):
        with factory() as connection:
            corrections.publish(connection, candidate_id=prepared['candidate_id'],
                expected_report_id=report['id'], key='failed-switch', created_by=99)
            connection.commit()
    with factory() as connection:
        assert connection.execute('SELECT count(*) AS n FROM m8_report_corrections').fetchone()['n'] == 0
        assert connection.execute('SELECT count(*) AS n FROM m8_reports').fetchone()['n'] == 1
        assert corrections.current_report_id(connection, connection.execute(
            'SELECT id FROM m5_cycles WHERE cycle_id=%s', (report['cycle_id'],)).fetchone()['id']) == report['id']
        connection.rollback()
