"""Owned localhost harness only: controlled mail sink and a paused real preparation worker."""
import os
import json
import threading
from pathlib import Path

if (os.getenv('AGENT4K_ISOLATED_STAND') != '1' or os.getenv('AGENT4K_PATH29_TEST_APP') != '1'):
    raise RuntimeError('PATH29_HARNESS_REQUIRES_OWNED_ISOLATED_STAND')

from scripts.test_stand import owned
stand_state = json.loads(Path(os.environ['STAND_STATE']).read_text())
with owned(stand_state):
    pass

if os.getenv('AGENT4K_COMPONENT_PLAN_FIXTURE'):
    from tests.browser_component_app import install
    install(stand_state)

if stand_state.get('path29_controlled_provider') is True:
    if (stand_state.get('path29_full_path') is not True
            or stand_state.get('path29_program_source') != 'published-pilot'
            or stand_state.get('provider_mode') != 'disabled'
            or stand_state.get('gateway') != 1
            or stand_state.get('component_plan_fixture')):
        raise RuntimeError('CONTROLLED_PROVIDER_REQUIRES_PUBLISHED_OWNED_PATH')
    from Api.llm import deepseek_gateway
    from tests.controlled_functional_provider import ControlledFunctionalProvider
    deepseek_gateway.DeepSeekGateway = ControlledFunctionalProvider
    from Api import m10_test_gateway
    class ControlledPathAssessmentGateway(m10_test_gateway.BrowserAcceptanceGateway):
        def chat(self, messages, **kwargs):
            value = json.loads(messages[1]['content'])
            content = super().chat(messages, **kwargs)
            if value.get('mode') != 'interim' or 'evidence_analysis' not in value:
                return content
            result = json.loads(content)
            for target in result['targets']:
                target.update(status='INTERIM', outcome=None, descriptor_basis=None)
            return json.dumps(result, ensure_ascii=False)
    m10_test_gateway.BrowserAcceptanceGateway = ControlledPathAssessmentGateway
    print('SYNTHETIC_FUNCTIONAL_PROVIDER: NO_EXTERNAL_LLM NO_NEW_HUMAN_ADMISSION', flush=True)

from main import app
from Api import routes, auth_service as auth_module
from Api.product_cycle_preparation_queue import product_cycle_preparation_queue
from fastapi import HTTPException

auth_module.settings.email_provider = 'postmark'
auth_module.settings.app_base_url = 'https://test.example.com'
auth_module.settings.app_origin_mode = 'public'
auth_module.settings.auth_invitation_token_secret = 'synthetic-path29-test-harness-not-a-real-credential'
mailbox = []


def deliver(**payload):
    if not payload['email'].endswith('@example.test'):
        raise RuntimeError('SYNTHETIC_RECIPIENT_REQUIRED')
    mailbox.append({key: payload[key] for key in ('email', 'action_url', 'purpose')})


routes.send_auth_action_email = deliver
auth_module.send_auth_action_email = deliver
def deliver_magic(*, email, login_url, expires_at):
    deliver(email=email, action_url=login_url, expires_at=expires_at, purpose='magic_link')
auth_module.send_magic_link_email = deliver_magic
preparation_gate = threading.Event()
next_preparation_gate = threading.Event()
original_process = product_cycle_preparation_queue._process_current_attempt


def paused_process(job):
    if not preparation_gate.wait(timeout=60):
        raise RuntimeError('CONTROLLED_PREPARATION_GATE_TIMEOUT')
    if (stand_state.get('path29_hold_next') is True
            and job.get('request_json', {}).get('kind') == 'next'
            and not next_preparation_gate.wait(timeout=90)):
        raise RuntimeError('CONTROLLED_NEXT_GATE_TIMEOUT')
    original_process(job)


product_cycle_preparation_queue._process_current_attempt = paused_process


@app.post('/__pytest__/drain-controlled-orchestration')
def drain_controlled_orchestration():
    if stand_state.get('path29_controlled_provider') is not True:
        raise HTTPException(404, 'CONTROLLED_PROVIDER_NOT_ACTIVE')
    from Api import m10_orchestration
    from Api.m10_test_gateway import BrowserAcceptanceGateway
    gateway = BrowserAcceptanceGateway()
    steps = 0
    while steps < 50 and (m10_orchestration.advance_once(gateway=gateway)
                          or m10_orchestration._run_browser_test_gateway_once()):
        steps += 1
    if steps >= 50:
        raise HTTPException(500, 'CONTROLLED_ORCHESTRATION_STEP_LIMIT')
    return {'steps': steps}


