"""Run from repository root; use only explicit disposable-test cluster URLs."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
from psycopg.conninfo import make_conninfo
root=Path.cwd()
env=dict(os.environ)
assert env.get('STAND_ADMIN_URL') and env.get('TEST_DATABASE_URL'), 'Explicit localhost maintenance/test URLs are required'
maintenance_test_url=env['TEST_DATABASE_URL']
state=Path(tempfile.mkdtemp(prefix='task106-integration-'))/'state.json'
def cli(action):
    subprocess.run([sys.executable,'scripts/test_stand.py',action,'--state',str(state),'--gateway','1'],env=env,check=True)
cli('create')
try:
    record=json.loads(state.read_text())
    env['TEST_DATABASE_URL']=make_conninfo(**{**record['connection'],'dbname':record['database']})
    env['H106_ARTIFACT_DIR']=str(root/'docs/evc/tasks/artifacts/task10-6')
    result=subprocess.run([sys.executable,'-m','pytest','--run-integration','-m','integration','--ignore=tests/integration/test_clean_bootstrap_db.py'],env=env)
finally:
    cli('destroy')
if result.returncode:sys.exit(result.returncode)
env['TEST_DATABASE_URL']=maintenance_test_url
sys.exit(subprocess.run([sys.executable,'-m','pytest','--run-integration','tests/integration/test_clean_bootstrap_db.py'],env=env).returncode)
