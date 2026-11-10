"""Owned localhost harness only: controlled mail sink and a paused real preparation worker."""
import os
import json
import threading
from pathlib import Path

if (os.getenv('AGENT4K_ISOLATED_STAND') != '1' or os.getenv('AGENT4K_PATH29_TEST_APP') != '1'):
    raise RuntimeError('PATH29_HARNESS_REQUIRES_OWNED_ISOLATED_STAND')

from scripts.test_stand import owned
with owned(json.loads(Path(os.environ['STAND_STATE']).read_text())):
    pass

if os.getenv('AGENT4K_COMPONENT_PLAN_FIXTURE'):
    from tests.browser_component_app import install
    install(json.loads(Path(os.environ['STAND_STATE']).read_text()))

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
original_process = product_cycle_preparation_queue._process_current_attempt


def paused_process(job):
    if not preparation_gate.wait(timeout=60):
        raise RuntimeError('CONTROLLED_PREPARATION_GATE_TIMEOUT')
    original_process(job)


product_cycle_preparation_queue._process_current_attempt = paused_process


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
