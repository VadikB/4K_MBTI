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


def seed_appeals_reentry(scope):
    from Api.auth_service import _hash_password, auth_service
    from Api.database import get_connection
    from tests.path_admin_contract_checks import payload, session

    with session(scope['admin']) as client:
        assigned = client.post(f"/users/admin/organizations/{scope['org']}/assessment-assignments",
                               json=payload(scope, role_profile_version_id=scope['role']))
        assert assigned.status_code == 200, assigned.text
    auth_service.ensure_schema()
    accounts = {}
    with get_connection() as c:
        for role, name in [('admin', 'Синтетический автор ответа'),
                           ('member', 'Синтетический участник обращений')]:
            user_id = scope[role]
            password = 'SyntheticAppeal!2-' + uuid4().hex
            salt, digest = _hash_password(password)
            email = c.execute('UPDATE users SET full_name=%s WHERE id=%s RETURNING email',
                              (name, user_id)).fetchone()['email']
            c.execute("""INSERT INTO auth_password_credentials
                (user_id,email,password_hash,password_salt) VALUES(%s,%s,%s,%s)""",
                (user_id, email, digest, salt))
            accounts[role] = {'id': user_id, 'email': email, 'name': name, 'password': password}
        c.commit()
    return {'organization_id': scope['org'], 'assessment_name': scope['config']['name'],
            'assignment_id': assigned.json()['items'][0]['assignment_id'], **accounts}


