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
parser.add_argument('action', choices=['create', 'serve'])
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--port', type=int, default=19341)
args = parser.parse_args()
path = args.state.resolve()
if args.action == 'create':
    raise SystemExit(subprocess.call([sys.executable, str(ROOT / 'scripts/p3-a-preview.py'), 'create',
        '--state', str(path), '--port', str(args.port), '--return-profile', 'r1'], cwd=ROOT))
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
    'source_head_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'startup_fingerprints': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                             for name in files if (ROOT / name).is_file()}}
app = preview.create_app(path)
@app.get('/exec03/identity')
def read_identity():
    return identity
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=state['port'], access_log=False)
