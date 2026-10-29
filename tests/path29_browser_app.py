"""Owned localhost harness only: controlled mail sink and a paused real preparation worker."""
import os
import json
import threading
from pathlib import Path

if (os.getenv('AGENT4K_ISOLATED_STAND') != '1' or os.getenv('AGENT4K_BROWSER_TEST_GATEWAY') != '1'
        or os.getenv('AGENT4K_PATH29_TEST_APP') != '1'):
    raise RuntimeError('PATH29_HARNESS_REQUIRES_OWNED_ISOLATED_STAND')

from scripts.test_stand import owned
with owned(json.loads(Path(os.environ['STAND_STATE']).read_text())):
    pass

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
