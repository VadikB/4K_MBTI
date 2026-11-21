"""Synthetic browser setup/readback using the SAME real HTTP/PG test inputs."""
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


def seed_cabinet(scope):
    from Api.database import get_connection
    from Api.m5_case_runtime import checksum
    from Api.preparation_observation import reference
    from psycopg.types.json import Jsonb
    from tests.path_admin_contract_checks import confirm_participant_profile, payload, session

    names = {
        'sent': 'Письмо отправлено',
        'running': 'Подготовка идёт',
        'failed': 'Сбой подготовки',
        'active': 'Проходит оценку',
        'ready': 'Полный результат',
        'limited': 'Ограниченный результат',
        'no_result': 'Результат без балла',
        'unavailable': 'Публикация недоступна',
    }
    members = {'assign': scope['member'], 'unknown': scope['second']}
    invitations = {}
    with get_connection() as c:
        c.execute("UPDATE users SET full_name='Участник для назначения' WHERE id=%s", (members['assign'],))
        c.execute("UPDATE users SET full_name='Отправка не подтверждена' WHERE id=%s", (members['unknown'],))
        for key, name in names.items():
            email = f'{key}-{uuid4().hex[:12]}@example.test'
            members[key] = c.execute(
                "INSERT INTO users(email,full_name,job_description) VALUES(%s,%s,'Синтетическая должность') RETURNING id",
                (email, name)).fetchone()['id']
            c.execute("INSERT INTO organization_memberships(organization_id,user_id,role,admission_source,admitted_at) "
                      "VALUES(%s,%s,'member','admin_add',NOW())", (scope['org'], members[key]))
        for key, delivery in [('sent', 'accepted'), ('unknown', 'sending')]:
            operation = 'cabinet-' + uuid4().hex
            email = c.execute('SELECT email FROM users WHERE id=%s', (members[key],)).fetchone()['email']
            invitation = c.execute("""INSERT INTO organization_invitations
                (organization_id,token_hash,expires_at,created_by_user_id,recipient_email,purpose,
                 delivery_status,request_id,assignment_ref)
                VALUES(%s,%s,NOW()+INTERVAL '2 days',%s,%s,'personal_registration',%s,%s,%s) RETURNING id""",
                (scope['org'], checksum(operation), scope['admin'], email, delivery, operation, scope['ref'])).fetchone()
            invitations[key] = {'id': invitation['id'], 'operation': operation, 'email': email}
        c.commit()
    scoped_members = {key: member for key, member in members.items() if key not in {'assign', 'unknown', 'sent'}}
    with session(scope['admin']) as client:
        response = client.post(f"/users/admin/organizations/{scope['org']}/assessment-assignments",
                               json=payload(scope, user_ids=list(scoped_members.values()), role_profile_version_id=scope['role']))
        assert response.status_code == 200, response.text
        assignments = {item['user_id']: item['assignment_id'] for item in response.json()['items']}
    reports = {}
    cases = {}
    for key, member_id in scoped_members.items():
        profile_id = confirm_participant_profile({**scope, 'member': member_id})
        assignment_id = assignments[member_id]
        with get_connection() as c:
            if key == 'running':
                operation = 'cabinet-' + uuid4().hex
                request = {'kind': 'assessment', 'organization_id': scope['org'], 'assignment_ref': scope['ref'],
                           'assignment_id': assignment_id, 'personalized_profile_id': profile_id,
                           'questionnaire_revision_id': c.execute(
                               'SELECT questionnaire_revision_id FROM organization_assessment_source_bindings WHERE assignment_id=%s',
                               (assignment_id,)).fetchone()['questionnaire_revision_id']}
                c.execute("""INSERT INTO product_cycle_preparation_operations
                    (operation_id,user_id,request_json,request_checksum,status)
                    VALUES(%s,%s,%s,%s,%s)""",
                    (operation, member_id, Jsonb(request), checksum(request), key))
                c.execute("""INSERT INTO preparation_observations
                    (source,operation_id,attempt_token,kind,stage,status,heartbeat_at)
                    VALUES('cycle',%s,'cabinet-fixture','assessment','checking',%s,NOW())""",
                    (operation, key))
                cases[key] = reference('cycle', operation)
            else:
                cycle_id = uuid4()
                closed = key not in {'active', 'failed'}
                cycle_status = 'paused' if key == 'failed' else 'calculated' if closed else 'active'
                cycle = c.execute("""INSERT INTO m5_cycles
                    (cycle_id,owner_user_id,organization_id,assignment_id,personalized_profile_id,
                     profile_ref_json,selected_role_ref_json,target_set_json,target_set_checksum,
                     time_budget_seconds,calendar_window_seconds,parameter_sources_json,
                     usage_scope,status,created_by,started_at,collection_closed_at)
                    VALUES(%s,%s,%s,%s,%s,'{}','{}','[]','synthetic',600,3600,'{}',
                    'assessment',%s,%s,NOW(),CASE WHEN %s THEN NOW() END) RETURNING id""",
                    (cycle_id, member_id, scope['org'], assignment_id, profile_id,
                     cycle_status, member_id, closed)).fetchone()['id']
                if closed:
                    reports[key] = seed_cabinet_report(c, member_id, cycle, cycle_id, key)
                elif key == 'failed':
                    cases[key] = seed_next_failure(c, member_id, cycle, cycle_id)
            c.commit()
    return {'members': members, 'invitations': invitations, 'cases': cases, 'reports': reports,
            'ref': scope['ref'], 'role': scope['second_role'], 'other_org': scope['foreign']}


