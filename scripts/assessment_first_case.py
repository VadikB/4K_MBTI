"""Preflight and entrypoint for the superadmin-to-first-case synthetic run."""
from __future__ import annotations
import argparse,hashlib,json,os,re,shutil,socket,subprocess,sys,urllib.parse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def preflight(port:int,python_path:str|None=None,*,verify_machine:bool=False,
              legacy_model_present:bool|None=None)->dict:
    checks=[]
    def add(code,ready,detail):checks.append({'code':code,'status':'READY' if ready else 'BLOCKED','detail':detail})
    add('isolated_database_admin',bool(os.getenv('STAND_ADMIN_URL')),
        'STAND_ADMIN_URL is set' if os.getenv('STAND_ADMIN_URL') else 'STAND_ADMIN_URL is required')
    python=Path(python_path) if python_path else ROOT/'.venv/bin/python';add('python_environment',python.is_file(),str(python) if python.is_file() else f'{python} is required')
    playwright=ROOT/'node_modules/.bin/playwright';add('browser',playwright.is_file(),str(playwright) if playwright.is_file() else 'npm ci is required')
    keys=any(bool(os.getenv(key)) for key in ('DEEPSEEK_API_KEYS','DEEPSEEK_API_KEY',
                                             'DEEPSEEK_API_KEY_2','DEEPSEEK_API_KEY_3'))
    add('real_provider',keys,'provider credentials are set' if keys else 'DeepSeek provider credentials are required')
    provider={'model_source':'provider_contract', 'legacy_env_model_present':
              'DEEPSEEK_MODEL' in os.environ if legacy_model_present is None else legacy_model_present,
              'legacy_env_model_ignored':True}
    try:
        from Api.llm.provider_contract import load_provider_contract
        contract=load_provider_contract()
        provider.update(provider=contract['provider'],model=contract['model'],
                        contract_id=contract['id'],contract_version=contract['version'],
                        contract_checksum=contract['checksum'])
        add('provider_contract',True,'versioned provider contract verified; model is not selected by env')
    except (OSError,ValueError,KeyError,TypeError):
        add('provider_contract',False,'required provider contract unavailable or invalid; no env fallback')
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
    return {'status':'READY' if all(c['status']=='READY' for c in checks) else 'BLOCKED','checks':checks,
            'provider':provider}


def code_identity():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    paths = ['scripts/test_stand.py', 'scripts/assessment_first_case.py',
        'Api/config.py', 'Api/llm/deepseek_gateway.py', 'Api/llm/provider_contract.py',
        'assessment_definitions/providers/deepseek/v1/manifest.json',
        'tests/path29_browser_inputs.py', 'tests/path29_browser_app.py',
        'tests/assessment_first_case_evidence.py', 'tests/browser/path29-participant.spec.mjs',
        'tests/assessment_completion_evidence.py',
        'tests/browser/fixtures/assessment-completion-profile.mjs',
        'tests/browser/fixtures/receipt-file.mjs', 'tests/browser/fixtures/preparation-receipt.mjs',
        'tests/browser/fixtures/path-viewports.mjs',
        'tests/browser/fixtures/auth-password-form.mjs', 'tests/browser/fixtures/failure-page.mjs',
        'tests/path_start_release_source.py', 'tests/path_start_release_inputs.py',
        'tests/browser/fixtures/path-start-release.json']
    return {'sha': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'),
        'origin_main': git('rev-parse', 'origin/main'),
        'worktree_status': git('status', '--short'),
        'files': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}}


def select_release(program_source, *, path=None, sha256=None, version=None):
    """Select inputs before reading credentials or opening a stand/database."""
    explicit = any(value is not None for value in (path, sha256, version))
    if program_source != 'published-pilot':
        if explicit:
            raise ValueError('RELEASE_RECEIPT_REQUIRES_PUBLISHED_PILOT')
        return None
    from tests.path_start_release_source import load_release_receipt
    return load_release_receipt(path=path, sha256=sha256, version=version)[1]


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
            'program_source': env.get('P4K_PROGRAM_SOURCE'),
            'published_release_ref': json.loads(env['P4K_PUBLISHED_RELEASE_REF'])
                if env.get('P4K_PUBLISHED_RELEASE_REF') else None,
            'llm_calls': 0}, indent=2) + '\n')
        cli('bootstrap')
        subprocess.run([python, str(ROOT / 'tests/path29_browser_inputs.py'), '--state', str(state_path)],
            cwd=ROOT, env={**env, 'P4K_FULL_PATH': '1'}, check=True, timeout=180)
    finally:
        cli('destroy')
    receipt = run_directory / 'source-provenance.json'
    (run_directory / 'completion.json').write_text(json.dumps({
        'run_id': state['run_id'], 'status': 'completed', 'exit_code': 0,
        'receipt_file': receipt.name, 'receipt_sha256': hashlib.sha256(receipt.read_bytes()).hexdigest()}) + '\n')
    print('PASS bootstrap_repeat; sources verified; LLM_CALLS=0; owned database removed', flush=True)


