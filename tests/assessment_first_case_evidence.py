"""Read-only evidence for the owned synthetic harness; no runtime substitutions."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from Api.m5_case_runtime import checksum
from Api.m5_functional_generation_service import checksum as candidate_checksum

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONAL = ROOT / 'assessment_definitions/cases/competencies_4k/functional-personalization/0.5'


def changed_paths(left, right, prefix=''):
    if isinstance(left, dict) and isinstance(right, dict):
        return [item for key in sorted(left.keys() | right.keys())
                for item in changed_paths(left.get(key), right.get(key), prefix + '/' + key)]
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [item for index, (a, b) in enumerate(zip(left, right))
                for item in changed_paths(a, b, prefix + '/' + str(index))]
    return [] if left == right else [{'path': prefix, 'before': left, 'after': right}]


def source_provenance(connection, catalog_id):
    package = dict(connection.execute('''SELECT p.* FROM m5_packages p
        JOIN m5_catalogs c ON c.package_db_id=p.id WHERE c.id=%s''', (catalog_id,)).fetchone())
    selected = dict(connection.execute('''SELECT cv.* FROM m5_case_versions cv
        JOIN m5_catalog_case_versions member ON member.case_version_id=cv.id
        WHERE member.catalog_db_id=%s''', (catalog_id,)).fetchone())
    evidence = [dict(row) for row in connection.execute('''SELECT id,scope,result,evidence_json,
        evidence_checksum FROM m5_qa_evidence WHERE case_version_id=%s ORDER BY id''',
        (selected['id'],)).fetchall()]
    source_package = json.loads((FUNCTIONAL / 'case-package.json').read_text())
    source_manifest = json.loads((FUNCTIONAL / 'manifest.json').read_text())
    source_case = next(item for item in source_package['cases'] if item['case_id'] == selected['case_id'])
    outer_frozen = copy.deepcopy(source_case)
    outer_frozen['status'] = 'FROZEN'
    from Api.m5_catalog_integrity import case_admission
    return {
        'canonicalization': 'sha256 of compact sorted UTF-8 JSON + LF (m5_case_runtime)',
        'source_files': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (FUNCTIONAL / 'case-package.json', FUNCTIONAL / 'manifest.json',
                ROOT / 'assessment_definitions/cases/competencies_4k/functional-personalization-runtime/1.2.0/manifest.json',
                ROOT / 'assessment_definitions/providers/deepseek/v1/manifest.json')},
        'case': {
            'id': selected['case_id'], 'version': selected['case_version'],
            'source_checksum': checksum(source_case),
            'outer_status_only_checksum': checksum(outer_frozen),
            'imported_checksum': selected['content_checksum'],
            'imported_recomputed_checksum': checksum(selected['content_json']),
            'changes': changed_paths(source_case, selected['content_json']),
            'imported_json': selected['content_json'],
        },
        'package': {
            'id': package['package_id'], 'version': package['package_version'],
            'source_package_only_checksum': checksum(source_package),
            'source_import_envelope_checksum': checksum({'package': source_package, 'manifest': source_manifest}),
            'imported_checksum': package['package_checksum'],
            'imported_recomputed_checksum': checksum({'package': package['package_json'], 'manifest': package['manifest_json']}),
            'changes': changed_paths(source_package, package['package_json']),
        },
        'qa_evidence': evidence,
        'admission': {key: value for key, value in case_admission(connection,
            case_version_id=selected['id'], usage_scope='assessment', catalog_db_id=catalog_id).items()
            if key != 'case'},
        'methodology_approval': 'NOT_CLAIMED',
        'origin_contract_note': 'assessment policy requires human_review; rows are explicitly synthetic fixture assertions, not records of a methodological review',
    }


def provider_calls(value):
    """A repair operation is referenced twice in the product trace; count its ID once."""
    unique = {}

    def visit(node):
        if isinstance(node, list):
            for child in node:
                visit(child)
        elif isinstance(node, dict):
            sent, provider = node.get('sent'), node.get('provider')
            if isinstance(sent, dict) and isinstance(provider, dict) and node.get('operation_id'):
                call = {key: node.get(key) for key in ('operation_id', 'kind', 'input_checksum')}
                call.update(provider=sent.get('provider'), endpoint=sent.get('endpoint'),
                    requested_model=sent.get('model'), actual_model=provider.get('model'),
                    contract=sent.get('contract'), usage=provider.get('usage'),
                    transport_attempts=provider.get('transport_attempts'),
                    json_parse_failures=node.get('parse_failures') or [])
                previous = unique.setdefault(call['operation_id'], call)
                if previous != call:
                    raise ValueError('PROVIDER_OPERATION_ID_CONTENT_CONFLICT')
            for child in node.values():
                visit(child)

    visit(value)
    return list(unique.values())


def functional_receipt(trace):
    tester = trace.get('tester') or {}
    repair = trace.get('repair') or {}
    calls = provider_calls(trace)
    stages = {}
    for name, operation in (
        ('generation', trace.get('generation_operation')),
        ('tester', tester.get('provider_operation')),
        ('challenger', tester.get('challenger_operation')),
    ):
        operation = operation or {}
        batches = operation.get('batches') or []
        stages[name] = {
            'operation_id': operation.get('operation_id'), 'kind': operation.get('kind'),
            'batch_count': len(batches),
            'batch_operation_ids': [batch['operation_id'] for batch in batches],
            'required_check_ids': [check for batch in batches for check in batch.get('required_check_ids', [])],
        }
    aggregation = tester.get('aggregation') or {}
    candidate = trace.get('accepted_as') or trace.get('candidate_as')
    return {
        'present': bool(trace), 'candidate_checksum': trace.get('candidate_checksum'),
        'candidate_recomputed_checksum': candidate_checksum(candidate) if candidate else None,
        'canonicalization': {'candidate': 'compact sorted UTF-8 JSON without LF',
                             'compiled_case_and_as': 'compact sorted UTF-8 JSON + LF'},
        'input_snapshot_checksum': trace.get('input_snapshot_checksum'),
        'compiled_case_checksum': trace.get('compiled_case_checksum'),
        'admitted_for_participant': trace.get('admitted_for_participant'),
        'admission_status': aggregation.get('status'),
        'blocking_failures': aggregation.get('blocking_failures'),
        'deterministic_failures': aggregation.get('deterministic_failures'),
        'repair_used': bool(repair), 'final_generation_operation_id': stages['generation']['operation_id'],
        'repair_operation_id': (repair.get('repair_generation_operation') or {}).get('operation_id'),
        'stages': stages, 'calls': calls, 'unique_operation_count': len(calls),
        'usage': {key: sum((call.get('usage') or {}).get(key, 0) for call in calls)
                  for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
    }