def seed_next_failure(c, member_id, cycle, cycle_id):
    from Api.m10_product_flow import next_preparation_scope
    from Api.m5_case_runtime import checksum
    from Api.preparation_observation import reference
    from psycopg.types.json import Jsonb

    plan = uuid4()
    rules = {'algorithm_version': 'synthetic'}
    content = {'route': [{}, {}]}
    c.execute("""INSERT INTO m7_cycle_plans
        (id,cycle_db_id,profile_ref_json,full_target_set_json,planned_target_set_json,
         observation_requirements_json,rules_json,rules_checksum,status,created_by)
        VALUES(%s,%s,'{}','[]','[]','[]',%s,%s,'READY',%s)""",
        (plan, cycle, Jsonb(rules), checksum(rules), member_id))
    c.execute("""INSERT INTO m7_plan_revisions
        (id,plan_id,cycle_db_id,revision_no,content_json,content_checksum,reason)
        VALUES(%s,%s,%s,1,%s,%s,'synthetic')""", (uuid4(), plan, cycle, Jsonb(content), checksum(content)))
    operation = 'cabinet-next-' + uuid4().hex
    request = {'kind': 'next', 'cycle_id': str(cycle_id), 'next_preparation_scope': next_preparation_scope(
        c, cycle_id=str(cycle_id), user_id=member_id, check_current=False)}
    c.execute("""INSERT INTO product_cycle_preparation_operations
        (operation_id,user_id,request_json,request_checksum,status) VALUES(%s,%s,%s,%s,'failed')""",
        (operation, member_id, Jsonb(request), checksum(request)))
    c.execute("""INSERT INTO preparation_observations
        (source,operation_id,attempt_token,kind,stage,status)
        VALUES('cycle',%s,'cabinet-fixture','next','checking','failed')""", (operation,))
    return reference('cycle', operation)


