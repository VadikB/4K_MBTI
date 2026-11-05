"""Offline source analysis only; output is NOT a runtime configuration/admission.

Print JSON (default) or a Markdown observation matrix. No DB/provider/network.
All content/targets are read from existing versioned sources, never invented here.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / 'assessment_definitions/cases/competencies_4k/functional-personalization/0.5'
M2 = ROOT / 'assessment_definitions/methodologies/competencies_4k/1.1/methodology.json'


def checksum(value):
    return hashlib.sha256((json.dumps(value, ensure_ascii=False, sort_keys=True,
                                      separators=(',', ':')) + '\n').encode()).hexdigest()


def validate_review(envelope):
    """Assertions for THIS unapproved review artifact, never an admission validator."""
    p = envelope['payload']
    assert envelope['proposal_payload_checksum'] == checksum(p)
    assert p['status'] == 'DRAFT_FOR_REVIEW' and p['scope'] == 'NON_RUNTIME_PROPOSAL_NOT_ADMISSION'
    assert p['runtime_authorization'] == 'NONE'
    assert p['productologist_approval'].startswith('PENDING') and p['methodologist_approval'].startswith('PENDING')
    full = {row['indicator_id']: row for row in p['full_m2_matrix']}
    assert len(full) == len(p['full_m2_matrix']) == p['full_m2_count'] == 61
    assert len(p['cases']) == 9
    union = {value for case in p['cases'] for value in case['target_ids']}
    assert len(union) == p['catalog_union_count'] == 39
    assert set(p['proposed_target_ids']) == union
    assert set(p['absent_target_ids']) == set(full) - union and len(p['absent_target_ids']) == 22
    assert len(p['observation_occurrences']) == p['catalog_design_occurrences'] == 55
    for row in p['observation_occurrences']:
        assert row['actual_opportunity'] == 'NOT_RUN' and row['final_as_validation'] == 'PENDING_PER_GENERATED_AS'
        assert row['observation_condition'] and row['source']['sha256'] and row['source']['pointer']
        assert all(row[key] == full[row['indicator_id']][key] for key in ('m2_version', 'skill_id', 'component_id'))
    route = p['proposed_primary_route']
    assert len(route) == len({row['case_id'] for row in route}) == 8
    assert {value for row in route for value in row['target_ids']} == union
    assert all(row['approval'] == 'PROPOSED_NOT_APPROVED' and row['pre_generate'] is False for row in route)
    assert p['timing_basis']['time_budget_seconds'] == 7200
    assert p['timing_basis']['binding_action_now'] == 'NOT_ALLOWED_NO_DATABASE_WRITES'


def build():
    release = json.loads((ROOT / 'tests/browser/fixtures/path-start-release.json').read_text())
    package = json.loads((PACKAGE / 'case-package.json').read_text())
    manifest = json.loads((PACKAGE / 'manifest.json').read_text())
    methodology = json.loads(M2.read_text())
    full = []
    versions = {'K1': 'v1.1', 'K2': 'v1.0', 'K3': 'v1.1', 'K4': 'v1.0'}
    for competency in methodology['competencies']:
        for skill in competency['skills']:
            for component in skill['components']:
                for indicator in component['indicators']:
                    full.append({'indicator_id': indicator['id'], 'name': indicator['name'],
                        'm2_version': versions[competency['id']], 'skill_id': skill['id'],
                        'component_id': component['id']})
    assert len(full) == len({row['indicator_id'] for row in full}) == 61
    refs = {case['case_id']: case for case in release['cases']}
    cases, occurrences = [], []
    admitted_package = copy.deepcopy(package)
    for case in admitted_package['cases']:
        case['status'] = case['author_case']['Status'] = 'FROZEN'
        assert checksum(case) == refs[case['case_id']]['content_checksum']
    assert checksum({'package': admitted_package, 'manifest': manifest}) == release['catalog']['manifest_json']['package_ref']['checksum']
    for case in package['cases']:
        ref = refs[case['case_id']]
        assert case['version'] == ref['case_version'] and case['base_role'] == 'specialist_expert'
        cases.append({'case_id': case['case_id'], 'version': case['version'], 'title': case['title'],
            'admitted_checksum': ref['content_checksum'], 'source_checksum': checksum(case),
            'planned_min_minutes': case['planned_min_minutes'], 'planned_max_minutes': case['planned_max_minutes'],
            'target_ids': [target['indicator_id'] for target in case['indicator_targets']],
            'qa_checksums': [qa['evidence_checksum'] for qa in ref['qa_evidence']],
            'admission_scope': 'EXISTING_CASE_QA_NOT_SPECIFIC_PLAN_APPROVAL'})
        for index, target in enumerate(case['indicator_targets']):
            normative = next(row for row in full if row['indicator_id'] == target['indicator_id'])
            assert all(target[key] == normative[key] for key in ('m2_version', 'skill_id', 'component_id'))
            source = PACKAGE / target['source']['file']
            assert hashlib.sha256(source.read_bytes()).hexdigest() == target['source']['sha256']
            original = json.loads(source.read_text())
            for part in target['source']['pointer'].strip('/').split('/'):
                original = original[int(part)] if isinstance(original, list) else original[part]
            condition = target['observation_condition']
            occurrences.append({'case_id': case['case_id'], 'case_version': case['version'],
                **{key: copy.deepcopy(target.get(key)) for key in (
                    'indicator_id', 'm2_version', 'skill_id', 'component_id', 'observation_condition',
                    'scenario_locations', 'material_refs', 'invariant_refs', 'validity_risk',
                    'branch_condition', 'event_condition', 'condition_absence_reason', 'source')},
                'package_pointer': f"/cases/{package['cases'].index(case)}/indicator_targets/{index}",
                'source_observability_checksum': checksum(original),
                'classification': 'EXPLICIT_BRANCH_SENSITIVE' if ('Условно' in condition or 'возникает только' in condition)
                                  else 'DESIGN_OPPORTUNITY_NOT_UNCONDITIONAL_OR_ACTUAL',
                'predicate_note': 'Null structured predicate is not proof of unconditional observability',
                'actual_opportunity': 'NOT_RUN', 'final_as_validation': 'PENDING_PER_GENERATED_AS'})
    all_ids = {row['indicator_id'] for row in full}
    catalog_ids = {row['indicator_id'] for row in occurrences}
    assert len(occurrences) == 55 and len(catalog_ids) == 39 and catalog_ids <= all_ids
    # Replay the existing technical ranking, not a methodology approval or deleted-plan reconstruction.
    uncovered = set(catalog_ids)
    route = []
    while uncovered:
        candidates = [case for case in cases if set(case['target_ids']) & uncovered]
        candidates.sort(key=lambda case: (-len(set(case['target_ids']) & uncovered),
            -len({value.split('.')[0] for value in set(case['target_ids']) & uncovered}),
            case['planned_max_minutes'], case['case_id'], case['version']))
        case = candidates[0]
        purpose = sorted(set(case['target_ids']) & uncovered)
        route.append({'position': len(route) + 1, **case, 'new_purpose_target_ids': purpose,
                      'approval': 'PROPOSED_NOT_APPROVED', 'pre_generate': False})
        uncovered -= set(purpose)
    matrix = [{**row, 'catalog_cases': sorted({item['case_id'] for item in occurrences
                 if item['indicator_id'] == row['indicator_id']}),
               'proposal_status': 'PROPOSED_CONDITIONAL_TARGET' if row['indicator_id'] in catalog_ids
                                  else 'ABSENT_FROM_NINE_CASE_CATALOG',
               'actual_evidence': 'NOT_RUN'} for row in full]
    skills = []
    for skill_id in dict.fromkeys(row['skill_id'] for row in full):
        members = [row for row in matrix if row['skill_id'] == skill_id]
        skills.append({'skill_id': skill_id, 'full_m2_indicators': len(members),
                       'catalog_potential_indicators': sum(bool(row['catalog_cases']) for row in members),
                       'actual_ia': 'NOT_RUN'})
    historic = json.loads((ROOT / 'docs/evc/evidence/path-start-2dc98c6-run/run/source-to-runtime-receipt.json').read_text())
    source_paths = ['tests/browser/fixtures/path-start-release.json', str(M2.relative_to(ROOT)),
        str((PACKAGE / 'case-package.json').relative_to(ROOT)), str((PACKAGE / 'manifest.json').relative_to(ROOT)),
        'docs/evc/tasks/arch-a05-coverage-pilot.md', 'docs/evc/tasks/arch30-add01.md',
        'docs/evc/evidence/path-plan-diagnostics/prior-02-decisions.txt',
        'docs/evc/evidence/path-plan-diagnostics/prior-07-a05.txt']
    payload = {'proposal_id': 'PATH-PILOT-01', 'version': '0.1', 'status': 'DRAFT_FOR_REVIEW',
        'scope': 'NON_RUNTIME_PROPOSAL_NOT_ADMISSION', 'runtime_authorization': 'NONE',
        'productologist_approval': 'PENDING_SPECIFIC_PLAN_AND_PRODUCT_PROMISE',
        'methodologist_approval': 'PENDING_SPECIFIC_PLAN_AND_OBSERVABILITY',
        'program': release['program'], 'configuration': release['configuration'],
        'catalog_ref': {key: release['catalog'][key] for key in ('id', 'catalog_id', 'catalog_version', 'manifest_checksum')},
        'role_refs': release['roles'], 'full_m2_count': 61,
        'm2_checksum': release['catalog']['manifest_json']['m2_checksum'],
        'cases': cases, 'catalog_design_occurrences': 55, 'catalog_union_count': 39,
        'proposed_target_ids': sorted(catalog_ids), 'absent_target_ids': sorted(all_ids - catalog_ids),
        'full_m2_matrix': matrix, 'skill_design_counts': skills, 'observation_occurrences': occurrences,
        'proposed_primary_route': route,
        'unselected_case_ids': sorted(set(refs) - {item['case_id'] for item in route}),
        'route_basis': 'OFFLINE_REPLAY_OF_EXISTING_TECHNICAL_GREEDY_RANKING_NOT_HISTORICAL_PLAN',
        'route_planned_minutes': {'min': sum(item['planned_min_minutes'] for item in route),
                                  'max': sum(item['planned_max_minutes'] for item in route)},
        'timing_basis': {'decision': 'ARCH-A05_PILOT-120', 'time_budget_seconds': 7200,
            'calendar_window_seconds': 259200, 'current_program_scoped_revision': 'NOT_PROVEN',
            'historical_run_budget_seconds': historic['cycle']['time_budget_seconds'],
            'binding_action_now': 'NOT_ALLOWED_NO_DATABASE_WRITES'},
        'historical_plan': 'UNKNOWN_FULL_PLAN_NOT_EXPORTED',
        'source_files': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths}}
    result = {'proposal_payload_checksum': checksum(payload), 'canonicalization': 'compact sorted UTF-8 JSON + LF',
              'payload': payload}
    validate_review(result)
    return result


def markdown(envelope):
    p = envelope['payload']
    lines = ['# Матрица возможностей ограниченного пилота — проект v0.1', '',
        'DRAFT_FOR_REVIEW / НЕ ДОПУСК. M2 содержит61 Indicator;39 — только предложенные',
        'плановые цели после просмотра маршрута, не утверждённый union и не Evidence.',
        'Для каждой AS обязательна новая валидация условий. Null branch/event не означает безусловность.', '',
        '## Сводка по Skills: полный M2 и потенциальный состав', '',
        '| Skill | Полный M2 | Потенциально в каталоге | Фактические IA |', '| --- | --- | --- | --- |']
    for row in p['skill_design_counts']:
        lines.append(f"| {row['skill_id']} | {row['full_m2_indicators']} | {row['catalog_potential_indicators']} | NOT_RUN |")
    lines += ['', 'Полнота проектного состава не означает полноту фактических возможностей или Score.', '',
        '## Все 61 Indicator', '',
        '| Indicator / M2 | Skill / Component | Каталог Cases | Статус в проекте |',
        '| --- | --- | --- | --- |']
    for row in p['full_m2_matrix']:
        lines.append(f"| {row['indicator_id']} / {row['m2_version']} — {row['name']} | {row['skill_id']} / {row['component_id']} | "
                     + (', '.join(x.rsplit('.', 1)[1] for x in row['catalog_cases']) or '—')
                     + ' | ' + ('Нет в каталоге' if not row['catalog_cases'] else 'Проектная возможность, не гарантия') + ' |')
    lines += ['', '## Конкретные условия 55 проектных возможностей', '',
        'Это извлечение условий из неизменённых sources; не экспертный oracle и не утверждение факта.',
        'Точные source SHA/pointers, материалы, места сценария и риски — также в JSON проекта.', '']
    for case in p['cases']:
        lines += [f"### {case['case_id']} {case['version']} — {case['title']}", '',
                  '| Цель | Условие возможности | Сценарий / материалы | Риск валидности |', '| --- | --- | --- | --- |']
        for row in p['observation_occurrences']:
            if row['case_id'] == case['case_id']:
                escape = lambda value: str(value).replace('|', '\\|').replace('\n', ' ')
                lines.append('| ' + ' | '.join(map(escape, [row['indicator_id'], row['observation_condition'],
                    ','.join(row['scenario_locations']) + ' / ' + ','.join(row['material_refs']), row['validity_risk']])) + ' |')
        lines.append('')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    args = parser.parse_args()
    value = build()
    print(markdown(value) if args.format == 'markdown' else json.dumps(value, ensure_ascii=False, indent=2), end='\n')