def seed_cabinet(scope, *, visual_states=False):
    from Api.database import get_connection
    from Api.invitation_outcomes import encode_reason
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
        'without_score': 'Наблюдения без балла',
        'unavailable': 'Публикация недоступна',
        'old_edition': 'Отчёт прежней версии программы',
        'legacy_report': 'Исторический отчёт без привязки',
        'old_batch': 'Участник прежней рассылки',
        'unverified_invitation': 'Приглашение без подтверждённой привязки',
        'profile_ready': 'Участник с закреплённым профилем',
        'profile_pending': 'Участник с общим профилем',
    }
    if visual_states:
        names.update(stale='Устаревшее состояние подготовки', first_failed='Сбой до старта',
                     unknown_failure='Сбой без сведений об этапе', processing_failed='Сбой обработки результата')
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
        current, previous, peer_org = seed_cabinet_programs(c, scope)
        emails = {row['id']: row['email'] for row in c.execute(
            'SELECT id,email FROM users WHERE id=ANY(%s)', (list(members.values()),)).fetchall()}
        general_profile = c.execute("""INSERT INTO user_role_profiles(user_id,normalized_duties)
            VALUES(%s,'Синтетические обязанности') RETURNING id""", (members['profile_pending'],)).fetchone()['id']
        general_role = c.execute("""INSERT INTO roles(code,name)
            VALUES('cabinet-profile-fixture','Синтетическая роль') RETURNING id""").fetchone()['id']
        c.execute("""UPDATE users SET active_profile_id=%s, company_industry='Синтетический контекст',
            role_id=%s WHERE id=%s""", (general_profile, general_role, members['profile_pending']))
        c.commit()
    scoped_members = {key: member for key, member in members.items()
                      if key not in {'assign', 'unknown', 'sent', 'old_batch', 'unverified_invitation'}}
    with session(scope['admin']) as client:
        response = client.post(f"/users/admin/organizations/{scope['org']}/assessment-assignments",
                               json=payload(scope, user_ids=list(scoped_members.values()), role_profile_version_id=scope['role']))
        assert response.status_code == 200, response.text
        assignments = {item['user_id']: item['assignment_id'] for item in response.json()['items']}
    reports = {}
    cases = {}
    profiles = {}
    for key, member_id in scoped_members.items():
        assignment_id = assignments[member_id]
        if key == 'profile_pending':
            profiles[key] = {'assignment_id': assignment_id, 'profile_id': None}
            continue
        profile_id = confirm_participant_profile({**scope, 'member': member_id})
        with get_connection() as c:
            if key in {'running', 'stale', 'first_failed', 'unknown_failure'}:
                status = 'running' if key in {'running', 'stale'} else 'failed'
                operation = 'cabinet-' + uuid4().hex
                request = {'kind': 'assessment', 'organization_id': scope['org'], 'assignment_ref': scope['ref'],
                           'assignment_id': assignment_id, 'personalized_profile_id': profile_id,
                           'questionnaire_revision_id': c.execute(
                               'SELECT questionnaire_revision_id FROM organization_assessment_source_bindings WHERE assignment_id=%s',
                               (assignment_id,)).fetchone()['questionnaire_revision_id']}
                c.execute("""INSERT INTO product_cycle_preparation_operations
                    (operation_id,user_id,request_json,request_checksum,status)
                    VALUES(%s,%s,%s,%s,%s)""",
                    (operation, member_id, Jsonb(request), checksum(request), status))
                if key != 'unknown_failure':
                    c.execute("""INSERT INTO preparation_observations
                        (source,operation_id,attempt_token,kind,stage,status,heartbeat_at)
                        VALUES('cycle',%s,'cabinet-fixture','assessment','checking',%s,
                               NOW()-CASE WHEN %s THEN INTERVAL '3 minutes' ELSE INTERVAL '0 seconds' END)""",
                        (operation, status, key == 'stale'))
                cases[key] = reference('cycle', operation)
                if key == 'first_failed':
                    _, cycle = seed_cabinet_cycle(c, scope, member_id, assignment_id, profile_id, 'prepared')
                    seed_preparation_plan(c, member_id, cycle, planned=8)
            else:
                cycle_status = {'failed': 'paused', 'active': 'active', 'profile_ready': 'prepared',
                                'processing_failed': 'calculation_pending'}.get(key, 'calculated')
                cycle_id, cycle = seed_cabinet_cycle(c, scope, member_id,
                    None if key == 'old_edition' else assignment_id, profile_id, cycle_status)
                if key == 'processing_failed':
                    c.execute("""INSERT INTO m10_pipeline_runs(cycle_db_id,status,stage,error_code)
                        VALUES(%s,'failed','report','SYNTHETIC_PROCESSING_FAILURE')""", (cycle,))
                elif cycle_status == 'calculated':
                    status = 'ready' if key in {'old_edition', 'legacy_report'} else key
                    reports[key] = seed_cabinet_report(
                        c, member_id, cycle, cycle_id, status, newer_unpublished=key == 'ready')
                    program = {'old_edition': previous, 'legacy_report': None}.get(key, current)
                    seed_cabinet_plan(c, member_id, cycle, program)
                elif key == 'failed':
                    cases[key] = seed_next_failure(c, member_id, cycle, cycle_id, profile_id,
                        planned=8 if visual_states else 2, completed=2 if visual_states else 0)
                elif key == 'profile_ready':
                    profiles[key] = {'assignment_id': assignment_id, 'profile_id': profile_id}
            c.commit()
    with get_connection() as c:
        batch = 'cabinet-batch-' + uuid4().hex
        recipients = [emails[members[key]] for key in ('unknown', 'old_batch')]
        invitation_fixtures = [
            ('sent', 'accepted', scope['ref'], 'cabinet-' + uuid4().hex),
            ('unknown', 'sending', previous['assignment_ref'], batch),
            ('old_batch', 'accepted', previous['assignment_ref'], batch),
            ('unverified_invitation', 'sending', '', 'cabinet-legacy-' + uuid4().hex),
        ]
        if visual_states:
            # Keep the confirmed profile and add an unresolved receipt for the other assessment.
            invitation_fixtures.append(('first_failed', 'sending', previous['assignment_ref'], 'cabinet-prior-' + uuid4().hex))
        for key, delivery, ref, operation in invitation_fixtures:
            email = emails[members[key]]
            invitation = c.execute("""INSERT INTO organization_invitations
                (organization_id,token_hash,expires_at,created_by_user_id,recipient_email,purpose,
                 delivery_status,request_id,assignment_ref,delivery_error)
                VALUES(%s,%s,NOW()+INTERVAL '2 days',%s,%s,'personal_registration',%s,%s,%s,%s) RETURNING id""",
                (scope['org'], checksum([operation, email]), scope['admin'], email, delivery, operation, ref,
                 encode_reason(delivery, delivery, recipients=recipients if operation == batch else [email]))).fetchone()
            invitations[key] = {'id': invitation['id'], 'operation': operation, 'email': email, 'ref': ref}
        c.execute("""UPDATE organization_assessment_program_connections SET is_current=FALSE,superseded_at=NOW()
            WHERE organization_id=%s AND is_current=TRUE""", (scope['org'],))
        c.execute("""UPDATE organization_assessment_program_connections SET is_current=TRUE,superseded_at=NULL
            WHERE id=%s""", (current['connection_id'],))
        catalog_case_count = c.execute("""SELECT COUNT(*) AS n FROM m5_catalog_case_versions cases
            JOIN assessment_program_definitions program ON program.catalog_version_id=cases.catalog_db_id
            WHERE program.id=%s""", (current['program_definition_id'],)).fetchone()['n']
        c.commit()
    return {'members': members, 'assignments': {key: assignments[member] for key, member in scoped_members.items()},
            'invitations': invitations, 'cases': cases, 'reports': reports,
            'profiles': profiles, 'ref': scope['ref'], 'role': scope['second_role'], 'catalog_case_count': catalog_case_count,
            'program_id': current['program_definition_id'], 'ordinary_program_id': scope['program'],
            'other_org': scope['foreign'], 'peer_org': peer_org, 'peer_ref': previous['assignment_ref'],
            'peer_program_id': previous['program_definition_id']}