@app.post('/__pytest__/terminalize-controlled-path/{cycle_id}')
def terminalize_controlled_path(cycle_id: str):
    """Close the technical fixture after the asserted first explicit Next."""
    if stand_state.get('path29_controlled_provider') is not True:
        raise HTTPException(404, 'CONTROLLED_PROVIDER_NOT_ACTIVE')
    from Api.database import get_connection
    from Api.m7_completion import complete
    from Api import m10_orchestration
    from Api.m10_test_gateway import BrowserAcceptanceGateway
    from tests.assessment_execution_export import execution_export as readback
    with get_connection() as connection:
        row = connection.execute("""SELECT c.owner_user_id,c.status FROM m5_cycles c
            JOIN users u ON u.id=c.owner_user_id
            WHERE c.cycle_id=%s AND u.email='path29-new@example.test'""", (cycle_id,)).fetchone()
        if not row or row['status'] not in ('active', 'paused'):
            raise HTTPException(409, 'OWNED_ACTIVE_FIXTURE_REQUIRED')
        count = connection.execute("""SELECT count(*) AS n FROM m5_assessment_situations s
            JOIN m5_cycles c ON c.id=s.cycle_db_id WHERE c.cycle_id=%s""", (cycle_id,)).fetchone()['n']
        if count < 2:
            raise HTTPException(409, 'EXPLICIT_NEXT_REQUIRED_BEFORE_FIXTURE_CLEANUP')
        closed = complete(connection, cycle_id=cycle_id,
            key='controlled-first-next-fixture-terminalize', action='complete',
            reason='controlled_fixture_cleanup_after_explicit_next',
            initiated_by=row['owner_user_id'])
        for handoff_id in closed['final_handoff_ids']:
            m10_orchestration.enqueue_handoff(connection, handoff_id=handoff_id,
                created_by=row['owner_user_id'])
        connection.commit()
    gateway = BrowserAcceptanceGateway()
    for _ in range(50):
        if not (m10_orchestration.advance_once(gateway=gateway)
                or m10_orchestration._run_browser_test_gateway_once()):
            break
    else:
        raise HTTPException(500, 'CONTROLLED_ORCHESTRATION_STEP_LIMIT')
    exported = readback(cycle_id)
    if (exported['collection_status'] not in ('collection_closed', 'calculation_pending', 'calculated')
            or (exported['pipeline'] or {}).get('status') not in ('ready', 'failed')):
        raise HTTPException(500, 'CONTROLLED_FIXTURE_TERMINAL_EXPORT_UNAVAILABLE')
    return {'collection_status': exported['collection_status'],
            'pipeline_status': exported['pipeline']['status'],
            'situation_count': len(exported['situations'])}


@app.get('/__pytest__/mailbox')
def read_mailbox(email: str, purpose: str):
    if not email.endswith('@example.test'):
        raise HTTPException(400, 'SYNTHETIC_RECIPIENT_REQUIRED')
    items = [item for item in mailbox if item['email'] == email and item['purpose'] == purpose]
    return {'item': items[-1] if items else None}


@app.post('/__pytest__/release-preparation')
def release_preparation():
    preparation_gate.set()
    return {'released': True}


@app.post('/__pytest__/release-next-preparation')
def release_next_preparation():
    if stand_state.get('path29_hold_next') is not True:
        raise HTTPException(404, 'CONTROLLED_NEXT_GATE_NOT_ACTIVE')
    next_preparation_gate.set()
    return {'released': True}


@app.get('/__pytest__/participant-state')
def participant_state():
    from Api.database import get_connection
    with get_connection() as c:
        user = c.execute("SELECT id FROM users WHERE email='path29-new@example.test'").fetchone()
        if not user:
            return {'profiles': 0, 'cycles': 0, 'started': 0, 'operations': 0}
        uid = user['id']
        return {key: c.execute(sql, (uid,)).fetchone()['n'] for key, sql in {
            'profiles': 'SELECT COUNT(*) AS n FROM assessment_personalized_profiles WHERE user_id=%s',
            'cycles': 'SELECT COUNT(*) AS n FROM m5_cycles WHERE owner_user_id=%s',
            'started': 'SELECT COUNT(*) AS n FROM m5_cycles WHERE owner_user_id=%s AND started_at IS NOT NULL',
            'operations': 'SELECT COUNT(*) AS n FROM product_cycle_preparation_operations WHERE user_id=%s',
        }.items()}


@app.get('/__pytest__/execution-export/{cycle_id}')
def execution_export(cycle_id: str):
    from tests.assessment_execution_export import execution_export as readback
    return readback(cycle_id)


