"""Preflight and entrypoint for the superadmin-to-first-case synthetic run."""
from __future__ import annotations
import argparse,hashlib,json,os,re,shutil,socket,subprocess,sys,urllib.parse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def preflight(port:int,python_path:str|None=None,*,verify_machine:bool=False)->dict:
    checks=[]
    def add(code,ready,detail):checks.append({'code':code,'status':'READY' if ready else 'BLOCKED','detail':detail})
    add('isolated_database_admin',bool(os.getenv('STAND_ADMIN_URL')),
        'STAND_ADMIN_URL is set' if os.getenv('STAND_ADMIN_URL') else 'STAND_ADMIN_URL is required')
    python=Path(python_path) if python_path else ROOT/'.venv/bin/python';add('python_environment',python.is_file(),str(python) if python.is_file() else f'{python} is required')
    playwright=ROOT/'node_modules/.bin/playwright';add('browser',playwright.is_file(),str(playwright) if playwright.is_file() else 'npm ci is required')
    keys=bool(os.getenv('DEEPSEEK_API_KEYS') or os.getenv('DEEPSEEK_API_KEY'));model=bool(os.getenv('DEEPSEEK_MODEL'))
    add('real_provider',keys and model,'provider credentials and model are set' if keys and model else 'DEEPSEEK_API_KEYS (or DEEPSEEK_API_KEY) and DEEPSEEK_MODEL are required')
    try:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);probe.bind(('127.0.0.1',port))
        add('localhost_port',True,f'127.0.0.1:{port} is available')
    except OSError as exc:add('localhost_port',False,f'127.0.0.1:{port} unavailable: {exc.__class__.__name__}')
    node=shutil.which('node');add('node',node is not None,node or 'node is required')
    if verify_machine:
        probes = [
            ('postgresql_connect_and_createdb', [str(python), '-c',
                'import os,psycopg; from scripts.test_stand import admin_params; '
                'c=psycopg.connect(**admin_params(os.getenv("STAND_ADMIN_URL"))); '
                'r=c.execute("SELECT rolcreatedb OR rolsuper FROM pg_roles WHERE rolname=current_user").fetchone(); '
                'assert r and r[0]; c.close()']),
            ('chromium_launch', ['node', '--input-type=module', '-e',
                'import {chromium} from "@playwright/test"; const b=await chromium.launch({headless:true}); await b.close();']),
        ]
        for name, command in probes:
            try:
                probe=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=30)
                add(name,probe.returncode==0,'verified' if probe.returncode==0 else 'probe failed; no credentials logged')
            except (OSError,subprocess.TimeoutExpired):
                add(name,False,'probe unavailable or timed out')
    return {'status':'READY' if all(c['status']=='READY' for c in checks) else 'BLOCKED','checks':checks}


def code_identity():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    paths = ['scripts/test_stand.py', 'scripts/assessment_first_case.py',
        'tests/path29_browser_inputs.py', 'tests/path29_browser_app.py',
        'tests/assessment_first_case_evidence.py', 'tests/browser/path29-participant.spec.mjs',
        'tests/browser/fixtures/receipt-file.mjs']
    return {'sha': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'),
        'origin_main': git('rev-parse', 'origin/main'),
        'worktree_status': git('status', '--short'),
        'files': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}}


def check_bootstrap(directory, port, python, env):
    """Repeat ownership/source lifecycle without paying for another generation."""
    from uuid import uuid4
    run_directory = directory / uuid4().hex
    run_directory.mkdir(mode=0o700)
    state_path = run_directory / 'state.json'
    def cli(action):
        subprocess.run([python, str(ROOT / 'scripts/test_stand.py'), action,
            '--state', str(state_path), '--port', str(port), '--gateway', '0', '--provider', 'real'],
            cwd=ROOT, env=env, check=True, timeout=180)
    cli('create')
    try:
        state = json.loads(state_path.read_text())
        (run_directory / 'run.json').write_text(json.dumps({
            'run_id': state['run_id'], 'database': state['database'], 'scope': 'bootstrap_repeat',
            'llm_calls': 0}, indent=2) + '\n')
        cli('bootstrap')
        subprocess.run([python, str(ROOT / 'tests/path29_browser_inputs.py'), '--state', str(state_path)],
            cwd=ROOT, env={**env, 'P4K_FULL_PATH': '1'}, check=True, timeout=180)
    finally:
        cli('destroy')
    print('PASS bootstrap_repeat; sources verified; LLM_CALLS=0; owned database removed', flush=True)


