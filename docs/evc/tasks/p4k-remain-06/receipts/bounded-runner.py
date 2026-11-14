import argparse,json,os,signal,subprocess,sys,time
p=argparse.ArgumentParser();p.add_argument('--seconds',type=float,default=180);p.add_argument('--idle',type=float,default=60);p.add_argument('--log',required=True);p.add_argument('cmd',nargs=argparse.REMAINDER);a=p.parse_args()
cmd=a.cmd[1:] if a.cmd[:1]==['--'] else a.cmd
started=time.monotonic();progress=started;size=0;child=None;reason='completed';code=1

def cleanup():
 if child is None:return
 try:os.killpg(child.pid,signal.SIGTERM)
 except ProcessLookupError:return
 try:child.wait(timeout=15)
 except subprocess.TimeoutExpired:
  os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)

def stopped(signum,frame):
 raise InterruptedError('bounded runner interrupted')

for s in [signal.SIGINT,signal.SIGTERM]:signal.signal(s,stopped)
try:
 with open(a.log,'wb') as log:
  child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  print(json.dumps({'pid':child.pid,'pgid':child.pid,'deadline_seconds':a.seconds,'no_progress_seconds':a.idle}),flush=True)
  while child.poll() is None:
   now=time.monotonic();new=os.fstat(log.fileno()).st_size
   if new!=size:progress=now;size=new
   if now-started>a.seconds:reason='deadline';code=124;break
   if now-progress>a.idle:reason='no_progress';code=125;break
   if size>10*1024*1024:reason='log_limit';code=126;break
   time.sleep(.1)
  else:code=child.returncode
except BaseException:
 reason='exception';code=130;raise
finally:
 cleanup()
 print(json.dumps({'result':reason,'exit_code':code,'elapsed_seconds':round(time.monotonic()-started,2),'child_exited':child is None or child.poll() is not None}),flush=True)
sys.exit(code)
