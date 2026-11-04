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


def assignment_lineage(connection, *, user_id, assignment_ref, configuration_id):
    """Owned-fixture refs only: no names, contacts, professional answers or prompts."""
    rows = connection.execute('''SELECT a.id AS assignment_id,a.organization_id,a.recipient_user_id,
        a.assignment_ref,a.created_by_user_id AS assigning_actor_id,b.id AS binding_id,
        b.assessment_configuration_id,b.role_profile_version_id,b.questionnaire_revision_id,
        q.status AS questionnaire_status,q.organization_context_version_id,
        confirmation.id AS acquaintance_confirmation_id,confirmation.answers_checksum,
        p.id AS personalized_profile_id,p.checksum AS profile_checksum,p.status AS profile_status,
        p.frozen_at,p.user_context_version_id,
        org.checksum AS organization_context_checksum,role.checksum AS role_checksum,
        professional.checksum AS user_context_checksum
        FROM organization_assessment_assignments a
        JOIN LATERAL (SELECT * FROM organization_assessment_source_bindings binding
            WHERE binding.assignment_id=a.id ORDER BY binding.id DESC LIMIT 1) b ON TRUE
        JOIN questionnaire_response_revisions q ON q.id=b.questionnaire_revision_id
            AND q.organization_id=a.organization_id AND q.assignment_ref=a.assignment_ref
        LEFT JOIN LATERAL (SELECT * FROM participant_acquaintance_confirmations item
            WHERE item.user_id=a.recipient_user_id AND item.organization_id=a.organization_id
              AND item.assignment_ref=a.assignment_ref AND item.questionnaire_revision_id=q.id
            ORDER BY item.confirmed_at DESC,item.id DESC LIMIT 1) confirmation ON TRUE
        LEFT JOIN assessment_personalized_profiles p ON p.id=confirmation.personalized_profile_id
            AND p.user_id=a.recipient_user_id AND p.organization_id=a.organization_id
            AND p.assessment_configuration_id=b.assessment_configuration_id
            AND p.role_profile_version_id=b.role_profile_version_id
            AND p.organization_context_version_id=q.organization_context_version_id
        LEFT JOIN assessment_organization_context_versions org ON org.id=p.organization_context_version_id
        LEFT JOIN assessment_role_profile_versions role ON role.id=p.role_profile_version_id
        LEFT JOIN assessment_user_context_versions professional ON professional.id=p.user_context_version_id
        WHERE a.recipient_user_id=%s AND a.assignment_ref=%s AND b.assessment_configuration_id=%s
          AND a.status='active' AND a.revoked_at IS NULL''',
        (user_id, assignment_ref, configuration_id)).fetchall()
    if len(rows) != 1:
        return {'status': 'UNKNOWN_OR_AMBIGUOUS', 'matching_assignments': len(rows)}
    result = dict(rows[0])
    linked = connection.execute('''SELECT link.id AS connection_id,link.program_definition_id,
        program.definition_checksum FROM organization_assessment_program_connections link
        JOIN assessment_program_definitions program ON program.id=link.program_definition_id
        WHERE link.organization_id=%s AND link.is_current=TRUE
          AND program.assessment_configuration_id=%s AND program.assignment_ref=%s''',
        (result['organization_id'], configuration_id, assignment_ref)).fetchone()
    result['program_connection'] = dict(linked) if linked else None
    result['administrator_user_ids'] = [row['user_id'] for row in connection.execute(
        "SELECT user_id FROM organization_memberships WHERE organization_id=%s AND role='admin' ORDER BY user_id",
        (result['organization_id'],)).fetchall()]
    result['status'] = 'LINKED' if result['personalized_profile_id'] is not None else 'PROFILE_NOT_BOUND'
    from Api.acquaintance import resolve_display_timing
    result['assigned_timing'] = resolve_display_timing(connection,
        personalized_profile_id=result['personalized_profile_id'])
    return result


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
        'candidate_ref': ({'case_id': candidate.get('CaseID'), 'case_version': candidate.get('CaseVersion'),
                           'checksum': trace.get('candidate_checksum')} if candidate else None),
        'candidate_recomputed_checksum': candidate_checksum(candidate) if candidate else None,
        'canonicalization': {'candidate': 'compact sorted UTF-8 JSON without LF',
                             'compiled_case_and_as': 'compact sorted UTF-8 JSON + LF'},
        'input_snapshot_checksum': trace.get('input_snapshot_checksum'),
        'compiled_case_checksum': trace.get('compiled_case_checksum'),
        'admitted_for_participant': trace.get('admitted_for_participant'),
        'admission_status': aggregation.get('status'),
        'blocking_failures': aggregation.get('blocking_failures'),
        'deterministic_failures': aggregation.get('deterministic_failures'),
        'incomplete_checks': [{key: item.get(key) for key in
            ('check_id', 'status', 'reason', 'evidence_paths', 'aggregation_error')}
            for item in aggregation.get('incomplete_checks', [])],
        'incomplete_details_availability': ('PRESENT' if 'incomplete_checks' in aggregation
            else 'UNKNOWN_NOT_IN_TRACE' if aggregation.get('status') == 'INCOMPLETE' else 'NOT_APPLICABLE'),
        'deterministic_protocol_errors': aggregation.get('deterministic_protocol_errors') or [],
        'repair_used': bool(repair), 'final_generation_operation_id': stages['generation']['operation_id'],
        'repair_operation_id': (repair.get('repair_generation_operation') or {}).get('operation_id'),
        'stages': stages, 'calls': calls, 'unique_operation_count': len(calls),
        'usage': {key: sum((call.get('usage') or {}).get(key, 0) for call in calls)
                  for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
    }
