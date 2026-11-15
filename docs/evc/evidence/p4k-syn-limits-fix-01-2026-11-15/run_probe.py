"""Independent <=30s diagnostic supervisor, never a product limiter."""
import json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
name=sys.argv[1];command=sys.argv[2:]
env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','SYSTEMROOT')}
env.update(PYTHON_DOTENV_DISABLED='1',DB_POOL_MIN_SIZE='0',PYTHONPATH=str(OUT)+':'+str(ROOT),
           AUDIT_GUARD_FILE=str(OUT/(name+'-guard.json')),LOG_TO_FILE='false')
if command[0]=='node':command[1:1]=['--import',str(OUT/'netguard.mjs')]
started=time.monotonic()
with (OUT/(name+'.log')).open('w') as log:
 process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 with (OUT/'resources.jsonl').open('a') as registry:
  registry.write(json.dumps({'probe':name,'pid':process.pid,'pgid':process.pid,'timeout':30,
   'command':command,'restart':'no','ports':[],'containers':[]})+'\n')
 try:code=process.wait(timeout=30);timed_out=False
 except subprocess.TimeoutExpired:code=1;timed_out=True
 finally:
  for sig in (signal.SIGTERM,signal.SIGKILL):
   try:os.killpg(process.pid,sig)
   except ProcessLookupError:pass
  process.wait(timeout=5)
 result={'exit_code':code,'external_timeout':timed_out,'wall_seconds':time.monotonic()-started}
 (OUT/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
 sys.exit(code)
