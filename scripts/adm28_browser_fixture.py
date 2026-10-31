"""Synthetic org-admin inputs for an owned local test stand; no provider calls."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def seed(state):
    from Api.database import get_connection
    from Api.auth_service import _hash_password
    from Api.assessment_authoring_service import assessment_authoring_service
    from Api import assessment_programs
    from Api.m5_catalog_integrity import publish_catalog
    with get_connection() as connection:
        organization_id = connection.execute("""INSERT INTO organizations(code,name)
            VALUES('adm28_synthetic','Синтетическая организация ADM28') RETURNING id""").fetchone()['id']
        admin_user_id = None
        for email, role in [('admin@example.test', 'admin'), ('colleague@example.test', 'member')]:
            user_id = connection.execute('INSERT INTO users(full_name,email,job_description) VALUES(%s,%s,%s) RETURNING id',
                                         ('Синтетический ' + role, email, 'Синтетический специалист')).fetchone()['id']
            if role == 'admin':
                admin_user_id = user_id
            connection.execute("""INSERT INTO organization_memberships(
                organization_id,user_id,role,admission_source,admitted_at)
                VALUES(%s,%s,%s,'admin_add',NOW())""", (organization_id, user_id, role))
            salt, digest = _hash_password(state['password'])
            connection.execute('INSERT INTO auth_password_credentials(user_id,email,password_hash,password_salt) VALUES(%s,%s,%s,%s)',
                               (user_id, email, digest, salt))
            connection.execute("""INSERT INTO user_identities(user_id,provider,email,is_primary,is_verified,verified_at)
                VALUES(%s,'email_magic_link',%s,TRUE,TRUE,NOW())""", (user_id, email))
        source_configuration = connection.execute("""SELECT configuration.*,
                catalog.id AS source_catalog_id,catalog.package_db_id
            FROM assessment_configurations configuration
            JOIN m5_catalogs catalog ON catalog.id=configuration.catalog_version_id
            WHERE configuration.code='e102_controlled_catalog'
              AND configuration.status='published' AND catalog.status='published'
              AND catalog.usage_scope='assessment'
            LIMIT 1""").fetchone()
        specialist = connection.execute("""SELECT version.id
            FROM assessment_role_profile_versions version
            JOIN assessment_role_profiles profile ON profile.id=version.role_profile_id
            WHERE profile.code='specialist_expert' AND version.status='published'
              AND version.methodology_version='1.1'
            ORDER BY version.version DESC LIMIT 1""").fetchone()
        if not source_configuration or not specialist or not admin_user_id:
            raise RuntimeError('ADM28 fixture requires one admitted assessment catalog and published specialist role')
        case_ids = [row['case_version_id'] for row in connection.execute(
            'SELECT case_version_id FROM m5_catalog_case_versions WHERE catalog_db_id=%s ORDER BY case_version_id',
            (source_configuration['source_catalog_id'],)).fetchall()]
        catalog = publish_catalog(connection, catalog_id='adm28-specialist-pilot', catalog_version='1.0',
            package_db_id=source_configuration['package_db_id'], case_version_ids=case_ids,
            usage_scope='assessment', organization_id=organization_id, published_by=admin_user_id,
            decision_basis='Synthetic ADM28 isolated binding', idempotency_key='adm28-specialist-pilot-catalog')
        configuration = assessment_authoring_service.create_configuration(connection,
            code='adm28_specialist_pilot', name='ADM28 synthetic Specialist pilot',
            methodology_version_id=source_configuration['methodology_version_id'],
            scenario_version_id=source_configuration['scenario_version_id'],
            catalog_version_id=catalog['catalog_db_id'], actor_user_id=admin_user_id,
            comment='Synthetic ADM28 isolated binding')
        configuration = assessment_authoring_service.publish_configuration(connection,
            configuration_id=configuration['id'], make_default=False, actor_user_id=admin_user_id,
            comment='Synthetic ADM28 isolated binding')
        source_refs = {
            'methodology_version_id': int(configuration['methodology_version_id']),
            'scenario_version_id': int(configuration['scenario_version_id']),
            'prompt_bundle_checksum': configuration['prompt_bundle_checksum'],
        }
        program_checksum = assessment_programs.definition_checksum(
            code='adm28-specialist-pilot', version='1.0', name='ADM28 synthetic Specialist pilot',
            assignment_ref='ADM28 isolated', mode='dialogue', configuration_id=configuration['id'],
            role_version_ids=[specialist['id']], catalog_version_id=configuration['catalog_version_id'],
            source_refs=source_refs,
        )
        program_id = connection.execute("""INSERT INTO assessment_program_definitions
            (code,version,name,assignment_ref,mode,status,assessment_configuration_id,
             catalog_version_id,source_refs_json,definition_checksum,published_by_user_id)
            VALUES('adm28-specialist-pilot','1.0','ADM28 synthetic Specialist pilot',
             'ADM28 isolated','dialogue','draft',%s,%s,%s::jsonb,%s,%s) RETURNING id""",
            (configuration['id'], configuration['catalog_version_id'], json.dumps(source_refs),
             program_checksum, admin_user_id)).fetchone()['id']
        connection.execute("""INSERT INTO assessment_program_allowed_roles
            (program_definition_id,role_profile_version_id,display_order) VALUES(%s,%s,0)""",
            (program_id, specialist['id']))
        connection.execute("""UPDATE assessment_program_definitions
            SET status='published',published_at=NOW() WHERE id=%s""", (program_id,))
        assessment_programs.connect(connection, organization_id=organization_id,
            program_definition_id=program_id, actor_user_id=admin_user_id,
            operation_id='adm28-connect-specialist-pilot')
        connection.execute("""INSERT INTO organization_assessment_pilot_bindings
            (organization_id,assignment_ref,binding_version,assessment_configuration_id,
             role_profile_version_id,configured_by_user_id)
            VALUES(%s,'ADM28 isolated','specialist-pilot/1',%s,%s,%s)""",
            (organization_id, configuration['id'], specialist['id'], admin_user_id))
        connection.commit()
    print('Synthetic organization/admin/colleague ready; no assessments started')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--isolated-child', action='store_true')
    args = parser.parse_args()
    from scripts.test_stand import environment, owned
    state = json.loads(args.state.read_text())
    with owned(state): pass
    if args.isolated_child:
        if os.getenv('AGENT4K_ISOLATED_STAND') != '1': raise ValueError('ISOLATED_STAND_REQUIRED')
        seed(state)
    else:
        subprocess.run([sys.executable, __file__, '--state', str(args.state), '--isolated-child'],
                       env=environment(state), cwd=ROOT, check=True)
