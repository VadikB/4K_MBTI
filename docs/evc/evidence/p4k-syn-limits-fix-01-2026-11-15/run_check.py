"""Candidate check using the existing suite limits; no 30s microprobe wrapper."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
name=sys.argv[1];command=sys.argv[2:]
env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','SYSTEMROOT')}
env.update(PYTHON_DOTENV_DISABLED='1',DB_POOL_MIN_SIZE='0',PYTHONPATH=str(OUT)+':'+str(ROOT),
 AUDIT_GUARD_FILE=str(OUT/(name+'-guard.json')),LOG_TO_FILE='false')
if command[0]=='node':command[1:1]=['--import',str(OUT/'netguard.mjs')]
started=time.monotonic()
with (OUT/(name+'.log')).open('w') as log:
 result=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
value={'command':command,'exit_code':result.returncode,'wall_seconds':time.monotonic()-started}
(OUT/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
sys.exit(result.returncode)
