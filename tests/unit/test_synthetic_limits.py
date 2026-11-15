"""Synthetic limiter regressions; no database, credentials, mail or real provider."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from scripts.owned_process import OwnedProcess, run_bounded


def test_strict_retry_reentry_keeps_reservation_and_deadline(monkeypatch):
    from Api.llm import deepseek_gateway as transport
    from Api.m5_functional_generation_service import _strict_json_call
    calls = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({'choices': [{'message': {'content': '{invalid'}, 'finish_reason': 'stop'}]}).encode()
    def send(*args, **kwargs):
        calls.append(kwargs['timeout'])
        if len(calls) % 2: raise TimeoutError('synthetic unknown outcome')
        return Response()
    monkeypatch.setattr(transport.request, 'urlopen', send)
    monkeypatch.setattr(transport, 'pause_thread_connections_for_external_io', lambda: 0)
    gateway = transport.DeepSeekGateway(api_keys=['synthetic-a', 'synthetic-b'],
        operation_max_attempts=5, operation_timeout_seconds=2)
    def invoke(key):
        return _strict_json_call(gateway, [{'role': 'user', 'content': 'synthetic'}],
            operation_id=key, max_tokens=20, temperature=0, retry_instruction='synthetic retry')
    with pytest.raises(ValueError, match='PROVIDER_JSON_INVALID'): invoke('same')
    budget = gateway.operation_budget('same')
    deadline = budget.deadline
    assert budget.used == 4
    with pytest.raises(ValueError, match='OPERATION_ATTEMPT_LIMIT'): invoke('same')
    print(json.dumps({'operation':'same','calls':len(calls),'limit':budget.limit,'used':budget.used,'deadline_preserved':budget.deadline==deadline}))
    assert len(calls) == 5 and budget.used == 5 and budget.deadline == deadline
    with pytest.raises(ValueError, match='OPERATION_ATTEMPT_LIMIT'): invoke('same')
    assert len(calls) == 5
    with pytest.raises(ValueError, match='PROVIDER_JSON_INVALID'): invoke('other')
    assert len(calls) == 8  # independent operation: response/timeout/response
    assert gateway.operation_budget('other').used == 3
    fresh = transport.DeepSeekGateway(api_keys=['synthetic'], operation_max_attempts=1)
    assert fresh.operation_budget('same').used == 0
    budget.deadline = time.monotonic() - 1
    with pytest.raises(ValueError, match='OPERATION_DEADLINE_EXCEEDED'): invoke('same')
    assert len(calls) == 8


def test_strict_positive_control_and_native_synthetic_guard(monkeypatch):
    from Api.llm import deepseek_gateway as transport
    from Api.m5_functional_generation_service import _strict_json_call
    from tests.controlled_functional_provider import ControlledFunctionalProvider
    monkeypatch.setenv('AGENT4K_SYNTHETIC_ONLY', '1')
    sent = []
    monkeypatch.setattr(transport.request, 'urlopen', lambda *a, **kw: sent.append('forbidden'))
    # Captured native class stays blocked even if controlled installation is missing.
    with pytest.raises(RuntimeError, match='SYNTHETIC_PROFILE_EXTERNAL_PROVIDER_FORBIDDEN'):
        transport.DeepSeekGateway(api_keys=['synthetic']).chat_with_trace([])
    assert sent == []
    controlled = ControlledFunctionalProvider()
    value, _, failures = _strict_json_call(controlled, [{'role': 'user', 'content': json.dumps({
        'candidate_checksum': 'synthetic', 'protected_checks': []})}], operation_id='test:tester:1',
        max_tokens=20, temperature=0, retry_instruction='synthetic')
    assert value == {'candidate_checksum': 'synthetic', 'checks': []} and failures == []


def test_native_transport_positive_budget(monkeypatch):
    from Api.llm import deepseek_gateway as transport
    from Api.m5_functional_generation_service import _strict_json_call
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{"choices":[{"message":{"content":"{}"}}]}'
    monkeypatch.setattr(transport.request, 'urlopen', lambda *a, **kw: Response())
    monkeypatch.setattr(transport, 'pause_thread_connections_for_external_io', lambda: 0)
    gateway = transport.DeepSeekGateway(api_keys=['synthetic'], operation_max_attempts=1)
    assert _strict_json_call(gateway, [], operation_id='ok', max_tokens=20,
        temperature=0, retry_instruction='synthetic')[0] == {}
    assert gateway.operation_budget('ok').used == 1


@pytest.mark.parametrize('deadline,stalled,expected', [(.15, 2, 'RUN_DEADLINE_EXCEEDED'),
                                                     (2, .15, 'RUN_NO_PROGRESS_EXCEEDED')])
def test_runner_limits_ignore_heartbeat(tmp_path, deadline, stalled, expected):
    file = tmp_path/'progress.json'
    code = '''import json,sys,time
from pathlib import Path
for n in range(1000):
 Path(sys.argv[1]).write_text(json.dumps({'progress_key':'processing','heartbeat':n}))
 time.sleep(.01)
'''
    result = run_bounded([sys.executable, '-c', code, str(file)], registry=tmp_path/'owner.json',
        progress_file=file, deadline_seconds=deadline, no_progress_seconds=stalled)
    print(json.dumps({'expected':expected, **result}))
    assert result['reason'] == expected and result['returncode'] != 0
    assert result['wall_seconds'] < 3
    assert not (tmp_path/'owner.json').exists()


def test_runner_positive_cleanup(tmp_path):
    result = run_bounded([sys.executable, '-c', 'pass'], registry=tmp_path/'owner.json',
        progress_file=tmp_path/'progress.json', deadline_seconds=2, no_progress_seconds=2)
    assert result['returncode'] == 0 and result['reason'] is None


TREE = '''import os,subprocess,sys,time,json,signal
from pathlib import Path
child=subprocess.Popen([sys.executable,'-c', 'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(20)'])
Path(sys.argv[1]).write_text(json.dumps({'parent':os.getpid(),'child':child.pid,'pgid':os.getpgrp()}))
if sys.argv[2]=='exit': sys.exit(0)
time.sleep(20)
'''


def wait_state(file):
    until = time.monotonic()+2
    while time.monotonic() < until:
        try: return json.loads(file.read_text())
        except (OSError, ValueError): time.sleep(.01)
    raise AssertionError('SYNTHETIC_CHILD_NOT_STARTED')


def assert_tree_stopped(state):
    # External ps readback: independent of the stopped parent/child code.
    output = subprocess.check_output(['ps', '-axo', 'pid=,pgid=,stat='], text=True)
    alive = [line for line in output.splitlines() if len(line.split()) == 3
             and int(line.split()[1]) == state['pgid'] and not line.split()[2].startswith('Z')]
    assert alive == []


@pytest.mark.parametrize('mode', ['wait', 'exit'])
def test_owned_tree_and_foreign_control(tmp_path, mode):
    control = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'], start_new_session=True)
    owner = OwnedProcess(tmp_path/'owner.json')
    try:
        owner.start([sys.executable, '-c', TREE, str(tmp_path/'tree.json'), mode])
        state = wait_state(tmp_path/'tree.json')
        print(json.dumps({'mode':mode,'owned_resource':json.loads(owner.registry.read_text()),'tree':state,'control_pid':control.pid}))
        if mode == 'exit': owner.process.wait(timeout=2)
        owner.stop()
        assert_tree_stopped(state)
        assert control.poll() is None
    finally:
        owner.stop()
        control.terminate(); control.wait(timeout=2)


def test_recover_after_runner_crash(tmp_path):
    code = '''from scripts.owned_process import OwnedProcess
import sys,os,time
from pathlib import Path
owner=OwnedProcess(sys.argv[1]);owner.start([sys.executable,'-c',sys.argv[3],sys.argv[2],'exit'])
while not Path(sys.argv[2]).exists(): time.sleep(.01)
os._exit(17)
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path/'owner.json'),
        str(tmp_path/'tree.json'), TREE], timeout=3)
    assert result.returncode == 17
    state = wait_state(tmp_path/'tree.json')
    OwnedProcess(tmp_path/'owner.json').recover()
    assert_tree_stopped(state)


def test_actual_check_sigint_stops_audit_descendant(tmp_path, monkeypatch):
    from scripts import test_stand_check as runner
    from io import BytesIO
    class FixtureOwner(OwnedProcess):
        def start(self, command, **kwargs):
            return super().start([sys.executable, '-c', TREE, str(tmp_path/'tree.json'), 'wait'], **kwargs)
    actions = []
    def run(command, **kwargs):
        action = command[2]; actions.append(action)
        if action == 'create': (tmp_path/'state.json').write_text('{}')
        if action == 'smoke':
            wait_state(tmp_path/'tree.json')
            os.kill(os.getpid(), signal.SIGINT)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(runner, 'OwnedProcess', FixtureOwner)
    monkeypatch.setattr(runner, 'subprocess', SimpleNamespace(run=run, STDOUT=subprocess.STDOUT))
    monkeypatch.setattr(runner.urllib.request, 'urlopen', lambda *a, **kw: BytesIO(b'{"status":"ready"}'))
    with pytest.raises(KeyboardInterrupt): runner.check(tmp_path, 18999)
    assert_tree_stopped(wait_state(tmp_path/'tree.json'))
    print(json.dumps({'actual_signal':'SIGINT','tree':wait_state(tmp_path/'tree.json'),'actions':actions,'external_ps':'no_running_members'}))
    assert actions == ['create', 'bootstrap', 'seed', 'smoke', 'destroy']


@pytest.mark.parametrize('missing', [False, True])
def test_actual_controlled_app_install_fails_closed(tmp_path, monkeypatch, missing):
    import builtins
    import contextlib
    import runpy
    from scripts import test_stand
    from Api.llm import deepseek_gateway as transport
    from tests.controlled_functional_provider import ControlledFunctionalProvider
    native = transport.DeepSeekGateway
    from Api import m10_test_gateway
    monkeypatch.setattr(m10_test_gateway, 'BrowserAcceptanceGateway', m10_test_gateway.BrowserAcceptanceGateway)
    state = {'path29_controlled_provider': True, 'path29_full_path': True,
             'path29_program_source': 'published-pilot', 'provider_mode': 'disabled', 'gateway': 1}
    file = tmp_path/'state.json'; file.write_text(json.dumps(state))
    monkeypatch.setenv('AGENT4K_ISOLATED_STAND', '1')
    monkeypatch.setenv('AGENT4K_PATH29_TEST_APP', '1')
    monkeypatch.setenv('AGENT4K_SYNTHETIC_ONLY', '0')
    monkeypatch.setenv('STAND_STATE', str(file))
    monkeypatch.setattr(test_stand, 'owned', lambda state: contextlib.nullcontext())
    monkeypatch.setattr(transport, 'DeepSeekGateway', native)
    original = builtins.__import__
    def imported(name, *args, **kwargs):
        if missing and name == 'tests.controlled_functional_provider':
            raise ImportError('SYNTHETIC_MISSING_ADAPTER')
        if name == 'main': raise RuntimeError('STOP_AFTER_ACTUAL_INSTALL')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', imported)
    with pytest.raises((ImportError, RuntimeError), match='MISSING_ADAPTER|STOP_AFTER_ACTUAL_INSTALL'):
        runpy.run_path(str(Path(__file__).resolve().parents[1]/'path29_browser_app.py'))
    if not missing: assert transport.DeepSeekGateway is ControlledFunctionalProvider
    with pytest.raises(RuntimeError, match='SYNTHETIC_PROFILE_EXTERNAL_PROVIDER_FORBIDDEN'):
        native(api_keys=['synthetic']).chat_with_trace([])


def test_export_failure_stops_compute_preserves_state(tmp_path):
    from scripts.assessment_first_case import summarize_runs
    root = Path(__file__).resolve().parents[2]
    directory = tmp_path/'run'; directory.mkdir()
    state = directory/'state.json'
    state.write_text(json.dumps({'run_id': 'synthetic-export', 'cycle_status': 'active', 'material': ['synthetic']}))
    script = directory/'probe.mjs'
    script.write_text('''import fs from 'node:fs';
import { spawn } from 'node:child_process';
import { readExecutionExport, destroyOwnedStandIfAdmitted } from 'PROFILE';
const dir=process.argv[2], state=dir+'/state.json';
const worker=spawn(process.argv[3],['-c','import time; time.sleep(20)'],{stdio:'ignore'});worker.unref();
fs.writeFileSync(dir+'/compute.json',JSON.stringify({pid:worker.pid,pgid:process.pid}));
const value={run_id:'synthetic-export',cycle_id:'cycle',collection_status:'active',situations:[]};
const page={request:{get:async()=>({ok:()=>true,json:async()=>value})}};
let reason;try{await readExecutionExport(page,'http://fixture.invalid','cycle','synthetic-export',dir,'readback');}
catch(e){reason=e.message;}
const commands=[];
try{destroyOwnedStandIfAdmitted({executionStarted:true,terminalExecutionExportSaved:false,
preparationReceiptRequired:true,terminalPreparationReceiptSaved:true,statePath:state,runId:'synthetic-export',
save:()=>{},cli:action=>{commands.push(action);fs.unlinkSync(state);}});}catch(e){}
fs.writeFileSync(dir+'/cleanup-deferred.json',JSON.stringify({reason,commands}));
fs.writeFileSync(dir+'/run.json',JSON.stringify({run_id:'synthetic-export',database:'product4k_pytest_file_fixture',
scenario_outcome:'controlled_target_completed',profile:'assessment-execution-contour/2'}));
'''.replace('PROFILE', (root/'tests/browser/fixtures/assessment-completion-profile.mjs').as_uri()))
    result = run_bounded(['node', '--import', str(root/'docs/evc/evidence/p4k-syn-limits-fix-01-2026-11-15/netguard.mjs'),
        str(script), str(directory), sys.executable], registry=tmp_path/'owner.json',
        progress_file=tmp_path/'progress.json', deadline_seconds=3, no_progress_seconds=3)
    assert result['returncode'] == 0
    compute = json.loads((directory/'compute.json').read_text())
    assert_tree_stopped(compute)
    assert json.loads(state.read_text())['material'] == ['synthetic']
    deferred = json.loads((directory/'cleanup-deferred.json').read_text())
    assert deferred == {'reason': 'EXECUTION_EXPORT_READBACK_MISMATCH', 'commands': []}
    summary = summarize_runs(tmp_path, 0)
    assert summary['result'] == 'FAIL' and summary['exit_code'] == 1 and summary['process_exit_code'] == 0
    assert 'FAILURE_ARTIFACT:cleanup-deferred' in summary['runs'][0]['validation_errors']
    assert summary['runs'][0]['run']['scenario_outcome'] == 'controlled_target_completed'
    print(json.dumps({'export':deferred,'compute':compute,'state_readback':json.loads(state.read_text()),'runner_outcome':result,'summary_result':summary['result'],'scenario_outcome':summary['runs'][0]['run']['scenario_outcome']}))


def test_registration_failure_does_not_leave_worker(tmp_path, monkeypatch):
    from scripts import owned_process as module
    processes = []
    original = subprocess.Popen
    def launch(*args, **kwargs):
        process = original(*args, **kwargs); processes.append(process)
        return process
    monkeypatch.setattr(module, 'subprocess', SimpleNamespace(Popen=launch, check_output=subprocess.check_output))
    blocked = tmp_path/'not-a-directory'; blocked.write_text('synthetic')
    with pytest.raises(FileExistsError):
        OwnedProcess(blocked/'owner.json').start([sys.executable, '-c', 'import time; time.sleep(20)'])
    assert len(processes) == 1 and processes[0].poll() is not None
    assert_tree_stopped({'pgid': processes[0].pid})


@pytest.mark.parametrize('invalid', [0, -1, float('inf'), float('nan')])
def test_profiles_require_finite_positive_limits(tmp_path, invalid):
    from Api.llm.deepseek_gateway import OperationBudget
    with pytest.raises(ValueError, match='OPERATION_LIMITS_INVALID'):
        OperationBudget(2, invalid)
    with pytest.raises(ValueError, match='RUN_LIMITS_MUST_BE_POSITIVE'):
        run_bounded(['must-not-spawn'], registry=tmp_path/'owner.json',
            deadline_seconds=invalid, no_progress_seconds=1, progress_file=tmp_path/'progress.json')
    with pytest.raises(ValueError, match='OPERATION_LIMITS_INVALID'):
        OperationBudget(invalid, 1)


def test_original_l04_counterexample_default_profile(monkeypatch):
    from Api.llm import deepseek_gateway as transport
    from Api.m5_functional_generation_service import _strict_json_call
    calls = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return b'{"choices":[{"message":{"content":"{invalid"},"finish_reason":"stop"}]}'
    def send(*args, **kwargs):
        calls.append(len(calls)+1)
        if len(calls) % 2: raise TimeoutError('synthetic timeout before network')
        return Response()
    monkeypatch.setattr(transport.request, 'urlopen', send)
    monkeypatch.setattr(transport, 'pause_thread_connections_for_external_io', lambda: 0)
    gateway = transport.DeepSeekGateway(api_keys=['synthetic-key-a', 'synthetic-key-b'], model='deepseek-flash')
    def invoke():
        return _strict_json_call(gateway, [{'role':'user','content':'synthetic'}],
            operation_id='audit-same-operation', max_tokens=20, temperature=0,
            retry_instruction='synthetic diagnostic retry input')
    with pytest.raises(ValueError, match='M5_FUNCTIONAL_PROVIDER_JSON_INVALID'): invoke()
    assert len(calls) == 4
    with pytest.raises(ValueError, match='OPERATION_ATTEMPT_LIMIT'): invoke()
    assert len(calls) == 4
    print(json.dumps({'original_counterexample':'L04','default_limit':4,'calls_after_reentry':len(calls)}))