def summarize_runs(directory, exit_code):
    runs = []
    for run_path in sorted(directory.glob('*/run.json')):
        run_directory = run_path.parent
        errors = []
        def read(name):
            file = run_directory / (name + '.json')
            try:
                value = json.loads(file.read_text())
                if not isinstance(value, dict):
                    raise ValueError('JSON_OBJECT_REQUIRED')
                return value
            except (OSError, ValueError):
                errors.append('MISSING_OR_INVALID:' + name)
                return {}
        run, cleanup = read('run'), read('cleanup')
        completion = read('completion')
        process_file = run_directory / 'process-result.json'
        process = read('process-result') if process_file.exists() else None
        process_exit = process.get('exit_code') if process is not None else exit_code
        if type(process_exit) is not int or process_exit != 0:
            errors.append('PROCESS_EXIT_NOT_ZERO')
        if process is not None and process.get('run_id') != run.get('run_id'):
            errors.append('PROCESS_RUN_MISMATCH')
        if (completion.get('status') != 'completed' or type(completion.get('exit_code')) is not int
                or completion.get('exit_code') != 0 or not run.get('run_id')
                or completion.get('run_id') != run.get('run_id')):
            errors.append('RUN_NOT_COMPLETED')
        if (not all(cleanup.get(key) is True for key in ('owner_verified', 'database_absent', 'state_absent'))
                or not run.get('database') or cleanup.get('run_id') != run.get('run_id')
                or cleanup.get('database') != run.get('database')):
            errors.append('CLEANUP_NOT_VERIFIED')
        for name in ('failure', 'failure-receipt', 'cleanup-deferred'):
            if (run_directory / (name + '.json')).exists():
                errors.append('FAILURE_ARTIFACT:' + name)
        bootstrap = run.get('scope') == 'bootstrap_repeat'
        composite = run.get('profile') == 'assessment-execution-contour/1'
        receipt_name = 'source-provenance' if bootstrap else 'first-case-receipt'
        receipt_path = run_directory / (receipt_name + '.json')
        receipt = read(receipt_name)
        terminal_receipt_path = (run_directory / 'execution-contour-receipt.json'
                                 if composite else receipt_path)
        try:
            receipt_digest = hashlib.sha256(terminal_receipt_path.read_bytes()).hexdigest()
        except OSError:
            receipt_digest = None
        if (completion.get('receipt_file') != terminal_receipt_path.name or not receipt_digest
                or completion.get('receipt_sha256') != receipt_digest):
            errors.append('COMPLETION_RECEIPT_MISMATCH')
        selected = run.get('published_release_ref')
        source_path = None
        source = None
        before = read('source-to-runtime-receipt') if not bootstrap else {}
        program = receipt.get('program_definition')
        before_program = before.get('program_definition')
        provenance_source = receipt.get('release')
        provenance_program = provenance_source.get('program') if isinstance(provenance_source, dict) else None
        is_published = (run.get('program_source') == 'published-pilot'
                        or isinstance(program, dict) and program.get('code') == 'specialist_pilot'
                        or isinstance(before_program, dict) and before_program.get('code') == 'specialist_pilot'
                        or isinstance(provenance_program, dict) and provenance_program.get('code') == 'specialist_pilot'
                        or selected is not None)
        if is_published:
            try:
                from tests.path_start_release_source import load_release_receipt
                source_path = run_directory / 'published-release-source.json'
                source, actual = load_release_receipt(path=source_path, sha256=selected['sha256'],
                                                     version=selected['program']['version'])
                if actual['program'] != selected['program']:
                    raise ValueError('RELEASE_REFERENCE_MISMATCH')
            except (ValueError, TypeError, KeyError):
                errors.append('PUBLISHED_RELEASE_EVIDENCE_INVALID')
                source_path = None
        if bootstrap:
            case = receipt.get('case') if isinstance(receipt.get('case'), dict) else {}
            def digest(value):
                raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
                return hashlib.sha256(raw.encode()).hexdigest()
            qa = receipt.get('qa_evidence') or []
            if (not re.fullmatch('[a-f0-9]{64}', str(case.get('imported_checksum', '')))
                    or case.get('imported_checksum') != case.get('imported_recomputed_checksum')
                    or digest(case.get('imported_json')) != case.get('imported_checksum')
                    or not isinstance(qa, list) or not qa
                    or any(not isinstance(row, dict) or digest(row.get('evidence_json')) != row.get('evidence_checksum')
                           for row in qa)):
                errors.append('SOURCE_PROVENANCE_INVALID')
            if is_published and (source is None or receipt.get('release') != source
                                 or receipt.get('release_receipt_sha256') != selected['sha256']):
                errors.append('PUBLISHED_RELEASE_PROVENANCE_MISMATCH')
        else:
            if receipt and before:
                try:
                    checked = subprocess.run(['node', str(ROOT / 'tests/browser/fixtures/preparation-receipt.mjs'),
                        str(receipt_path), str(run_directory / 'source-to-runtime-receipt.json')]
                        + ([str(source_path)] if source_path else []),
                        capture_output=True, timeout=30)
                    if checked.returncode:
                        errors.append('FIRST_CASE_EVIDENCE_INVALID')
                except (OSError, subprocess.TimeoutExpired):
                    errors.append('EVIDENCE_VALIDATOR_UNAVAILABLE')
            else:
                errors.append('FIRST_CASE_EVIDENCE_INVALID')
            if not (run_directory / 'first-case.png').is_file():
                errors.append('PRESENTATION_SCREENSHOT_MISSING')
            if composite:
                try:
                    from tests.assessment_completion_evidence import validate_completion
                    errors.extend(validate_completion(run_directory, run=run, first_case=receipt,
                        completion=completion, cleanup=cleanup, process_exit=process_exit))
                except (OSError, ValueError, KeyError, TypeError):
                    errors.append('COMPOSITE_VALIDATOR_UNAVAILABLE')
        log = run_directory / 'server.log'
        completions = [{'duration_ms': float(match[0]), 'routing_key': match[1]}
            for match in re.findall(
                r'DeepSeek request completed duration_ms=([0-9.]+)[^\n]*routing_key=([a-f0-9-]{36}:[a-zA-Z0-9:_-]+)',
                log.read_text() if log.exists() else '')]
        runs.append({'run': run, 'cleanup': cleanup,
            'result': ('PASS_BOOTSTRAP_ONLY' if bootstrap else 'PASS') if not errors else 'FAIL',
            'completion': completion, 'process_exit_code': process_exit, 'validation_errors': errors,
            'evidence_directory': str(run_directory),
            'failure': read('failure') if (run_directory / 'failure.json').exists() else None,
            'provider_completed_requests': len(completions),
            'provider_completions': completions,
            'usage_note': 'Receipt totals count unique retained operations; JSON retries have separate completions, but earlier malformed-response usage is not retained by product trace.'})
    success = exit_code == 0 and bool(runs) and all(run['result'] != 'FAIL' for run in runs)
    profile = ('assessment-execution-contour/1'
               if any(item.get('run', {}).get('profile') == 'assessment-execution-contour/1' for item in runs)
               else 'assessment-first-case/1.1')
    return {'profile': profile, 'scope': 'synthetic_diagnostic',
        'process_exit_code': exit_code, 'exit_code': exit_code if exit_code else (0 if success else 1),
        'result': 'PASS' if success else 'FAIL', 'runs': runs}


