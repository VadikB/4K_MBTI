"""Two existing synthetic runtime cases on a disposable owned PostgreSQL16."""
import errno,json,os,shutil,socket,subprocess,sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from scripts.owned_process import run_bounded
root=Path.cwd();bin_dir=Path('/opt/homebrew/opt/postgresql@16/bin')
mode=sys.argv[1] if len(sys.argv)>1 else 'ci-legacy'
assert mode in {'ci-legacy','ci-legacy-final','ci-legacy-confirmed'}
folder=root/'docs/evc/tasks/p4k-postw02-01/evidence'/mode;folder.mkdir(exist_ok=True)
with socket.socket() as sock:
 sock.settimeout(1);assert sock.connect_ex(('127.0.0.1',18830))==errno.ECONNREFUSED,'APP_PORT_NOT_FREE'
with socket.socket() as sock:
 sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
cluster=Path(tempfile.mkdtemp(prefix='postw02-pg-',dir='/private/tmp'));data=cluster/'data'
(cluster/'owner.json').write_text(json.dumps({'task':'POSTW02-01','data':str(data),'port':port})+'\n')
env={k:os.environ[k] for k in ['PATH','HOME','TMPDIR','LANG','LC_ALL'] if k in os.environ}
env.update(PYTHON_DOTENV_DISABLED='1',DB_POOL_MIN_SIZE='0',PYTHONPATH=str(root),PYTHONUNBUFFERED='1',DEEPSEEK_API_KEYS='',DEEPSEEK_API_KEY='',STAND_ADMIN_URL=f'postgresql://pytest@127.0.0.1:{port}/postgres',BROWSER_PYTHON=str(root/'.venv/bin/python'))
started=False;result={'returncode':1};stop=threading.Event();watcher=None
log_path=folder/'runtime.log';progress=folder/'progress.json'
def watch_output():
 previous=-1
 while not stop.wait(.2):
  size=log_path.stat().st_size if log_path.exists() else 0
  if size!=previous:progress.write_text(json.dumps({'progress_key':size})+'\n');previous=size
try:
 with (folder/'postgres-setup.log').open('w') as log:
  subprocess.run([str(bin_dir/'initdb'),'-D',str(data),'-U','pytest','-A','trust','--no-locale','--encoding=UTF8'],check=True,env=env,stdout=log,stderr=log,timeout=30)
  subprocess.run([str(bin_dir/'pg_ctl'),'-D',str(data),'-l',str(cluster/'postgres.log'),'-o',f'-h 127.0.0.1 -p {port} -k {cluster}','-w','start'],check=True,env=env,stdout=log,stderr=log,timeout=30);started=True
 watcher=threading.Thread(target=watch_output);watcher.start()
 with log_path.open('w') as log:
  result=run_bounded(['node_modules/.bin/playwright','test','tests/browser/runtime.spec.mjs','--grep','Recovery: lost response|P10.5 ready profile with no admitted catalog','--workers=1'],registry='.test-stand/postw02-legacy-repro-owner.json',deadline_seconds=240,no_progress_seconds=90,progress_file=progress,env=env,stdout=log,stderr=log)
finally:
 stop.set()
 if watcher:watcher.join()
 if started:
  marker=json.loads((cluster/'owner.json').read_text());assert marker['data']==str(data) and marker['task']=='POSTW02-01'
  with (folder/'postgres-stop.log').open('w') as log:subprocess.run([str(bin_dir/'pg_ctl'),'-D',str(data),'-m','immediate','-w','stop'],check=True,env=env,stdout=log,stderr=log,timeout=20)
 closed={}
 for name,target in [('postgres',port),('app',18830)]:
  with socket.socket() as sock:sock.settimeout(1);closed[name]=sock.connect_ex(('127.0.0.1',target))
 assert all(code==errno.ECONNREFUSED for code in closed.values()),closed
 assert not Path('.test-stand/postw02-legacy-repro-owner.json').exists()
 shutil.rmtree(cluster)
 (folder/'cleanup.json').write_text(json.dumps({'owned_cluster_removed':True,'closed_port_errno':closed,'registry_absent':True,'real_llm':0,'mail':0},indent=2)+'\n')
(folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));print(log_path.read_text()[-7000:]);sys.exit(result['returncode'])