@app.get('/__pytest__/path-receipt')
def path_receipt():
    """Safe source-to-runtime trace; excludes prompts, responses and credentials."""
    from Api.database import get_connection
    from Api.m5_case_runtime import checksum
    from tests.assessment_first_case_evidence import functional_receipt, assignment_lineage, plan_receipt
    with get_connection() as c:
        state = json.loads(Path(os.environ['STAND_STATE']).read_text())
        program = c.execute("""SELECT p.id,p.code,p.version,p.assignment_ref,p.status,p.definition_checksum,
                p.assessment_configuration_id,p.catalog_version_id,p.source_refs_json
            FROM assessment_program_definitions p WHERE p.id=%s""", (state['path29']['program_id'],)).fetchone()
        configuration = c.execute("""SELECT id,code,status,methodology_version_id,
                scenario_version_id,catalog_version_id,prompt_bundle_checksum
            FROM assessment_configurations WHERE id=%s""",
            (program['assessment_configuration_id'],)).fetchone()
        catalog = c.execute("""SELECT c.id,c.catalog_id,c.catalog_version,c.status,c.usage_scope,
                c.organization_id,c.manifest_checksum,c.decision_basis,c.package_db_id,
                p.package_id,p.package_version,p.package_checksum,p.source_checksum
            FROM m5_catalogs c JOIN m5_packages p ON p.id=c.package_db_id WHERE c.id=%s""",
            (program['catalog_version_id'],)).fetchone()
        cases = c.execute("""SELECT cv.id,cv.case_id,cv.case_version,cv.status,cv.base_role,
                cv.content_checksum,member.runtime_rule_version_id
            FROM m5_catalog_case_versions member
            JOIN m5_case_versions cv ON cv.id=member.case_version_id
            WHERE member.catalog_db_id=%s ORDER BY cv.case_id""", (catalog['id'],)).fetchall()
        participant = c.execute("SELECT id FROM users WHERE email='path29-new@example.test'").fetchone()
        operation = situation = cycle = None
        sessions = []
        assessment_answers = 0
        lineage = None
        plan = None
        if participant:
            lineage = assignment_lineage(c, user_id=participant['id'], assignment_ref=program['assignment_ref'],
                configuration_id=program['assessment_configuration_id'])
            operation = c.execute("""SELECT operation_id,status,attempts,request_checksum,
                    request_json->>'personalized_profile_id' AS requested_profile_id,
                    request_json->>'profile_checksum' AS requested_profile_checksum,
                    result_json,error_code,error_message
                FROM product_cycle_preparation_operations WHERE user_id=%s
                ORDER BY id DESC LIMIT 1""", (participant['id'],)).fetchone()
            cycle = c.execute("""SELECT id,cycle_id,status,started_at,catalog_ref_json,
                    execution_manifest_checksum,personalized_profile_id,owner_user_id,organization_id,
                    assignment_id,profile_ref_json,time_budget_seconds,calendar_window_seconds,parameter_sources_json
                FROM m5_cycles WHERE owner_user_id=%s ORDER BY id DESC LIMIT 1""",
                (participant['id'],)).fetchone()
            if cycle:
                plan = plan_receipt(c, cycle_db_id=cycle['id'])
                from tests.assessment_first_case_evidence import start_readiness_receipt
                start_readiness = start_readiness_receipt(c, cycle_id=str(cycle['cycle_id']), user_id=participant['id'])
                sessions = [dict(row) for row in c.execute('''SELECT session_id,status,started_at
                    FROM m5_cycle_sessions WHERE cycle_db_id=%s ORDER BY ordinal''', (cycle['id'],)).fetchall()]
                assessment_answers = c.execute('''SELECT count(*) AS n FROM m5_dialogue_turns t
                    JOIN m5_assessment_situations s ON s.id=t.assessment_situation_db_id
                    WHERE s.cycle_db_id=%s AND t.speaker_type='assessee' ''', (cycle['id'],)).fetchone()['n']
                situation = c.execute("""SELECT assessment_situation_id,status,snapshot_checksum,
                        snapshot_json,execution_payload_json,started_at
                    FROM m5_assessment_situations WHERE cycle_db_id=%s ORDER BY id DESC LIMIT 1""",
                    (cycle['id'],)).fetchone()
        situation_value = dict(situation) if situation else {}
        persisted_functional = ((situation_value.get('execution_payload_json') or {})
                                .get('ai_operations') or {}).get('functional_personalization') or {}
        failed_generated = ((((dict(operation).get('result_json') or {}) if operation else {})
                            .get('generated')) or {})
        functional = persisted_functional or failed_generated
        snapshot = situation_value.get('snapshot_json') or {}
        payload = situation_value.get('execution_payload_json') or {}
        return {
            'program_definition': dict(program), 'assessment_configuration': dict(configuration),
            'catalog': dict(catalog), 'case_versions': [dict(item) for item in cases],
            'preparation_operation': ({key: operation[key] for key in
                ('operation_id', 'status', 'attempts', 'request_checksum', 'requested_profile_id',
                 'requested_profile_checksum', 'error_code', 'error_message')}
                if operation else None),
            'cycle': dict(cycle) if cycle else None,
            'assignment_lineage': lineage, 'plan': dict(plan) if plan else None,
            'start_readiness': start_readiness if cycle else None,
            'sessions': sessions, 'assessment_answers': assessment_answers,
            'assessment_situation': ({key: situation[key] for key in
                ('assessment_situation_id', 'status', 'snapshot_checksum', 'started_at')} if situation else None),
            'saved_checksums': {
                'snapshot_recomputed': checksum(snapshot) if snapshot else None,
                'case_ref': snapshot.get('case_ref'),
                'execution_payload_ref': snapshot.get('execution_payload_ref'),
                'execution_payload_recomputed': checksum(payload) if payload else None,
                'participant_payload': checksum(snapshot['participant_payload']) if snapshot else None,
            },
            'functional_generation': functional_receipt(functional),
        }
