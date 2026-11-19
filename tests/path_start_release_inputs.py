"""Mirror an independently read published release, only in the existing owned stand.

The original human_review evidence is copied byte-for-canonical-byte, not
manufactured by a synthetic reviewer. The local publishing actor is technical;
this is no new methodology approval or publication to a persistent environment.
"""
import json
import os


def reserve_release_ids(connection, table, first_id):
    """Published checksums include physical refs; reserve unused IDs, not fake rows.

    Only the empty/initial owned fixture is eligible. Fail instead of rewriting
    existing IDs or silently changing the catalog/program checksum.
    """
    assert table in {'m5_case_versions', 'm5_catalogs', 'assessment_configurations',
                     'assessment_program_definitions'}
    assert os.getenv('AGENT4K_ISOLATED_STAND') == '1'
    assert connection.execute('SELECT current_database() AS name').fetchone()['name'].startswith('product4k_pytest_')
    maximum = connection.execute('SELECT COALESCE(MAX(id),0) AS n FROM ' + table).fetchone()['n']
    assert maximum < first_id, 'RELEASE_ID_ALREADY_OCCUPIED:' + table
    connection.execute('SELECT setval(pg_get_serial_sequence(%s,%s),%s,false)', (table, 'id', first_id))


def _mirror_catalog(connection, *, catalog, package_db_id, case_ids, runtime_id, actor, receipt_sha256):
    from Api.m5_case_runtime import checksum
    from Api.m5_catalog_integrity import catalog_readback, publication_plan

    # Restore the exact receipt in the owned stand. A new publication builds
    # a new manifest with the current CaseType reference.
    reserve_release_ids(connection, 'm5_catalogs', catalog['id'])
    plan = publication_plan(
        connection, package_db_id=package_db_id, case_version_ids=case_ids,
        usage_scope=catalog['usage_scope'], organization_id=catalog['organization_id'],
        runtime_rule_version_id=runtime_id,
    )
    assert plan['publishable'], plan['decisions']
    manifest = catalog['manifest_json']
    runtime_ref = connection.execute('''
        SELECT artifact_id,artifact_version,manifest_checksum,rules_checksum
        FROM m5_runtime_rule_versions WHERE id=%s
    ''', (runtime_id,)).fetchone()
    assert manifest['package_ref'] == {
        'id': plan['package_id'], 'version': plan['package_version'], 'checksum': plan['package_checksum'],
    }
    assert manifest['m2_checksum'] == plan['m2_checksum']
    assert manifest['case_version_ids'] == plan['case_version_ids']
    assert manifest['runtime_rule_ref'] == dict(runtime_ref)
    assert (manifest['catalog_id'], manifest['catalog_version'], manifest['organization_id'], manifest['usage_scope']) == (
        catalog['catalog_id'], catalog['catalog_version'], catalog['organization_id'], catalog['usage_scope'],
    )
    request_hash = checksum({'receipt_sha256': receipt_sha256, 'published_by': actor})
    row = connection.execute('''
        INSERT INTO m5_catalogs
            (catalog_id,catalog_version,organization_id,usage_scope,package_db_id,manifest_json,
             manifest_checksum,status,published_by,decision_basis,idempotency_key,request_hash,published_at)
        VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,'published',%s,%s,'path-start-release-mirror',%s,NOW())
        RETURNING id
    ''', (catalog['catalog_id'], catalog['catalog_version'], catalog['organization_id'], catalog['usage_scope'],
          package_db_id, json.dumps(manifest, ensure_ascii=False), catalog['manifest_checksum'],
          actor, catalog['decision_basis'], request_hash)).fetchone()
    catalog_db_id = row['id']
    assert catalog_db_id == catalog['id'], 'RELEASE_CATALOG_ID_MISMATCH'
    for case_version_id in plan['case_version_ids']:
        connection.execute('''
            INSERT INTO m5_catalog_case_versions (catalog_db_id,case_version_id,runtime_rule_version_id)
            VALUES (%s,%s,%s)
        ''', (catalog_db_id, case_version_id, runtime_id))
    assert catalog_readback(connection, catalog_db_id)['manifest'] == manifest, 'RELEASE_CATALOG_MISMATCH'
    return catalog_db_id