def seed_cabinet_cycle(c, scope, member_id, assignment_id, profile_id, status):
    cycle_id = uuid4()
    cycle = c.execute("""INSERT INTO m5_cycles
        (cycle_id,owner_user_id,organization_id,assignment_id,personalized_profile_id,
         profile_ref_json,selected_role_ref_json,target_set_json,target_set_checksum,
         time_budget_seconds,calendar_window_seconds,parameter_sources_json,
         usage_scope,status,created_by,started_at,collection_closed_at)
        VALUES(%s,%s,%s,%s,%s,'{}','{}','[]','synthetic',600,3600,'{}',
        'assessment',%s,%s,CASE WHEN %s THEN NULL ELSE NOW() END,
        CASE WHEN %s THEN NOW() END) RETURNING id""",
        (cycle_id, member_id, scope['org'], assignment_id, profile_id, status, member_id,
         status == 'prepared', status in {'calculation_pending', 'calculated'})).fetchone()['id']
    return cycle_id, cycle


def seed_cabinet_programs(c, scope):
    from Api.assessment_programs import current_connection, definition_checksum
    from Api.m5_case_runtime import checksum
    from Api.pilot_plan_admission import CONTRACT
    from Api.schema_bootstrap import fingerprint
    from psycopg import sql
    from psycopg.types.json import Jsonb

    ordinary = current_connection(c, organization_id=scope['org'])
    assert 'pilot_plan_admission' not in ordinary['source_refs_json']
    roles = [role['version_id'] for role in ordinary['roles']]

    def pilot_version(version, ref):
        # The cabinet reads saved reports and a program reference. It does not run pilot admission.
        pilot = {'contract': CONTRACT, 'artifact_id': 'synthetic-cabinet', 'artifact_version': version}
        sources = {**ordinary['source_refs_json'], 'pilot_plan_admission': {
            **pilot, 'snapshot_checksum': checksum(pilot)}}
        digest = definition_checksum(code=ordinary['program_code'], version=version, name=ordinary['program_name'],
            assignment_ref=ref, mode=ordinary['mode'], configuration_id=ordinary['assessment_configuration_id'],
            catalog_version_id=ordinary['catalog_version_id'], role_version_ids=roles, source_refs=sources)
        program_id = c.execute("""INSERT INTO assessment_program_definitions
            (code,version,name,assignment_ref,mode,status,assessment_configuration_id,catalog_version_id,
             source_refs_json,definition_checksum,published_by_user_id,published_at)
            SELECT code,%s,name,%s,mode,'draft',assessment_configuration_id,catalog_version_id,
                   %s,%s,published_by_user_id,NOW()
            FROM assessment_program_definitions WHERE id=%s RETURNING id""",
            (version, ref, Jsonb(sources), digest, scope['program'])).fetchone()['id']
        c.execute("""INSERT INTO assessment_program_allowed_roles
            (program_definition_id,role_profile_version_id,display_order)
            SELECT %s,role_profile_version_id,display_order FROM assessment_program_allowed_roles
            WHERE program_definition_id=%s""", (program_id, scope['program']))
        c.execute("UPDATE assessment_program_definitions SET status='published' WHERE id=%s", (program_id,))
        connection_id = c.execute("""INSERT INTO organization_assessment_program_connections
            (organization_id,program_definition_id,connected_by_user_id,operation_id,request_fingerprint,is_current,superseded_at)
            VALUES(%s,%s,%s,%s,'synthetic',FALSE,NOW()) RETURNING id""",
            (scope['org'], program_id, scope['super'], 'cabinet-' + version)).fetchone()['id']
        return {**ordinary, 'connection_id': connection_id, 'program_definition_id': program_id,
                'program_version': version, 'assignment_ref': ref, 'definition_checksum': digest}

    previous = pilot_version('test.0', 'previous-' + scope['ref'])
    current = pilot_version('test.2', scope['ref'])
    peer_org = c.execute("""INSERT INTO organizations(code,name)
        VALUES('cabinet-peer','Вторая организация') RETURNING id""").fetchone()['id']
    # Allow the synthetic admin to exercise two organizations in the owned stand.
    c.execute('DROP INDEX uq_organization_memberships_user')
    c.execute(sql.SQL('CREATE UNIQUE INDEX uq_organization_memberships_user '
                      'ON organization_memberships(user_id) WHERE user_id <> {}').format(sql.Literal(scope['admin'])))
    c.execute('UPDATE app_bootstrap SET schema_hash=%s', (fingerprint(c),))
    c.execute("""INSERT INTO organization_memberships(organization_id,user_id,role,admission_source)
        VALUES(%s,%s,'admin','admin_add')""", (peer_org, scope['admin']))
    c.execute("""INSERT INTO organization_assessment_program_connections
        (organization_id,program_definition_id,connected_by_user_id,operation_id,request_fingerprint)
        VALUES(%s,%s,%s,'cabinet-peer','synthetic')""", (peer_org, previous['program_definition_id'], scope['super']))
    return current, previous, peer_org


