"""Synthetic admin + published test sources; target participant is never pre-created here."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def seed(state_path, state):
    full_path = state.get('path29_full_path') is True
    if not full_path:
        from scripts.test_stand_seed import seed as source_seed
        source_seed(state)
    from Api.database import get_connection
    from Api.auth_service import _hash_password
    from Api.assessment_authoring_service import assessment_authoring_service
    from Api.m5_catalog_integrity import publication_plan, publish_catalog
    from Api.m5_case_runtime import checksum as runtime_checksum
    from Api.m5_runtime_rules import import_runtime_rule_version, load_runtime_rule_package
    from Api.m5_storage import import_package
    from scripts.build_m5_functional_package import OUTPUT as FUNCTIONAL_OUTPUT
    from scripts.build_m5_sales_package import build_execution_rules
    from Api import assessment_programs
    with get_connection() as c:
        org = None
        if full_path:
            # No organization, member, questionnaire or profile is pre-created.
            actor = c.execute("""INSERT INTO users(full_name,email)
                VALUES('Синтетический суперадминистратор','superadmin@example.test')
                RETURNING id""").fetchone()['id']
            salt, digest = _hash_password(state['password'])
            c.execute('INSERT INTO auth_password_credentials(user_id,email,password_hash,password_salt) VALUES(%s,%s,%s,%s)',
                (actor, 'superadmin@example.test', digest, salt))
            c.execute("""INSERT INTO user_identities(user_id,provider,email,is_primary,is_verified,verified_at)
                VALUES(%s,'email_magic_link','superadmin@example.test',TRUE,TRUE,NOW())""", (actor,))
            from Api.assessment_methodology_publication import publish_m2_qa_configuration
            from Api.assessment_role_profiles import publish_base_roles
            basis = 'Disposable synthetic source loading; not methodology approval or CURRENT'
            publication = publish_m2_qa_configuration(c, published_by_user_id=actor, decision_basis=basis)
            role_root = ROOT / 'assessment_definitions/role_profiles/competencies_4k/1.1'
            publish_base_roles(c, package=json.loads((role_root / 'base_roles.json').read_text()),
                manifest=json.loads((role_root / 'manifest.json').read_text()),
                published_by_user_id=actor, decision_basis=basis)
            source = c.execute('SELECT * FROM assessment_configurations WHERE id=%s',
                               (publication['configuration_id'],)).fetchone()
        else:
            org = c.execute("SELECT id FROM organizations WHERE code='e102_synthetic'").fetchone()['id']
            actor = c.execute("""INSERT INTO users(full_name,email,job_description)
                VALUES('Синтетический администратор PATH29','path29-admin@example.test','Синтетический координатор') RETURNING id""").fetchone()['id']
            c.execute("""INSERT INTO organization_memberships(organization_id,user_id,role,admission_source,admitted_at)
                VALUES(%s,%s,'admin','admin_add',NOW())""", (org, actor))
            salt, digest = _hash_password(state['password'])
            c.execute('INSERT INTO auth_password_credentials(user_id,email,password_hash,password_salt) VALUES(%s,%s,%s,%s)',
                (actor, 'path29-admin@example.test', digest, salt))
            c.execute("""INSERT INTO user_identities(user_id,provider,email,is_primary,is_verified,verified_at)
                VALUES(%s,'email_magic_link','path29-admin@example.test',TRUE,TRUE,NOW())""", (actor,))
            source = c.execute("SELECT * FROM assessment_configurations WHERE code='e102_controlled_catalog'").fetchone()
        catalog_version_id = source['catalog_version_id']
        if full_path:
            # PATH-START-01 diagnostic input: use the existing functional PM-03
            # preparation contract. The repository package remains immutable;
            # only a disposable DB copy receives technical FROZEN/admission state.
            package = json.loads((FUNCTIONAL_OUTPUT / 'case-package.json').read_text())
            manifest = json.loads((FUNCTIONAL_OUTPUT / 'manifest.json').read_text())
            legacy_rules = json.loads((FUNCTIONAL_OUTPUT / 'execution-rules.json').read_text())
            runtime_package = FUNCTIONAL_OUTPUT.parent.parent / 'functional-personalization-runtime/1.2.0'
            runtime_bindings = load_runtime_rule_package(
                runtime_package, package['cases'], expected_case_package_version='0.5')
            fixture_package = copy.deepcopy(package)
            fixture_bindings = copy.deepcopy(runtime_bindings)
            for case in fixture_package['cases']:
                case['status'] = 'FROZEN'
                case['author_case']['Status'] = 'FROZEN'
                fixture_bindings['bindings']['case_bindings'][case['case_id']]['case_checksum'] = \
                    runtime_checksum(case)
            imported = import_package(c, package=fixture_package, manifest=manifest,
                                      execution_rules=legacy_rules)
            runtime = import_runtime_rule_version(
                c, fixture_bindings,
                build_execution_rules(fixture_package['cases'], fixture_bindings['bindings']))
            selected = c.execute("""SELECT * FROM m5_case_versions
                WHERE package_id=%s AND case_id='CASE.SPEC.02'""",
                (imported['package_db_id'],)).fetchone()
            if not selected:
                raise RuntimeError('PATH_START_FUNCTIONAL_CASE_NOT_IMPORTED')
            basis = ('PATH-START-01 v1.1 disposable diagnostic admission of exact '
                     'functional package content; not normative/GC publication')
            for scope in ('case_format', 'case_dialogue', 'assessment_situation'):
                evidence = {'schema_version': 1, 'eligibility': 'user_admission', 'scope': scope,
                    'result': 'PASS', 'case_ref': {'id': selected['case_id'],
                    'version': selected['case_version'], 'checksum': selected['content_checksum']},
                    'base_role': selected['base_role'], 'usage_scopes': ['assessment'],
                    'origin': {'type': 'human_review',
                               'actor_ref': 'synthetic-fixture:assessment-first-case/1.1',
                               'synthetic': True, 'methodology_approval': False},
                    'decision_basis': basis}
                c.execute("""INSERT INTO m5_qa_evidence
                    (case_version_id,scope,result,evidence_json,evidence_checksum)
                    VALUES(%s,%s,'PASS',%s::jsonb,%s)""",
                    (selected['id'], scope, json.dumps(evidence, ensure_ascii=False),
                     runtime_checksum(evidence)))
            plan = publication_plan(c, package_db_id=imported['package_db_id'],
                case_version_ids=[selected['id']], usage_scope='assessment', organization_id=None,
                runtime_rule_version_id=runtime['id'])
            if plan['publishable'] is not True:
                raise RuntimeError('PATH_START_FUNCTIONAL_CATALOG_NOT_PUBLISHABLE:' +
                                   json.dumps(plan['decisions'], ensure_ascii=False))
            shared = publish_catalog(c, catalog_id='path-start-functional-diagnostic',
                catalog_version='1.0', package_db_id=imported['package_db_id'],
                case_version_ids=[selected['id']], usage_scope='assessment', organization_id=None,
                published_by=actor, decision_basis=basis,
                idempotency_key='path-start-functional-diagnostic-v1',
                runtime_rule_version_id=runtime['id'])
            catalog_version_id = shared['catalog_db_id']
        other = assessment_authoring_service.create_configuration(c, code='path29_browser_explicit_second',
            name='Synthetic second explicit configuration', methodology_version_id=source['methodology_version_id'],
            scenario_version_id=source['scenario_version_id'], catalog_version_id=catalog_version_id,
            actor_user_id=actor, comment='Synthetic owned browser source selection only')
        other = assessment_authoring_service.publish_configuration(c, configuration_id=other['id'], make_default=False,
            actor_user_id=actor, comment='Synthetic owned browser source selection only')
        role_id = c.execute('''SELECT v.id FROM assessment_role_profile_versions v
            JOIN assessment_role_profiles r ON r.id=v.role_profile_id WHERE r.code=%s AND v.status='published' ''',
            ('specialist_expert',)).fetchone()['id']
        source_refs = {
            'methodology_version_id': int(other['methodology_version_id']),
            'scenario_version_id': int(other['scenario_version_id']),
            'prompt_bundle_checksum': other['prompt_bundle_checksum'],
        }
        program_checksum = assessment_programs.definition_checksum(
            code='path29-browser-specialist', version='1.0', name='PATH29 browser Specialist',
            assignment_ref='PATH29 browser', mode='dialogue', configuration_id=other['id'],
            role_version_ids=[role_id], catalog_version_id=other['catalog_version_id'],
            source_refs=source_refs,
        )
        program_id = c.execute("""INSERT INTO assessment_program_definitions
            (code,version,name,assignment_ref,mode,status,assessment_configuration_id,
             catalog_version_id,source_refs_json,definition_checksum,published_by_user_id)
            VALUES('path29-browser-specialist','1.0','PATH29 browser Specialist',
             'PATH29 browser','dialogue','draft',%s,%s,%s::jsonb,%s,%s) RETURNING id""",
            (other['id'], other['catalog_version_id'], json.dumps(source_refs),
             program_checksum, actor)).fetchone()['id']
        c.execute("""INSERT INTO assessment_program_allowed_roles
            (program_definition_id,role_profile_version_id,display_order) VALUES(%s,%s,0)""",
            (program_id, role_id))
        c.execute("""UPDATE assessment_program_definitions
            SET status='published',published_at=NOW() WHERE id=%s""", (program_id,))
        if full_path:
            counts = {name: c.execute('SELECT count(*) AS n FROM ' + table).fetchone()['n']
                for name, table in {
                    'users': 'users', 'organizations': 'organizations',
                    'memberships': 'organization_memberships',
                    'profiles': 'assessment_personalized_profiles', 'cycles': 'm5_cycles',
                    'assignments': 'organization_assessment_assignments',
                }.items()}
            if counts != {'users': 1, 'organizations': 0, 'memberships': 0,
                          'profiles': 0, 'cycles': 0, 'assignments': 0}:
                raise RuntimeError('FULL_PATH_BOOTSTRAP_NOT_MINIMAL:' + json.dumps(counts))
            from tests.assessment_first_case_evidence import source_provenance
            provenance = source_provenance(c, catalog_version_id)
            provenance['initial_counts'] = counts
            (state_path.parent / 'source-provenance.json').write_text(
                json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')
        if not full_path:
            assessment_programs.connect(c, organization_id=org, program_definition_id=program_id,
                actor_user_id=actor, operation_id='path29-connect-specialist')
            c.execute("""INSERT INTO organization_assessment_pilot_bindings
                (organization_id,assignment_ref,binding_version,assessment_configuration_id,
                 role_profile_version_id,configured_by_user_id)
                VALUES(%s,'PATH29 browser','specialist-pilot/1',%s,%s,%s)""",
                (org, other['id'], role_id, actor))
        assert c.execute("SELECT id FROM users WHERE email='path29-new@example.test'").fetchone() is None
        c.commit()
    state['path29'] = {'organization_id': None if full_path else org, 'configuration_id': other['id'], 'program_id': program_id,
                      'role_version_id': role_id,
                      'input_mode': 'functional-diagnostic' if full_path else 'legacy-static',
                      'admin_email': 'path29-admin@example.test', 'participant_email': 'path29-new@example.test'}
    state_path.write_text(json.dumps(state))
    print('PATH29 synthetic Specialist binding/admin ready; target participant/M4/Cycle absent')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', type=Path, required=True)
    p.add_argument('--child', action='store_true')
    args = p.parse_args()
    from scripts.test_stand import owned, environment
    state = json.loads(args.state.read_text())
    with owned(state):
        pass
    if args.child:
        if os.getenv('AGENT4K_ISOLATED_STAND') != '1':
            raise RuntimeError('ISOLATED_STAND_REQUIRED')
        seed(args.state, state)
    else:
        if os.getenv('P4K_FULL_PATH') == '1':
            state['path29_full_path'] = True
            args.state.write_text(json.dumps(state))
        subprocess.run([sys.executable, __file__, '--state', str(args.state), '--child'],
                       env=environment(state), cwd=ROOT, check=True)
