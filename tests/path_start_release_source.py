"""Read-only published source receipt; no users, history, or synthetic QA admission.

Run on the configured test server, then independently verify the receipt before
using it as the immutable source of an owned browser fixture. Importing this
module never connects to a database.
"""
from __future__ import annotations

import json
import subprocess

PROGRAM_CHECKSUM = '07576484b6c6467fd5fc7047cb1686a2f952532a893660375984373bab87f58c'
CATALOG_CHECKSUM = '0008d020cbeb8b06ef5d38ad1eaf136fab8dc42728d98c2d5ec275476a6c25a0'
DECISION_BASIS = 'owner_decision_2026-10-30_specialist_cases'


def validate_release(source):
    from Api.m5_case_runtime import checksum
    from Api.assessment_programs import definition_checksum

    program, catalog = source['program'], source['catalog']
    configuration, roles = source['configuration'], source['roles']
    assert (program['code'], program['version'], program['status']) == ('specialist_pilot', '1.1', 'published')
    assert (catalog['catalog_id'], catalog['catalog_version'], catalog['status']) == ('specialist-pilot', '1.0', 'published')
    assert catalog['decision_basis'] == DECISION_BASIS
    assert catalog['manifest_checksum'] == CATALOG_CHECKSUM == checksum(catalog['manifest_json'])
    assert program['assessment_configuration_id'] == configuration['id']
    assert program['catalog_version_id'] == configuration['catalog_version_id'] == catalog['id']
    assert configuration['code'] == 'specialist_pilot_v1' and configuration['status'] == 'published'
    assert program['source_refs_json'] == {key: configuration[key] for key in
        ('methodology_version_id', 'scenario_version_id', 'prompt_bundle_checksum')}
    assert [(role['code'], str(role['version'])) for role in roles] == [('specialist_expert', '1')]
    assert program['definition_checksum'] == PROGRAM_CHECKSUM == definition_checksum(
        code=program['code'], version=program['version'], name=program['name'],
        assignment_ref=program['assignment_ref'], mode=program['mode'],
        configuration_id=configuration['id'], catalog_version_id=catalog['id'],
        source_refs=program['source_refs_json'], role_version_ids=[role['id'] for role in roles])
    cases = source['cases']
    assert [case['case_id'] for case in cases] == [f'CASE.SPEC.{index:02d}' for index in range(1, 10)]
    assert catalog['manifest_json']['case_version_ids'] == sorted(case['id'] for case in cases)
    for case in cases:
        assert case['status'] == 'FROZEN' and case['base_role'] == 'specialist_expert'
        assert case['admission']['admitted'] is True and not case['admission']['reasons']
        qa = case['qa_evidence']
        assert {row['scope'] for row in qa} == {'case_format', 'case_dialogue', 'assessment_situation'}
        for row in qa:
            evidence = row['evidence_json']
            assert row['result'] == evidence['result'] == 'PASS'
            assert checksum(evidence) == row['evidence_checksum']
            assert evidence['case_ref'] == {'id': case['case_id'], 'version': case['case_version'],
                                           'checksum': case['content_checksum']}
            assert evidence['origin']['type'] == 'human_review'
            assert not evidence['origin'].get('synthetic')
            assert evidence['origin']['actor_ref'] == 'user:4:' + DECISION_BASIS


def collect(connection):
    from Api.config import settings
    from Api.m5_catalog_integrity import case_admission

    # Must be the first SQL statement. No ensure_schema/publication helpers here.
    connection.execute('SET TRANSACTION READ ONLY')
    target = dict(connection.execute('SELECT current_database() AS database, '
        'inet_server_port() AS internal_port').fetchone())
    assert target['database'] == 'agent4k_test', 'EXPECTED_PERMANENT_TEST_READ_ONLY'
    program = dict(connection.execute("""SELECT id,code,version,name,assignment_ref,mode,status,
        assessment_configuration_id,catalog_version_id,source_refs_json,definition_checksum,
        published_at FROM assessment_program_definitions WHERE code='specialist_pilot'
        AND version='1.1'""").fetchone())
    config = dict(connection.execute('''SELECT id,code,name,status,methodology_version_id,
        scenario_version_id,catalog_version_id,prompt_bundle_checksum FROM assessment_configurations
        WHERE id=%s''', (program['assessment_configuration_id'],)).fetchone())
    catalog = dict(connection.execute('''SELECT id,catalog_id,catalog_version,status,package_db_id,
        usage_scope,organization_id,manifest_json,manifest_checksum,decision_basis FROM m5_catalogs
        WHERE id=%s''', (program['catalog_version_id'],)).fetchone())
    roles = [dict(row) for row in connection.execute('''SELECT v.id,p.code,v.version,v.checksum
        FROM assessment_program_allowed_roles a JOIN assessment_role_profile_versions v
        ON v.id=a.role_profile_version_id JOIN assessment_role_profiles p ON p.id=v.role_profile_id
        WHERE a.program_definition_id=%s ORDER BY a.display_order''', (program['id'],)).fetchall()]
    cases = []
    for row in connection.execute('''SELECT cv.id,cv.case_id,cv.case_version,cv.status,cv.base_role,
        cv.content_checksum,member.runtime_rule_version_id FROM m5_case_versions cv
        JOIN m5_catalog_case_versions member ON member.case_version_id=cv.id
        WHERE member.catalog_db_id=%s ORDER BY cv.case_id''', (catalog['id'],)).fetchall():
        case = dict(row)
        case['qa_evidence'] = [dict(item) for item in connection.execute('''SELECT scope,result,
            evidence_json,evidence_checksum FROM m5_qa_evidence WHERE case_version_id=%s
            ORDER BY scope,evidence_checksum''', (case['id'],)).fetchall()]
        case['admission'] = {key: value for key, value in case_admission(connection,
            case_version_id=case['id'], usage_scope='assessment', catalog_db_id=catalog['id']).items()
            if key != 'case'}
        cases.append(case)
    source = {'schema_version': 1, 'purpose': 'PATH-START-01 exact published release mirror',
        'source_code_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'target': {**target, 'configured_port': settings.db_port, 'read_only': True},
        'program': program, 'configuration': config, 'catalog': catalog, 'roles': roles, 'cases': cases,
        'contains_user_history': False, 'new_methodology_approval': False}
    validate_release(source)
    return source


if __name__ == '__main__':
    from Api.database import get_connection
    with get_connection() as connection:
        receipt = collect(connection)
    print(json.dumps(receipt, ensure_ascii=False, indent=2, default=str))