def seed_release(connection, actor, *, receipt_reference=None):
    from tests.path_start_release_source import load_release_receipt, load_release_reference
    from scripts.plan_specialist_program_release import build_admitted_materials, PACKAGE_DIR

    # DECISION_BASIS is taken from the verified release, never from CLI guesses.
    source, selected = (load_release_receipt() if receipt_reference is None
                        else load_release_reference(receipt_reference))
    basis = source['catalog']['decision_basis']
    package, runtime, evidence_refs = build_admitted_materials(basis)
    from Api.m5_case_runtime import checksum
    from Api.m5_storage import import_package
    from Api.m5_runtime_rules import import_runtime_rule_version
    from scripts.build_m5_sales_package import build_execution_rules
    case_ids = [case['id'] for case in source['cases']]
    assert case_ids == list(range(case_ids[0], case_ids[0] + 9)), 'RELEASE_NONCONTIGUOUS_IDS'
    reserve_release_ids(connection, 'm5_case_versions', case_ids[0])
    imported = import_package(connection, package=package,
        manifest=json.loads((PACKAGE_DIR / 'manifest.json').read_text()),
        execution_rules=json.loads((PACKAGE_DIR / 'execution-rules.json').read_text()))
    runtime = import_runtime_rule_version(connection, runtime,
        build_execution_rules(package['cases'], runtime['bindings']))
    local_cases = connection.execute('SELECT * FROM m5_case_versions WHERE package_id=%s ORDER BY case_id',
        (imported['package_db_id'],)).fetchall()
    assert len(local_cases) == len(source['cases']) == 9
    for local, original in zip(local_cases, source['cases']):
        assert all(local[key] == original[key] for key in
            ('id', 'case_id', 'case_version', 'content_checksum', 'status', 'base_role')), 'RELEASE_CASE_MISMATCH'
        assert checksum(local['content_json']) == original['content_checksum']
        for qa in original['qa_evidence']:
            assert qa['evidence_json']['evidence_ref'] == evidence_refs[qa['scope']]
            connection.execute('''INSERT INTO m5_qa_evidence
                (case_version_id,scope,result,evidence_json,evidence_checksum)
                VALUES(%s,%s,%s,%s::jsonb,%s)''', (local['id'], qa['scope'], qa['result'],
                    json.dumps(qa['evidence_json'], ensure_ascii=False), qa['evidence_checksum']))
    catalog_db_id = _mirror_catalog(
        connection, catalog=source['catalog'], package_db_id=imported['package_db_id'],
        case_ids=case_ids, runtime_id=runtime['id'], actor=actor, receipt_sha256=selected['sha256'],
    )
    from Api.assessment_authoring_service import assessment_authoring_service
    config = source['configuration']
    reserve_release_ids(connection, 'assessment_configurations', config['id'])
    other = assessment_authoring_service.create_configuration(connection,
        code=config['code'], name=config['name'], methodology_version_id=config['methodology_version_id'],
        scenario_version_id=config['scenario_version_id'], catalog_version_id=catalog_db_id,
        actor_user_id=actor, comment='Owned mirror of independently verified published PATH release')
    other = assessment_authoring_service.publish_configuration(connection,
        configuration_id=other['id'], make_default=False, actor_user_id=actor,
        comment='Technical test mirror; no new methodology approval')
    assert all(other[key] == config[key] for key in config), 'RELEASE_CONFIGURATION_MISMATCH'
    role = source['roles'][0]
    local_role = connection.execute('''SELECT p.code,v.version,v.checksum FROM assessment_role_profile_versions v
        JOIN assessment_role_profiles p ON p.id=v.role_profile_id WHERE v.id=%s''', (role['id'],)).fetchone()
    assert all(local_role[key] == role[key] for key in ('code', 'version', 'checksum')), 'RELEASE_ROLE_MISMATCH'
    program = source['program']
    from Api.assessment_programs import definition_checksum
    assert program['definition_checksum'] == definition_checksum(code=program['code'], version=program['version'],
        name=program['name'], assignment_ref=program['assignment_ref'], mode=program['mode'],
        configuration_id=other['id'], catalog_version_id=catalog_db_id,
        role_version_ids=[role['id']], source_refs=program['source_refs_json'])
    reserve_release_ids(connection, 'assessment_program_definitions', program['id'])
    program_id = connection.execute('''INSERT INTO assessment_program_definitions
        (code,version,name,assignment_ref,mode,status,assessment_configuration_id,catalog_version_id,
         source_refs_json,definition_checksum,published_by_user_id)
        VALUES(%s,%s,%s,%s,%s,'draft',%s,%s,%s::jsonb,%s,%s) RETURNING id''',
        (program['code'], program['version'], program['name'], program['assignment_ref'], program['mode'],
         other['id'], catalog_db_id, json.dumps(program['source_refs_json']),
         program['definition_checksum'], actor)).fetchone()['id']
    connection.execute('''INSERT INTO assessment_program_allowed_roles
        (program_definition_id,role_profile_version_id,display_order) VALUES(%s,%s,0)''', (program_id, role['id']))
    connection.execute("UPDATE assessment_program_definitions SET status='published',published_at=NOW() WHERE id=%s", (program_id,))
    from tests.assessment_first_case_evidence import source_provenance
    provenance = source_provenance(connection, catalog_db_id)
    provenance.update(release=source, release_receipt_sha256=selected['sha256'],
        published_release_ref=selected,
        origin_contract_note='Original published QA origins preserved; no synthetic human_review substitution',
        methodology_approval='NO_NEW_APPROVAL; reused owner decision and existing published QA')
    return other, role['id'], program_id, provenance
