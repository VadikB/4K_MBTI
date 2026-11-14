import subprocess,os,time,selectors,signal,json
from pathlib import Path
root=Path.cwd(); evidence=root/os.environ.get('W02_RUN_EVIDENCE','docs/evc/tasks/p4k-w02-01/evidence')
evidence.mkdir(parents=True,exist_ok=True)
env=os.environ.copy();env['W02_RESOURCE_LOG']=str(evidence/'resources.jsonl');env['W02_EVIDENCE_DIR']=str(evidence)
cmd=['node_modules/.bin/playwright','test',*os.environ.get('W02_RUN_FILES','w02-acquaintance.spec.mjs remain04-waiting.spec.mjs remain05-first-start.spec.mjs auth-r03.spec.mjs').split(),'--grep',os.environ.get('W02_RUN_GREP','W02|UX-AUD29-03|UX-AUD29-05|REMAIN04|REMAIN05'),'--workers=1','--retries=0','--global-timeout=600000']
p=subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
(evidence/'runner.json').write_text(json.dumps({'run_id':os.environ.get('W02_RUN_ID','w02-review-replay'),'pid':p.pid,'pgid':p.pid,'command':cmd,'db':None,'containers':[]},indent=2))
sel=selectors.DefaultSelector();sel.register(p.stdout,selectors.EVENT_READ);start=last=time.monotonic(); reason=None
with (evidence/'browser.log').open('wb') as log:
 try:
  while p.poll() is None:
   for key,_ in sel.select(1):
    b=os.read(key.fd,65536)
    if b: log.write(b);log.flush();print(b.decode(errors='replace'),end='',flush=True);last=time.monotonic()
   if time.monotonic()-start>600 or time.monotonic()-last>90:
    reason='deadline' if time.monotonic()-start>600 else 'no-progress';break
 finally:
  try: os.killpg(p.pid,signal.SIGTERM)
  except ProcessLookupError: pass
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
  rest=p.stdout.read();log.write(rest);print(rest.decode(errors='replace'),end='')
  try:os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  try:os.killpg(p.pid,0);absent=False
  except ProcessLookupError:absent=True
  (evidence/'runner-result.json').write_text(json.dumps({'exit_code':p.returncode,'reason':reason,'elapsed_seconds':round(time.monotonic()-start,2),'owned_group_absent':absent},indent=2))
raise SystemExit(p.returncode if not reason else 124)
