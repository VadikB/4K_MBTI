"""Read-only observation, not an approval or a change to READY/LIMITED policy."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.environ['DB_POOL_MIN_SIZE'] = '0'
from Api.routes import _project_admin_assessment_stage

node = r"""
import {preparationView} from './web/js/onboarding-flow.js';
import {verifyPreparation} from './tests/browser/fixtures/preparation-receipt.mjs';
import fs from 'node:fs';
const views = Object.fromEntries(['READY','LIMITED','NO_ROUTE'].map(status => [status,
  preparationView({late_readiness:{status:'ready_to_prepare'}, preparation_operation:{status:'completed'},
    prepared_plan:{cycle_id:'synthetic-observation',plan:{status,
      route:status==='NO_ROUTE'?[]:[{}],time_budget_seconds:3600,calendar_window_seconds:259200}}})]));
const receipt = JSON.parse(fs.readFileSync('docs/evc/evidence/path-start-2dc98c6-run/run/source-to-runtime-receipt.json'));
let historical_validator;
try {verifyPreparation(receipt); historical_validator='UNEXPECTED_SUCCESS';}
catch(error){historical_validator=error.message.split('\n')[0];}
process.stdout.write(JSON.stringify({views,historical_validator}));
"""
observed = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', node], cwd=ROOT, text=True))
rows = []
for status in ('READY', 'LIMITED', 'NO_ROUTE'):
    admin = _project_admin_assessment_stage({
        'assignment_id': 1, 'assignment_status': 'active', 'cycle_status': 'prepared', 'plan_status': status,
        'planned_positions': 0 if status == 'NO_ROUTE' else 1, 'admitted_situation': True,
        'preparation_status': 'completed',
    })
    rows.append({'plan_status': status, 'admin_code': admin['code'], 'admin_action': admin['action'],
                 'participant_view': observed['views'][status]})
assert rows[1]['admin_code'] == 'start_blocked' and rows[1]['participant_view'] == 'ready'
assert observed['historical_validator'] == 'PLAN_NOT_READY'
paths = ['Api/m7_cycle_planner.py', 'Api/m10_product_flow.py', 'Api/routes.py',
         'Api/acquaintance.py', 'web/js/onboarding-flow.js', 'web/js/screens/onboarding.js',
         'tests/browser/fixtures/preparation-receipt.mjs',
         'docs/architecture/m7-cycle-planning-contract.md',
         'docs/methodology/source-sets/2026-10-01/derived/M7-v1.3.md']
print(json.dumps({'scope': 'read_only_synthetic_projection_observation_not_admission',
    'runtime_base': '2dc98c6b5b2637c6c505a90686e82f5e4274e763', 'matrix': rows,
    'historical_validator': observed['historical_validator'], 'http_start_calls': 0, 'llm_calls': 0,
    'actual_historical_start_refusal': 'NOT_PROVEN_REQUEST_NOT_MADE',
    'methodological_approval_for_limited_pilot': 'NOT_FOUND',
    'files': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}},
    ensure_ascii=False, indent=2))