def summarize_runs(directory, exit_code):
    runs = []
    for run_path in sorted(directory.glob('*/run.json')):
        run_directory = run_path.parent
        def read(name):
            file = run_directory / (name + '.json')
            return json.loads(file.read_text()) if file.exists() else None
        run, cleanup = read('run'), read('cleanup')
        clean = bool(cleanup and cleanup.get('owner_verified') and cleanup.get('database_absent')
                     and cleanup.get('state_absent'))
        bootstrap = run.get('scope') == 'bootstrap_repeat'
        success = clean and (run_directory / ('source-provenance.json' if bootstrap else 'first-case-receipt.json')).exists()
        log = run_directory / 'server.log'
        completions = [{'duration_ms': float(match[0]), 'routing_key': match[1]}
            for match in re.findall(
                r'DeepSeek request completed duration_ms=([0-9.]+)[^\n]*routing_key=([a-f0-9-]{36}:[a-zA-Z0-9:_-]+)',
                log.read_text() if log.exists() else '')]
        runs.append({'run': run, 'cleanup': cleanup,
            'result': ('PASS_BOOTSTRAP_ONLY' if bootstrap else 'PASS') if success else 'FAIL',
            'evidence_directory': str(run_directory), 'failure': read('failure'),
            'provider_completed_requests': len(completions),
            'provider_completions': completions,
            'usage_note': 'Receipt totals count unique retained operations; JSON retries have separate completions, but earlier malformed-response usage is not retained by product trace.'})
    return {'profile': 'assessment-first-case/1.1', 'scope': 'synthetic_diagnostic',
        'exit_code': exit_code, 'runs': runs}

def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=ROOT/'.test-stand/assessment-first-case');p.add_argument('--port',type=int,default=18861);p.add_argument('--preflight-only',action='store_true');p.add_argument('--env-file',type=Path);p.add_argument('--python',default=str(ROOT/'.venv/bin/python'));p.add_argument('--db-admin-port',type=int,default=55432)
    p.add_argument('--check-bootstrap', action='store_true', help='Repeat create/bootstrap/minimal seed/destroy without LLM')
    p.add_argument('--summarize-only', action='store_true', help='Rebuild normalized summary from existing evidence; no credentials or LLM')
    a=p.parse_args()
    if a.summarize_only:
        original = json.loads((a.directory / 'runner-result.json').read_text())
        summary = summarize_runs(a.directory, original['exit_code'])
        (a.directory / 'runner-result.normalized.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return original['exit_code']
    env=os.environ.copy()
    if a.env_file:
        from dotenv import dotenv_values
        values=dotenv_values(a.env_file)
        for key in ('DEEPSEEK_API_KEYS','DEEPSEEK_API_KEY','DEEPSEEK_API_KEY_2','DEEPSEEK_API_KEY_3','DEEPSEEK_BASE_URL','DEEPSEEK_MODEL','DEEPSEEK_MAX_CONCURRENCY'):
            if values.get(key):env[key]=str(values[key])
        if not env.get('STAND_ADMIN_URL') and values.get('DB_USER') and values.get('DB_PASSWORD'):
            env['STAND_ADMIN_URL']='postgresql://'+urllib.parse.quote(str(values['DB_USER']),safe='')+':'+urllib.parse.quote(str(values['DB_PASSWORD']),safe='')+f'@127.0.0.1:{a.db_admin_port}/postgres'
    os.environ.update({key:value for key,value in env.items() if key in ('STAND_ADMIN_URL','DEEPSEEK_API_KEYS','DEEPSEEK_API_KEY','DEEPSEEK_MODEL')})
    result=preflight(a.port,a.python,verify_machine=True);a.directory.mkdir(parents=True,exist_ok=True);(a.directory/'preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    if result['status']!='READY':return 2
    if a.preflight_only:return 0
    identity = code_identity()
    (a.directory / 'code-identity.json').write_text(json.dumps(identity, ensure_ascii=False, indent=2) + '\n')
    if a.check_bootstrap:
        check_bootstrap(a.directory, a.port, a.python, env)
        (a.directory / 'runner-result.json').write_text(json.dumps(
            summarize_runs(a.directory, 0), ensure_ascii=False, indent=2) + '\n')
        return 0
    env.update(BROWSER_PYTHON=a.python,P4K_FULL_PATH='1',P4K_REAL_PROVIDER='1',
               P4K_EVIDENCE_DIRECTORY=str(a.directory.resolve()),P4K_PORT=str(a.port),
               P4K_CODE_IDENTITY=json.dumps(identity))
    completed = subprocess.run(['npx','playwright','test','tests/browser/path29-participant.spec.mjs',
        '--workers=1','--reporter=line'],cwd=ROOT,env=env)
    summary = summarize_runs(a.directory, completed.returncode)
    (a.directory / 'runner-result.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return completed.returncode

if __name__=='__main__':raise SystemExit(main())
