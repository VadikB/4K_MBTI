"""Synthetic admin + published test sources; target participant is never pre-created here."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def seed(state_path, state):
    from scripts.test_stand_seed import seed as source_seed
    source_seed(state)
    from Api.database import get_connection
    from Api.auth_service import _hash_password
    from Api.assessment_authoring_service import assessment_authoring_service
    from Api import assessment_programs
    with get_connection() as c:
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
        other = assessment_authoring_service.create_configuration(c, code='path29_browser_explicit_second',
            name='Synthetic second explicit configuration', methodology_version_id=source['methodology_version_id'],
            scenario_version_id=source['scenario_version_id'], catalog_version_id=source['catalog_version_id'],
            actor_user_id=actor, comment='Synthetic owned browser source selection only')
        assessment_authoring_service.publish_configuration(c, configuration_id=other['id'], make_default=False,
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
        assessment_programs.connect(c, organization_id=org, program_definition_id=program_id,
            actor_user_id=actor, operation_id='path29-connect-specialist')
        c.execute("""INSERT INTO organization_assessment_pilot_bindings
            (organization_id,assignment_ref,binding_version,assessment_configuration_id,
             role_profile_version_id,configured_by_user_id)
            VALUES(%s,'PATH29 browser','specialist-pilot/1',%s,%s,%s)""",
            (org, other['id'], role_id, actor))
        assert c.execute("SELECT id FROM users WHERE email='path29-new@example.test'").fetchone() is None
        c.commit()
    state['path29'] = {'organization_id': org, 'configuration_id': other['id'], 'program_id': program_id,
                      'role_version_id': role_id,
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
        subprocess.run([sys.executable, __file__, '--state', str(args.state), '--child'],
                       env=environment(state), cwd=ROOT, check=True)
