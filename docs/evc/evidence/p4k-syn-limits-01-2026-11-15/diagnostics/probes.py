"""Минимальные входы к существующим функциям; продукт не изменяется."""
import json, os, signal, subprocess, sys, time
from pathlib import Path
probe, root, output = sys.argv[1:]
root, output = Path(root), Path(output)
sys.path.insert(0,str(root))
def save(value):
    (output/(probe+'.json')).write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(value),flush=True)
if probe == 'L04':
    from Api.llm.deepseek_gateway import DeepSeekGateway
    from Api.m5_functional_generation_service import _strict_json_call
    import Api.llm.deepseek_gateway as transport
    fake_calls=[]; traces=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({'choices':[{'message':{'content':'{invalid'},'finish_reason':'stop'}],
            'usage':{'total_tokens':9}}).encode()
    def synthetic_urlopen(req,timeout):
        fake_calls.append({'attempt':len(fake_calls)+1,'timeout_parameter':timeout})
        if len(fake_calls)%2:raise TimeoutError('synthetic timeout before any network')
        return Response()
    transport.request.urlopen=synthetic_urlopen
    gateway=DeepSeekGateway(api_keys=['synthetic-key-a','synthetic-key-b'],model='deepseek-flash')
    original=gateway.chat_with_trace
    def observed(*args,**kwargs):
        response=original(*args,**kwargs)
        traces.append({'routing_key':kwargs['routing_key'],'transport_attempts':response.provider['transport_attempts'],
            'usage':response.provider['usage']})
        return response
    gateway.chat_with_trace=observed
    reasons=[]
    for entry in (1,2):
        try:_strict_json_call(gateway,[{'role':'user','content':'synthetic'}],operation_id='audit-same-operation',
            max_tokens=20,temperature=0,retry_instruction='synthetic diagnostic retry input')
        except ValueError as error:reasons.append({'entry':entry,'reason':str(error),'cumulative_fake_calls':len(fake_calls)})
    save({'status':'FAIL','operation_id':'audit-same-operation','fake_calls':fake_calls,'traces':traces,
        'entries':reasons,'external_calls':0,'shared_operation_budget':'absent in exercised function',
        'scope':'actual strict JSON retry + actual key rotation; repair and durable queue not executed'})
elif probe == 'L05':
    from scripts import test_stand_check as runner
    from io import BytesIO
    from types import SimpleNamespace
    original_popen=subprocess.Popen
    statefile=output/'diagnostics/l05-state.json'
    actions=[];process=None
    parent_code="""import json,os,subprocess,sys,time
from pathlib import Path
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
Path(sys.argv[1]).write_text(json.dumps({'parent_pid':os.getpid(),'child_pid':child.pid,'pgid':os.getpgrp()}))
time.sleep(60)
"""
    def popen(*args,**kwargs):
        global process
        process=original_popen([sys.executable,'-c',parent_code,str(statefile)],env=os.environ.copy(),
            stdout=kwargs.get('stdout'),stderr=kwargs.get('stderr'),cwd=root)
        return process
    def run(command,**kwargs):
        action=command[2]; actions.append(action)
        if action=='create':
            state=Path(command[command.index('--state')+1]);state.write_text('{}')
        if action=='smoke':
            deadline=time.monotonic()+2
            while not statefile.exists() and time.monotonic()<deadline:time.sleep(.01)
            if not statefile.exists():raise RuntimeError('DIAGNOSTIC_CHILD_START_FAILED')
            os.kill(os.getpid(),signal.SIGINT)
        return SimpleNamespace(returncode=0)
    runner.subprocess.Popen=popen;runner.subprocess.run=run
    runner.urllib.request.urlopen=lambda *args,**kwargs:BytesIO(b'{"status":"ready"}')
    interrupted=False
    try:runner.check(output/'L05-fixture',18999)
    except KeyboardInterrupt:interrupted=True
    state=json.loads(statefile.read_text())
    try:os.kill(state['child_pid'],0);child_alive=True
    except ProcessLookupError:child_alive=False
    save({'status':'FAIL' if child_alive else 'PASS','signal':'SIGINT','caught_interrupt':interrupted,
        **state,'parent_exit_code':process.poll(),'descendant_alive_after_native_cleanup':child_alive,
        'actions_spy':actions,'database':'NOT_CREATED','scope':'actual check() finally; real own process tree; CLI/HTTP are synthetic'})
elif probe in ('L06','L06-verify'):
    node=os.environ['AUDIT_NODE']
    if probe == 'L06':
        subprocess.run([node,'--import',str(output/'diagnostics/netguard.mjs'),str(output/'diagnostics/probes.mjs'),
            'L06-export',str(root),str(output)],check=True,timeout=5,
            env={**os.environ,'AUDIT_GUARD_FILE':str(output/'L06-node-guard.json')})
    from scripts.assessment_first_case import summarize_runs
    summary=summarize_runs(output,0 if probe == 'L06-verify' else 1)
    (output/('L06-summary-verified.json' if probe == 'L06-verify' else 'L06-summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
    save({'status':'PARTIAL','summary_result':summary['result'],'summary_exit':summary['exit_code'],
        'database_preservation':'NOT_RUN: no DB','source':'L06-export.json + L06-summary.json'})
