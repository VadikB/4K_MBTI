"""EXEC03 R1 preview: existing owned bootstrap plus an explicit technical AI boundary.

Production routes, auth, snapshots, guards, persistence and clocks stay real.
The deterministic gateway is scoped to this disposable disabled-provider app.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import importlib.util
spec = importlib.util.spec_from_file_location('exec03_p3_preview', ROOT / 'scripts/p3-a-preview.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)

parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['create', 'serve', '_parameters'])
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--port', type=int, default=19341)
args = parser.parse_args()
path = args.state.resolve()
if args.action == 'create':
    if path.exists():
        raise ValueError('EXEC03_STATE_ALREADY_EXISTS')
    from scripts.test_stand import check_port
    check_port(args.port)
    def cli(action):
        subprocess.run([sys.executable, str(ROOT / 'scripts/test_stand.py'), action,
            '--state', str(path), '--port', str(args.port), '--gateway', '1', '--provider', 'disabled'],
            cwd=ROOT, check=True)
    cli('create')
    state = json.loads(path.read_bytes())
    state.update(p3_a_fixture=preview.FIXTURE, p3_a_return_profile='r1', qa_orchestration=False,
        browser_scenario='acceptance-v1', component_plan_fixture='browser-component-plan-boundary/1')
    path.write_text(json.dumps(state))
    cli('bootstrap'); cli('seed')
    subprocess.run([sys.executable, __file__, '_parameters', '--state', str(path)],
        cwd=ROOT, env=preview.fixture_environment(state), check=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts/p3-a-preview.py'), '_prepare', '--state', str(path)],
        cwd=ROOT, env=preview.fixture_environment(state), check=True)
    print('EXEC03 R1 fixture prepared with versioned 7200/259200 input before Cycle creation')
    raise SystemExit(0)
if args.action == '_parameters':
    state = preview.read_state(path)
    from Api.database import get_connection
    from Api.m7_parameter_resolution import save_revision
    with get_connection() as connection:
        if connection.execute('SELECT 1 FROM m5_cycles LIMIT 1').fetchone():
            raise ValueError('EXEC03_PARAMETERS_MUST_PRECEDE_CYCLES')
        admin = connection.execute("SELECT id FROM users WHERE email='superadmin@example.test'").fetchone()['id']
        profiles = connection.execute("""SELECT DISTINCT organization_id,assessment_configuration_id
            FROM assessment_personalized_profiles WHERE status='ready'""").fetchall()
        receipts = []
        for profile in profiles:
            saved = save_revision(connection, source_scope='program', organization_id=profile['organization_id'],
                assessment_configuration_id=profile['assessment_configuration_id'],
                values={'time_budget_seconds': 7200, 'calendar_window_seconds': 259200}, created_by=admin)
            receipts.append({'revision_id': str(saved['id']), 'checksum': saved['values_checksum'],
                'values': saved['values_json']})
        connection.commit()
    state['exec03_parameter_receipts'] = receipts
    path.write_text(json.dumps(state))
    print('Owned synthetic program parameter revisions saved; no existing Cycle or snapshot changed')
    raise SystemExit(0)
state = preview.read_state(path)
if state.get('p3_a_return_profile') != 'r1':
    raise ValueError('EXEC03_R1_SNAPSHOT_REQUIRED')
env = preview.fixture_environment(state)
# Enable the existing deterministic response contract without switching product
# usage_scope to QA. The saved assessment R1 policy/budget stays unchanged.
env['AGENT4K_BROWSER_SCENARIO'] = 'acceptance-v1'
os.environ.clear()
os.environ.update(env)
from scripts.test_stand import check_port
check_port(state['port'])
files = subprocess.check_output(['git', 'ls-files', 'Api', 'web/js', 'web/dist',
    'scripts/p3-a-preview.py', 'tests/frontend/exec03_preview.py',
    'tests/frontend/exec03-send-recovery.spec.mjs'], cwd=ROOT, text=True).splitlines()
identity = {'fixture': 'exec03_r1_technical_gateway/1', 'run_id': state['run_id'],
    'provider_mode': state['provider_mode'], 'qa_orchestration': False,
    'parameter_receipts': state.get('exec03_parameter_receipts'),
    'source_head_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'startup_fingerprints': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                             for name in files if (ROOT / name).is_file()}}
app = preview.create_app(path)
@app.get('/exec03/identity')
def read_identity():
    return identity
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=state['port'], access_log=False)