def seed_cabinet_report(c, member_id, cycle, cycle_id, status):
    # Saved synthetic result inputs. The real customer API still checks the
    # published ID, status, organization membership and exact Cycle.
    from Api.m5_case_runtime import checksum
    from psycopg.types.json import Jsonb

    c46, calculation, result, revision, report, alternate = (uuid4() for _ in range(6))
    c.execute("""INSERT INTO m7_c46_revisions
        (id,cycle_db_id,revision_no,status,composition_checksum,payload_json,payload_checksum)
        VALUES(%s,%s,1,'collection_snapshot','synthetic','{}','synthetic')""", (c46, cycle))
    c.execute("""INSERT INTO m6_cycle_calculations
        (id,cycle_db_id,revision_no,request_key,request_hash,composition_checksum,
         input_json,input_hash,result_json,result_hash,c56_json,c56_hash,created_by)
        VALUES(%s,%s,1,'cabinet','synthetic','synthetic','{}','synthetic','{}','synthetic','{}','synthetic',%s)""",
        (calculation, cycle, member_id))
    c.execute('INSERT INTO m8_results(id,cycle_db_id) VALUES(%s,%s)', (result, cycle))
    outcomes = {'ready': 'full_score', 'limited': 'partial_score', 'no_result': 'no_result'}
    payload = {'assessed_skill_profile': [{'outcome': outcomes[status]}]} if status in outcomes else {}
    c.execute("""INSERT INTO m8_result_revisions
        (id,results_id,revision_no,calculation_id,c46_revision_id,composition_checksum,payload_json,payload_checksum,reason,created_by)
        VALUES(%s,%s,1,%s,%s,'synthetic',%s,%s,'synthetic',%s)""",
        (revision, result, calculation, c46, Jsonb(payload), checksum(payload), member_id))
    content = {'contract': 'C-67', 'display': {'program_name': 'Synthetic test program'}, 'skills': [],
               'descriptive': {'status': 'ready', 'summary': ['Синтетический результат для проверки кабинета.']}}
    saved_status = 'draft' if status == 'unavailable' else status
    for rn, report_id in [(1, report), (2, alternate)]:
        c.execute("""INSERT INTO m8_reports
            (id,result_revision_id,revision_no,audience,template_version,c67_json,c67_checksum,status,request_key,request_hash,created_by)
            VALUES(%s,%s,%s,'assessee','synthetic',%s,%s,%s,%s,'synthetic',%s)""",
            (report_id, revision, rn, Jsonb(content), checksum(content), saved_status, f'cabinet-{rn}', member_id))
    if status != 'unavailable':
        c.execute('INSERT INTO m8_published_reports(cycle_db_id,report_id) VALUES(%s,%s)', (cycle, report))
    return {'report_id': str(report), 'cycle_id': str(cycle_id)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'cabinet', 'readback'])
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--internal', action='store_true')
    args = parser.parse_args()
    state = json.loads(args.state.read_text())
    with owned(state):
        pass
    if not args.internal:
        subprocess.run([sys.executable, __file__, args.action, '--state', str(args.state), '--internal'],
                       env=environment(state), cwd=ROOT, check=True, timeout=60)
        return
    if os.getenv('AGENT4K_ISOLATED_STAND') != '1':
        raise RuntimeError('ISOLATED_STAND_REQUIRED')
    from tests.path_admin_contract_checks import create_scope, session, ready, assignment_counts
    from Api.database import get_connection, close_connection_pool
    from Api.web_session_service import web_session_service
    from Api.routes import SESSION_COOKIE_NAME
    try:
        if args.action in {'prepare', 'cabinet'}:
            scope = create_scope(include_second_role=args.action == 'cabinet')
            with session(scope['admin']) as client:
                ready(client, scope)
            with get_connection() as c:
                emails = {str(row['id']): row['email'] for row in c.execute(
                    'SELECT id,email FROM users WHERE id=ANY(%s)', ([scope['member'], scope['second']],)).fetchall()}
            cabinet = seed_cabinet(scope) if args.action == 'cabinet' else {}
            state['path_admin'] = scope
            args.state.write_text(json.dumps(state, default=str))
            # Short-lived synthetic session goes via private child stdout only;
            # caller never writes it into evidence or browser trace.
            print(json.dumps({'organization_id': scope['org'], 'member_emails': emails,
                'cookie_name': SESSION_COOKIE_NAME,
                'super_session': web_session_service.create_session(scope['super']),
                'program_id': scope['program'],
                'session': web_session_service.create_session(scope['admin']),
                **({'foreign_session': web_session_service.create_session(scope['foreign_admin']), **cabinet}
                   if args.action == 'cabinet' else {})}))
        else:
            print(json.dumps(assignment_counts(state['path_admin'])))
    finally:
        close_connection_pool()


if __name__ == '__main__':
    main()