def seed_cabinet_plan(c, member_id, cycle, program):
    from Api.m7_planning_repository import save_plan

    content = {'status': 'READY', 'route': []}
    if program:
        content['pilot_plan_binding'] = {
            'contract': 'm7_pilot_plan_binding/1',
            'program_ref': {'id': program['program_definition_id'], 'code': program['program_code'],
                            'version': program['program_version'], 'checksum': program['definition_checksum'],
                            'connection_id': program['connection_id']}}
    save_plan(c, cycle={'id': cycle}, profile_ref={}, full_targets=[], planned_targets=[], requirements=[],
              rules={'snapshot_checksum': 'synthetic'}, content=content, created_by=member_id,
              key=f'cabinet-report-{cycle}', request_hash='synthetic')


def seed_preparation_plan(c, member_id, cycle, *, planned):
    from Api.m5_case_runtime import checksum
    from psycopg.types.json import Jsonb

    plan, revision = uuid4(), uuid4()
    rules = {'algorithm_version': 'synthetic'}
    content = {'route': [{'position_no': number} for number in range(1, planned + 1)]}
    c.execute("""INSERT INTO m7_cycle_plans
        (id,cycle_db_id,profile_ref_json,full_target_set_json,planned_target_set_json,
         observation_requirements_json,rules_json,rules_checksum,status,created_by)
        VALUES(%s,%s,'{}','[]','[]','[]',%s,%s,'READY',%s)""",
        (plan, cycle, Jsonb(rules), checksum(rules), member_id))
    c.execute("""INSERT INTO m7_plan_revisions
        (id,plan_id,cycle_db_id,revision_no,content_json,content_checksum,reason)
        VALUES(%s,%s,%s,1,%s,%s,'synthetic')""", (revision, plan, cycle, Jsonb(content), checksum(content)))
    return revision


