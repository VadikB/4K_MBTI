import os,sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from scripts.owned_process import run_bounded
out=Path('docs/evc/tasks/p4k-w02-fix-01/evidence')/sys.argv[1];out.mkdir(parents=True,exist_ok=True)
out=out.resolve()
env={**os.environ,'W02_FIX_EVIDENCE':'1','W02_ADD02_EVIDENCE':'1','W02_EVIDENCE_DIR':str(out),'W02_RESOURCE_LOG':str(out/'resources.jsonl'),'W02_PROGRESS':str(out/'progress.json'),'W02_OWNER_REGISTRY':str(out/'owner.json'),'W02_RUN_RECEIPT':str(out/'run.json'),'W02_REFERENCE_UNUSED':'/Users/dmitriyzemlyanov/Library/CloudStorage/GoogleDrive-dozemlyanov@gmail.com/Мой диск/HC Ai/Архитектура/1.0 Доработка Полная/обработка замечаний/знакомство/LIDUM-W02.html','AGENT4K_SYNTHETIC_ONLY':'1'}
cmd=['node_modules/.bin/playwright','test',*sys.argv[2:],'--workers=1','--retries=0','--global-timeout=600000','--reporter=list,/private/tmp/p4k-w02-fix-reporter.cjs']
(out/'plan.json').write_text(json.dumps({'run_id':sys.argv[1],'command':cmd,'ports':['ephemeral W02 fixtures','18764 auth fixture','18766 auth recovery fixture','18784 waiting fixture'],'db':None,'containers':[],'restart_policy':'no','llm':0,'mail':0,'status':'read owner.json and resources.jsonl; ps -p PID; lsof -nP -iTCP:PORT -sTCP:LISTEN','stop':'python3 -c "from scripts.owned_process import OwnedProcess; OwnedProcess(REGISTRY).recover()"','deadline_seconds':600,'no_progress_seconds':90},ensure_ascii=False,indent=2))
try:
 result=run_bounded(cmd,registry=out/'owner.json',deadline_seconds=600,no_progress_seconds=90,progress_file=out/'progress.json',env=env)
finally:
 # The native runner always stops the owned process group, including descendants.
 print('owner_registry_remaining', (out/'owner.json').exists(),flush=True)
(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
sys.exit(result['returncode'])
