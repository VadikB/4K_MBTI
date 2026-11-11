"""F02: synthetic graph and independent SQL readback on a marker-owned stand."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.test_stand import environment, owned


def history(c, user_id, org):
    """Persist a synthetic graph; no assessment, email or AI call is made."""
    profile = c.execute('SELECT id FROM assessment_personalized_profiles WHERE user_id=%s', (user_id,)).fetchone()['id']
    assignment = c.execute("""INSERT INTO organization_assessment_assignments
        (organization_id,recipient_user_id,assignment_ref,operation_id,request_fingerprint)
        VALUES(%s,%s,%s,%s,'synthetic-f02') RETURNING id""", (org, user_id, 'f02-'+str(user_id), str(uuid4()))).fetchone()['id']
    cycle = c.execute("""INSERT INTO m5_cycles
        (cycle_id,owner_user_id,organization_id,assignment_id,personalized_profile_id,profile_ref_json,
         selected_role_ref_json,target_set_json,target_set_checksum,time_budget_seconds,
         calendar_window_seconds,parameter_sources_json,usage_scope,status,created_by)
        VALUES(%s,%s,%s,%s,%s,'{}','{}','[]','synthetic',7200,259200,'{}','assessment','active',%s)
        RETURNING id""", (uuid4(), user_id, org, assignment, profile, user_id)).fetchone()['id']
    session = c.execute("""INSERT INTO m5_cycle_sessions(session_id,cycle_db_id,ordinal,status,created_by)
        VALUES(%s,%s,1,'active',%s) RETURNING id""", (uuid4(), cycle, user_id)).fetchone()['id']
    case = c.execute('SELECT id FROM m5_case_versions ORDER BY id LIMIT 1').fetchone()['id']
    situation = c.execute("""INSERT INTO m5_assessment_situations
        (assessment_situation_id,case_version_id,personalized_profile_id,cycle_db_id,session_db_id,
         status,snapshot_json,execution_payload_json,snapshot_checksum)
        VALUES(%s,%s,%s,%s,%s,'active','{}','{}',%s) RETURNING id""",
        (uuid4(), case, profile, cycle, session, str(uuid4()))).fetchone()['id']
    turn = c.execute("""INSERT INTO m5_dialogue_turns
        (assessment_situation_db_id,turn_id,sequence_no,speaker_type,speaker_id,content_text,request_id)
        VALUES(%s,%s,1,'assessee','synthetic','Synthetic deletion fixture',%s) RETURNING id""",
        (situation, uuid4(), str(uuid4()))).fetchone()['id']
    c46, calculation, result, revision, report = [uuid4() for _ in range(5)]
    c.execute("""INSERT INTO m7_c46_revisions
        (id,cycle_db_id,revision_no,status,composition_checksum,payload_json,payload_checksum)
        VALUES(%s,%s,1,'collection_snapshot','synthetic','{}','synthetic')""", (c46, cycle))
    c.execute("""INSERT INTO m6_cycle_calculations
        (id,cycle_db_id,revision_no,request_key,request_hash,composition_checksum,input_json,input_hash,
         result_json,result_hash,c56_json,c56_hash,created_by)
        VALUES(%s,%s,1,'synthetic','synthetic','synthetic','{}','synthetic','{}','synthetic','{}','synthetic',%s)""",
        (calculation, cycle, user_id))
    c.execute('INSERT INTO m8_results(id,cycle_db_id) VALUES(%s,%s)', (result, cycle))
    c.execute("""INSERT INTO m8_result_revisions
        (id,results_id,revision_no,calculation_id,c46_revision_id,composition_checksum,payload_json,payload_checksum,reason,created_by)
        VALUES(%s,%s,1,%s,%s,'synthetic','{}','synthetic','synthetic',%s)""", (revision, result, calculation, c46, user_id))
    c.execute("""INSERT INTO m8_reports
        (id,result_revision_id,revision_no,audience,template_version,c67_json,c67_checksum,status,request_key,request_hash,created_by)
        VALUES(%s,%s,1,'assessee','synthetic','{}','synthetic','ready','synthetic','synthetic',%s)""", (report, revision, user_id))
    job = c.execute("""INSERT INTO assessment_preparation_jobs(operation_id,user_id,user_payload_json,personalized_profile_id)
        VALUES(%s,%s,'{}',%s) RETURNING id""", (str(uuid4()), user_id, profile)).fetchone()['id']
    # Capture exact keys independently of the purge plan. Later readback uses these keys.
    return {table: value for table, value in [
        ('organization_assessment_assignments', assignment), ('assessment_personalized_profiles', profile),
        ('m5_cycles', cycle), ('m5_cycle_sessions', session), ('m5_assessment_situations', situation),
        ('m5_dialogue_turns', turn), ('m7_c46_revisions', c46), ('m6_cycle_calculations', calculation),
        ('m8_results', result), ('m8_result_revisions', revision), ('m8_reports', report),
        ('assessment_preparation_jobs', job)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'readback'])
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--internal', action='store_true')
    args = parser.parse_args()
    state = json.loads(args.state.read_text())
    with owned(state):
        pass
    if not args.internal:
        result = subprocess.run([sys.executable, __file__, args.action, '--state', str(args.state), '--internal'],
            env=environment(state), cwd=ROOT, capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError(result.stderr)
        print(result.stdout.strip().split('\n')[-1])
        return
    assert os.getenv('AGENT4K_ISOLATED_STAND') == '1'
    from psycopg import sql
    from Api.database import close_connection_pool, get_connection
    from Api.web_session_service import web_session_service
    from Api.routes import SESSION_COOKIE_NAME
    try:
        with get_connection() as c:
            if args.action == 'prepare':
                org = c.execute("SELECT id FROM organizations WHERE code='e102_synthetic'").fetchone()['id']
                other_org = c.execute("INSERT INTO organizations(code,name) VALUES('f02_control','Synthetic F02 control') RETURNING id").fetchone()['id']
                users = {}
                for label, email in [('super', 'superadmin@example.test')]:
                    users[label] = dict(c.execute('SELECT id,email FROM users WHERE email=%s', (email,)).fetchone())
                for label in ['member', 'dual', 'admin', 'foreign', 'last_admin', 'scope', 'legacy']:
                    email = f'f02-{label}@example.test'
                    uid = c.execute('INSERT INTO users(email,full_name) VALUES(%s,%s) RETURNING id',
                        (email, 'Synthetic F02 '+label)).fetchone()['id']
                    c.execute("INSERT INTO user_identities(user_id,provider,email,is_primary,is_verified,verified_at) VALUES(%s,'email_magic_link',%s,TRUE,TRUE,NOW())", (uid, email))
                    users[label] = {'id': uid, 'email': email}
                    c.execute("""INSERT INTO organization_memberships(organization_id,user_id,role,is_participant,admission_source,admitted_at)
                        VALUES(%s,%s,%s,%s,'admin_add',NOW())""", (other_org if label in ['foreign', 'last_admin'] else org,
                            uid, 'admin' if label in ['admin', 'last_admin'] else 'member', label != 'legacy'))
                from Api.assessment_contexts import create_user_context_draft, confirm_user_context, create_personalized_profile
                from Api.assessment_role_profiles import select_role_profile_for_user
                from Api.auth_service import _hash_password
                source = c.execute('SELECT * FROM assessment_personalized_profiles ORDER BY id LIMIT 1').fetchone()
                for label in ['member', 'dual']:
                    uid = users[label]['id']
                    select_role_profile_for_user(c, user_id=uid, version_id=source['role_profile_version_id'])
                    version = create_user_context_draft(c, user_id=uid, identity={'full_name': 'Synthetic F02'},
                        professional={'position_or_status': 'Synthetic specialist'})
                    confirm_user_context(c, version_id=version, user_id=uid)
                    create_personalized_profile(c, user_id=uid, assessment_configuration_id=source['assessment_configuration_id'],
                        organization_context_version_id=source['organization_context_version_id'],
                        role_profile_version_id=source['role_profile_version_id'], user_context_version_id=version)
                    profile = c.execute("INSERT INTO user_role_profiles(user_id,raw_position) VALUES(%s,'Synthetic F02') RETURNING id", (uid,)).fetchone()['id']
                    c.execute('UPDATE users SET active_profile_id=%s WHERE id=%s', (profile, uid))
                    salt, digest = _hash_password(state['password'])
                    c.execute('INSERT INTO auth_password_credentials(user_id,email,password_hash,password_salt) VALUES(%s,%s,%s,%s)',
                        (uid, users[label]['email'], digest, salt))
                c.execute("UPDATE organization_memberships SET role='admin' WHERE user_id=%s", (users['dual']['id'],))
                c.execute("""INSERT INTO organization_invitations(organization_id,created_by_user_id,token_hash,expires_at)
                    VALUES(%s,%s,%s,NOW()+INTERVAL '1 day')""", (other_org, users['scope']['id'], str(uuid4())))
                for label in ['member', 'dual']:
                    users[label]['rows'] = history(c, users[label]['id'], org)
                state['f02'] = {'organization_id': org, 'other_organization_id': other_org, 'users': users}
                c.commit()
                args.state.write_text(json.dumps(state, default=str))
                # Synthetic sessions are returned privately to Playwright, never exported as evidence.
                print(json.dumps({**state['f02'], 'cookie_name': SESSION_COOKIE_NAME,
                    'sessions': {label: web_session_service.create_session(users[label]['id'])
                        for label in ['super', 'admin', 'member']}}, default=str))
            else:
                result = {}
                for label, user in state['f02']['users'].items():
                    uid = user['id']
                    checks = {table: c.execute(sql.SQL('SELECT count(*) AS n FROM {} WHERE id=%s').format(sql.Identifier(table)),
                        (key,)).fetchone()['n'] for table, key in user.get('rows', {}).items()}
                    for table, column in [('users', 'id'), ('organization_memberships', 'user_id'),
                            ('auth_password_credentials', 'user_id'), ('user_identities', 'user_id'),
                            ('user_role_profiles', 'user_id'), ('web_user_sessions', 'user_id')]:
                        checks[table] = c.execute(sql.SQL('SELECT count(*) AS n FROM {} WHERE {}=%s').format(
                            sql.Identifier(table), sql.Identifier(column)), (uid,)).fetchone()['n']
                    result[label] = {'counts': checks, 'receipts': [dict(row) for row in c.execute(
                        "SELECT operation_id,target_id,actor_user_id FROM data_deletion_receipts WHERE target_type='account' AND target_id=%s", (uid,)).fetchall()]}
                result['organizations'] = [dict(row) for row in c.execute('SELECT id,code,name,is_active FROM organizations ORDER BY id').fetchall()]
                print(json.dumps(result, default=str))
    finally:
        close_connection_pool()


if __name__ == '__main__':
    main()