def seed_next_failure(c, member_id, cycle, cycle_id, profile_id, *, planned, completed):
    from Api.m10_product_flow import next_preparation_scope
    from Api.m5_case_runtime import checksum
    from Api.preparation_observation import reference
    from psycopg.types.json import Jsonb

    revision = seed_preparation_plan(c, member_id, cycle, planned=planned)
    if completed:
        seed_completed_positions(c, member_id, cycle, profile_id, revision, completed)
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


def seed_completed_positions(c, member_id, cycle, profile_id, revision, completed):
    session_id = c.execute("""INSERT INTO m5_cycle_sessions(session_id,cycle_db_id,ordinal,status,created_by)
        VALUES(%s,%s,1,'paused',%s) RETURNING id""", (uuid4(), cycle, member_id)).fetchone()['id']
    case_version = c.execute('SELECT id FROM m5_case_versions ORDER BY id LIMIT 1').fetchone()['id']
    for position in range(1, completed + 1):
        situation = uuid4()
        situation_id = c.execute("""INSERT INTO m5_assessment_situations
            (assessment_situation_id,case_version_id,personalized_profile_id,cycle_db_id,session_db_id,
             status,snapshot_json,execution_payload_json,snapshot_checksum,closed_at)
            VALUES(%s,%s,%s,%s,%s,'closed','{}','{}',%s,NOW()) RETURNING id""",
            (situation, case_version, profile_id, cycle, session_id, str(situation))).fetchone()['id']
        c.execute("""INSERT INTO m7_route_positions
            (id,cycle_db_id,plan_revision_id,position_no,case_id,case_version,expected_targets_json,state,current_as_db_id)
            VALUES(%s,%s,%s,%s,'synthetic','1','[]','completed',%s)""",
            (uuid4(), cycle, revision, position, situation_id))