def record_process_result(directory, previous, exit_code):
    """Bind the actual child exit only to runs created by this invocation."""
    for file in set(directory.glob('*/run.json')) - previous:
        try:
            run = json.loads(file.read_text())
            (file.parent / 'process-result.json').write_text(json.dumps({
                'run_id': run['run_id'], 'exit_code': exit_code}) + '\n')
        except (OSError, ValueError, KeyError, TypeError):
            # Summary fails closed on malformed/missing evidence.
            continue

def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=ROOT/'.test-stand/assessment-first-case');p.add_argument('--port',type=int,default=18861);p.add_argument('--preflight-only',action='store_true');p.add_argument('--env-file',type=Path);p.add_argument('--python',default=str(ROOT/'.venv/bin/python'));p.add_argument('--db-admin-port',type=int,default=55432)
    p.add_argument('--check-bootstrap', action='store_true', help='Repeat create/bootstrap/minimal seed/destroy without LLM')
    p.add_argument('--program-source', choices=('functional-diagnostic', 'published-pilot'),
        default='functional-diagnostic', help='Explicit approved nine-case PATH release, or historical one-case diagnostic')
    p.add_argument('--program-receipt', type=Path, help='Exact published source receipt; requires SHA256 and program version')
    p.add_argument('--program-receipt-sha256', help='Expected SHA256 of the receipt bytes, not the program definition')
    p.add_argument('--program-version', help='Expected program version in the selected published receipt; never latest')
    p.add_argument('--profile', choices=('first-case', 'ac18-to-report'), default='first-case',
        help='Keep standalone AC18, or continue its owned DB/Cycle through explicit Report opening')
    p.add_argument('--summarize-only', action='store_true', help='Rebuild normalized summary from existing evidence; no credentials or LLM')
    a=p.parse_args()
    if a.summarize_only:
        original = json.loads((a.directory / 'runner-result.json').read_text())
        summary = summarize_runs(a.directory, original.get('process_exit_code', original['exit_code']))
        (a.directory / 'runner-result.normalized.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary['exit_code']
    try:
        selected = select_release(a.program_source, path=a.program_receipt,
                                  sha256=a.program_receipt_sha256, version=a.program_version)
    except ValueError as exc:
        p.error(str(exc))
    env=os.environ.copy()
    legacy_model_present='DEEPSEEK_MODEL' in env
    env.pop('DEEPSEEK_MODEL',None)
    env.pop('P4K_PUBLISHED_RELEASE_REF', None)
    if selected is not None:
        env['P4K_PUBLISHED_RELEASE_REF'] = json.dumps(selected)
    env['P4K_PROGRAM_SOURCE'] = a.program_source
    if a.env_file:
        from dotenv import dotenv_values
        values=dotenv_values(a.env_file)
        legacy_model_present=legacy_model_present or 'DEEPSEEK_MODEL' in values
        for key in ('DEEPSEEK_API_KEYS','DEEPSEEK_API_KEY','DEEPSEEK_API_KEY_2','DEEPSEEK_API_KEY_3','DEEPSEEK_BASE_URL','DEEPSEEK_MAX_CONCURRENCY'):
            if values.get(key):env[key]=str(values[key])
        if not env.get('STAND_ADMIN_URL') and values.get('DB_USER') and values.get('DB_PASSWORD'):
            env['STAND_ADMIN_URL']='postgresql://'+urllib.parse.quote(str(values['DB_USER']),safe='')+':'+urllib.parse.quote(str(values['DB_PASSWORD']),safe='')+f'@127.0.0.1:{a.db_admin_port}/postgres'
    os.environ.update({key:value for key,value in env.items() if key in ('STAND_ADMIN_URL',
        'DEEPSEEK_API_KEYS','DEEPSEEK_API_KEY','DEEPSEEK_API_KEY_2','DEEPSEEK_API_KEY_3',
        'DEEPSEEK_BASE_URL','DEEPSEEK_MAX_CONCURRENCY')})
    result=preflight(a.port,a.python,verify_machine=True,legacy_model_present=legacy_model_present);a.directory.mkdir(parents=True,exist_ok=True);(a.directory/'preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    if result['status']!='READY':return 2
    if a.preflight_only:return 0
    identity = code_identity()
    (a.directory / 'code-identity.json').write_text(json.dumps(identity, ensure_ascii=False, indent=2) + '\n')
    if a.check_bootstrap:
        previous = set(a.directory.glob('*/run.json'))
        try:
            check_bootstrap(a.directory, a.port, a.python, env)
            exit_code = 0
        except (OSError, ValueError, subprocess.SubprocessError):
            exit_code = 1
        record_process_result(a.directory, previous, exit_code)
        summary = summarize_runs(a.directory, exit_code)
        (a.directory / 'runner-result.json').write_text(json.dumps(
            summary, ensure_ascii=False, indent=2) + '\n')
        return summary['exit_code']
    env.update(BROWSER_PYTHON=a.python,P4K_FULL_PATH='1',P4K_REAL_PROVIDER='1',
               P4K_EVIDENCE_DIRECTORY=str(a.directory.resolve()),P4K_PORT=str(a.port),
               P4K_CODE_IDENTITY=json.dumps(identity))
    if a.profile == 'ac18-to-report':
        env['P4K_COMPLETION_PROFILE'] = '1'
    previous = set(a.directory.glob('*/run.json'))
    completed = subprocess.run(['npx','playwright','test','tests/browser/path29-participant.spec.mjs',
        '--workers=1','--reporter=line'],cwd=ROOT,env=env)
    record_process_result(a.directory, previous, completed.returncode)
    summary = summarize_runs(a.directory, completed.returncode)
    (a.directory / 'runner-result.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary['exit_code']

if __name__=='__main__':raise SystemExit(main())
