"""Структура QA-пакета; не проверка семантики и не экспертная приёмка GC."""
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from Api.m6_contracts import validate_analysis
from Api.m6_input_resolver import normalize
from Api.assessment_configuration import definition_checksum

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'tests/fixtures/m6_gc/v1'


def read(path):
    return json.loads(path.read_text())


def test_frozen_package_dependencies_and_content():
    manifest = read(PACKAGE / 'manifest.json')
    for record in manifest['sources'] + manifest['local_dependencies']:
        assert hashlib.sha256((ROOT / record['path']).read_bytes()).hexdigest() == record['sha256'], record['path']
    for record in manifest['files']:
        assert hashlib.sha256((PACKAGE / record['path']).read_bytes()).hexdigest() == record['sha256'], record['path']
    assert manifest['approved_gc_count'] == 0
    assert manifest['real_llm_runs'] == 0


def test_full_m2_criteria_match_extracted_original_cells():
    rows = read(PACKAGE / 'sources/m2-cells.json')
    criteria = read(PACKAGE / 'sources/criteria.json')
    assert len(rows) == len(criteria) == 9
    for criterion in criteria:
        row = next(r for r in rows if criterion['id'] in r['cells'].values())
        values = {''.join(c for c in key if c.isalpha()): value for key, value in row['cells'].items()}
        assert values['G'] == criterion['function']
        assert values['H'] == criterion['product']
        assert values['M'] == criterion['boundary']
        assert values['N'] == criterion['evidence_pattern']
        assert {f'L{i}': values[col] for i, col in enumerate('IJKL')} == criterion['levels']


@pytest.mark.parametrize('path', sorted((PACKAGE / 'technical').glob('*.json')), ids=lambda p: p.stem)
def test_technical_inputs(path):
    fixture = read(path)
    value = fixture['input']
    def run():
        if fixture['kind'] == 'normalize':
            return normalize(**value)
        return validate_analysis(value['analysis'], value['material'])
    if fixture['expected'] == 'PASS':
        result = run()
        if fixture['kind'] == 'normalize':
            assert result == fixture['material']
    elif fixture['expected'] == 'ValidationError':
        with pytest.raises(ValidationError):
            run()
    else:
        with pytest.raises(ValueError, match=fixture['expected']):
            run()


@pytest.mark.parametrize('path', sorted((PACKAGE / 'candidates').glob('*.json')), ids=lambda p: p.stem)
def test_candidate_references_not_semantics(path):
    candidate = read(path)
    material = candidate['material']
    assert candidate['status'] == 'CANDIDATE'
    assert candidate['expert_card']['approved_at'] is None
    assert len(material['indicator_targets']) == 9
    assert set(candidate['review_scope'] + candidate['unreviewed_targets']) == {x['indicator_id'] for x in material['indicator_targets']}
    assert material['indicator_targets'] == candidate['as_snapshot']['indicator_targets']
    if candidate['resolver_input']:
        assert normalize(**candidate['resolver_input']) == material
    payload = {k: v for k, v in material.items() if k != 'material_revision'}
    assert definition_checksum(payload) == material['material_revision']['material_sha256']
    validate_analysis(candidate['draft_analysis'], material)
    assert all(m['material_id'] != 'CASE-TDISC-01-D2' for m in material['materials'])
    if candidate['resolver_input']:
        first_user = min(t['sequence_no'] for t in material['turns'] if t['speaker_type'] == 'assessee')
        d3 = next(m for m in material['materials'] if m['material_id'] == 'CASE-TDISC-01-D3')
        end = next(e['sequence_no'] for e in material['events'] if e['event_type'] == 'scenario_completed')
        assert first_user < d3['available_sequence'] < end


def test_paraphrase_authorship_and_temporal_contrasts_have_different_inputs():
    items = {p.stem: read(p) for p in (PACKAGE / 'candidates').glob('*.json')}
    assert len({x['material']['material_revision']['material_sha256'] for x in items.values()}) == len(items)
    independent = items['independent']['draft_analysis']['fragments'][0]['quote']
    assert any(t['content'] == independent and t['speaker_type'] == 'character' for t in items['character']['material']['turns'])
    assert items['character']['draft_analysis']['evidence'] == []
    before = items['before_disclosure']['material']
    d1 = next(m['available_sequence'] for m in before['materials'] if m['material_id'] == 'CASE-TDISC-01-D1')
    assert any(t['sequence_no'] < d1 and t['content'].startswith(independent) for t in before['turns'])
    early = items['before_disclosure']['draft_analysis']
    assert early['signals'][0]['context_refs'] == []
    assert early['evidence'][0]['context_refs'] == []
    assert any('до D1' in text for text in early['evidence'][0]['limitations'])
    assert not items['no_opportunity']['material']['turns']
    assert not items['technical_loss']['draft_analysis']['evidence']


def test_blind_review_packet_has_no_draft_or_reviewer_data():
    packet = PACKAGE / 'blind_review'
    manifest = read(packet / 'manifest.json')
    assert manifest['contains_draft_analysis'] is False
    assert manifest['contains_personal_contacts'] is False
    assert len(manifest['records']) == 11
    for record in manifest['records']:
        source = ROOT / record['source_path']
        review = ROOT / record['review_path']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == record['source_sha256']
        assert hashlib.sha256(review.read_bytes()).hexdigest() == record['review_sha256']
        value = read(review)
        assert 'draft_analysis' not in value
        assert 'expert_card' not in value
        assert 'access_history' not in value
        assert 'resolver_input' not in value
        assert value['review_instructions']['independent_first_opinion_required'] is True


def test_m6_b_assessment_candidates_cover_outcomes_without_claiming_approval():
    package = read(PACKAGE / 'manifest.json')
    manifest = read(PACKAGE / 'assessment_candidates/manifest.json')
    assert package['assessment_candidate_count'] == len(manifest['records']) == 7
    assert package['approved_assessment_gc_count'] == manifest['approved_count'] == 0
    outcomes = {x['project_expected_outcome'] for x in manifest['records']}
    assert outcomes == {'L0','L1','L2','L3','INSUFFICIENT_EVIDENCE','NO_ASSESSMENT','TECHNICAL_FAILURE'}
    for record in manifest['records']:
        source = PACKAGE / record['source_input']['path']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == record['source_input']['sha256']
        candidate = read(source)
        assert record['status'] == 'CANDIDATE' and record['expert_approved'] is False
        assert record['source_input']['material_revision'] == candidate['material']['material_revision']['material_sha256']
        targets = {x['indicator_id']: x['m2_version'] for x in candidate['material']['indicator_targets']}
        focus = record['focus_target']
        assert targets[focus['indicator_id']] == focus['m2_version']
        assert set(record['unreviewed_targets']) == set(targets) - {focus['indicator_id']}