def seed_cabinet_report(c, member_id, cycle, cycle_id, status, *, newer_unpublished=False):
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
    outcomes = {'ready': 'full_score', 'limited': 'partial_score',
                'without_score': 'result_without_score', 'no_result': 'no_result'}
    payload = {'assessed_skill_profile': [{'outcome': outcomes[status]}]} if status in outcomes else {}
    c.execute("""INSERT INTO m8_result_revisions
        (id,results_id,revision_no,calculation_id,c46_revision_id,composition_checksum,payload_json,payload_checksum,reason,created_by)
        VALUES(%s,%s,1,%s,%s,'synthetic',%s,%s,'synthetic',%s)""",
        (revision, result, calculation, c46, Jsonb(payload), checksum(payload), member_id))
    content = {'contract': 'C-67', 'display': {'program_name': 'Имя программы в отчёте'}, 'skills': [],
               'descriptive': {'status': 'ready', 'summary': ['Синтетический результат для проверки кабинета.']}}
    saved_status = {'unavailable': 'draft', 'without_score': 'limited'}.get(status, status)
    for rn, report_id in [(1, report), (2, alternate)]:
        c.execute("""INSERT INTO m8_reports
            (id,result_revision_id,revision_no,audience,template_version,c67_json,c67_checksum,status,request_key,request_hash,created_by)
            VALUES(%s,%s,%s,'assessee','synthetic',%s,%s,%s,%s,'synthetic',%s)""",
            (report_id, revision, rn, Jsonb(content), checksum(content), saved_status, f'cabinet-{rn}', member_id))
    if status != 'unavailable':
        c.execute('INSERT INTO m8_published_reports(cycle_db_id,report_id) VALUES(%s,%s)', (cycle, report))
    if newer_unpublished:
        new_calculation, new_revision = uuid4(), uuid4()
        c.execute("""INSERT INTO m6_cycle_calculations
            (id,cycle_db_id,revision_no,request_key,request_hash,composition_checksum,
             input_json,input_hash,result_json,result_hash,c56_json,c56_hash,created_by)
            VALUES(%s,%s,2,'cabinet-new','synthetic','synthetic','{}','synthetic','{}','synthetic','{}','synthetic',%s)""",
            (new_calculation, cycle, member_id))
        new_payload = {'assessed_skill_profile': [{'outcome': 'result_without_score'}]}
        c.execute("""INSERT INTO m8_result_revisions
            (id,results_id,revision_no,calculation_id,c46_revision_id,composition_checksum,
             payload_json,payload_checksum,reason,created_by)
            VALUES(%s,%s,2,%s,%s,'synthetic',%s,%s,'synthetic',%s)""",
            (new_revision, result, new_calculation, c46, Jsonb(new_payload), checksum(new_payload), member_id))
    return {'report_id': str(report), 'cycle_id': str(cycle_id), 'results_revision_id': str(revision)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'cabinet', 'visual-states', 'readback', 'appeals-reentry',
                                           'cabinet-state', 'cabinet-race-start'])
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
    from tests.path_admin_contract_checks import create_scope, session, ready, assignment_counts, snapshot
    from Api.database import get_connection, close_connection_pool
    from Api.web_session_service import web_session_service
    from Api.routes import SESSION_COOKIE_NAME
    try:
        if args.action in {'prepare', 'cabinet', 'visual-states', 'appeals-reentry'}:
            with_cabinet = args.action in {'cabinet', 'visual-states'}
            scope = create_scope(include_second_role=with_cabinet)
            with session(scope['admin']) as client:
                ready(client, scope)
            if args.action == 'appeals-reentry':
                print(json.dumps(seed_appeals_reentry(scope)))
                return
            with get_connection() as c:
                emails = {str(row['id']): row['email'] for row in c.execute(
                    'SELECT id,email FROM users WHERE id=ANY(%s)', ([scope['member'], scope['second']],)).fetchall()}
            cabinet = seed_cabinet(scope, visual_states=args.action == 'visual-states') if with_cabinet else {}
            state['path_admin'] = scope
            if args.action == 'visual-states':
                state['cabinet_assignments'] = cabinet['assignments']
            args.state.write_text(json.dumps(state, default=str))
            # Short-lived synthetic session goes via private child stdout only;
            # caller never writes it into evidence or browser trace.
            print(json.dumps({'organization_id': scope['org'], 'member_emails': emails,
                'cookie_name': SESSION_COOKIE_NAME,
                'super_session': web_session_service.create_session(scope['super']),
                'program_id': scope['program'],
                'session': web_session_service.create_session(scope['admin']),
                **({'foreign_session': web_session_service.create_session(scope['foreign_admin']), **cabinet}
                   if with_cabinet else {})}))
        elif args.action == 'cabinet-race-start':
            with get_connection() as c:
                changed = c.execute("""UPDATE m5_cycles SET status='active', started_at=NOW()
                    WHERE assignment_id=%s AND status='prepared' AND started_at IS NULL""",
                    (state['cabinet_assignments']['first_failed'],))
                assert changed.rowcount == 1
                c.commit()
        elif args.action == 'cabinet-state':
            saved = snapshot()
            state_tables = {name: saved[name] for name in ('assessment_preparation_jobs',
                'product_cycle_preparation_operations', 'm5_cycles', 'organization_assessment_assignments')}
            with get_connection() as c:
                cancellations = c.execute("""SELECT assignment_id, COUNT(*) AS count
                    FROM organization_assessment_assignment_audit WHERE organization_id=%s
                    GROUP BY assignment_id ORDER BY assignment_id""", (state['path_admin']['org'],)).fetchall()
            print(json.dumps({'projection_sources': state_tables, 'cancellations': cancellations}))
        else:
            print(json.dumps(assignment_counts(state['path_admin'])))
    finally:
        close_connection_pool()


if __name__ == '__main__':
    main()
