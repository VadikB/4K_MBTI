"""Внешний bounded supervisor аудита, не штатный runner Product 4K."""
import datetime, json, os, shutil, signal, subprocess, sys, time
from pathlib import Path
out=Path(__file__).resolve().parents[1]
root=Path('/private/tmp/p4k-syn-limits-01-20261115')
python=Path('/Users/vadim_bogachev/Developer/4K/.venv/bin/python')
node=shutil.which('node')
env={'PATH':os.defpath,'PYTHONPATH':str(out/'diagnostics')+os.pathsep+str(root),
    'PYTHON_DOTENV_DISABLED':'1','PYTHONDONTWRITEBYTECODE':'1',
    'AGENT4K_ISOLATED_STAND':'1','DB_HOST':'127.0.0.1','DB_NAME':'product4k_pytest_audit_not_created',
    'DB_USER':'synthetic','AGENT4K_STAND_MARKER':'stand-10.2:audit','DB_POOL_MIN_SIZE':'0',
    'LOG_TO_FILE':'false','LOG_TO_STDOUT':'false','AUDIT_NODE':node}
results=json.loads((out/'probes.json').read_text()) if (out/'probes.json').exists() else []
already={json.loads(line)['probe'] for line in (out/'resources.jsonl').read_text().splitlines()} if (out/'resources.jsonl').exists() else set()
(out/'L01.json').write_text(json.dumps({'status':'NOT_RUN','reason':'No existing 5–10 s profile; native 120 s wait exceeds external 30 s limit',
    'native_wait_ms':120000,'no_progress_limit':'not found; heartbeat is not progress'},indent=2)+'\n')
selection=([('L06-verify',10)] if sys.argv[1:]==['L06-verify'] else [('L02',2),('L03',10),('L04',10),('L05',10),('L06',10)])
for probe,timeout in selection:
    if probe in already:continue
    child_env={**env,'AUDIT_GUARD_FILE':str(out/(probe+'-guard.json'))}
    command=([node,'--import',str(out/'diagnostics/netguard.mjs'),str(out/'diagnostics/probes.mjs')]
        if probe in ('L02','L03') else [str(python),str(out/'diagnostics/probes.py')])+[probe,str(root),str(out)]
    started=time.monotonic();timed_out=False
    with (out/(probe+'.log')).open('w') as log:
        process=subprocess.Popen(command,env=child_env,cwd=root,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        resource={'probe':probe,'pid':process.pid,'pgid':process.pid,'owner':'P4K-SYN-LIMITS-01',
            'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':command,'timeout_s':timeout}
        with (out/'resources.jsonl').open('a') as file:file.write(json.dumps(resource)+'\n')
        try:process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:timed_out=True
        code_before_cleanup=process.poll()
        cleanup_started=time.monotonic()
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=2)
        # Root may already have exited while a grandchild remains in its group.
        time.sleep(.15)
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    pids=[process.pid]
    if probe=='L05' and (out/'diagnostics/l05-state.json').exists():
        state=json.loads((out/'diagnostics/l05-state.json').read_text());pids += [state['parent_pid'],state['child_pid']]
    result={**resource,'external_timeout':timed_out,'exit_before_external_cleanup':code_before_cleanup,
        'final_exit_code':process.returncode,'wall_s':round(time.monotonic()-started,4),
        'teardown_s':round(time.monotonic()-cleanup_started,4),'process_readback':'PENDING'}
    results.append(result)
    (out/'probes.json').write_text(json.dumps(results,indent=2)+'\n')
    try:
        readback=subprocess.run(['/bin/ps','-o','pid=,ppid=,pgid=,stat=','-p',','.join(map(str,pids))],capture_output=True,text=True)
        result['process_readback']=readback.stdout.strip()
    except PermissionError:result['process_readback']='BLOCKED_BY_SANDBOX'
    (out/'probes.json').write_text(json.dumps(results,indent=2)+'\n')
(out/'probes.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps([{k:r[k] for k in ('probe','external_timeout','final_exit_code','wall_s','process_readback')} for r in results],indent=2))
