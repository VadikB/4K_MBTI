"""Bounded offline release checks; progress changes only with actual output."""
import json,os,sys,threading
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from scripts.owned_process import run_bounded
mode=sys.argv[1]
commands={
 'frontend':(['node','--test',*map(str,sorted(Path('tests/frontend').glob('*.test.mjs')))],120,30),
 'unit':(['.venv/bin/python','-m','pytest','-q','-m','not integration and not e2e and not llm'],600,90),
 'http':(['.venv/bin/python','-m','pytest','-q','-m','e2e','tests/e2e'],300,90),
}
command,whole,idle=commands[mode]
stage=sys.argv[2] if len(sys.argv)>2 else 'release'
assert stage in {'release','release214'}
folder=Path('docs/evc/tasks/p4k-postw02-01/evidence')/stage;folder.mkdir(exist_ok=True)
log_path=folder/f'{mode}.log';progress=folder/f'{mode}-progress.json';stopped=threading.Event()
def watch_output():
 previous=-1
 while not stopped.wait(.2):
  size=log_path.stat().st_size if log_path.exists() else 0
  if size!=previous:
   progress.write_text(json.dumps({'progress_key':size})+'\n');previous=size
watcher=threading.Thread(target=watch_output);watcher.start()
env={k:os.environ[k] for k in ['PATH','HOME','TMPDIR','LANG','LC_ALL'] if k in os.environ}
env.update(PYTHON_DOTENV_DISABLED='1',DB_POOL_MIN_SIZE='0',PYTHONPATH=str(Path.cwd()),PYTHONUNBUFFERED='1',DEEPSEEK_API_KEYS='',DEEPSEEK_API_KEY='',TEST_DATABASE_URL='',STAND_ADMIN_URL='')
try:
 with log_path.open('w') as log:
  result=run_bounded(command,registry=f'.test-stand/postw02-release-{mode}-owner.json',deadline_seconds=whole,no_progress_seconds=idle,progress_file=progress,env=env,stdout=log,stderr=log)
finally:
 stopped.set();watcher.join()
(folder/f'{mode}-result.json').write_text(json.dumps({'command':command,**result},indent=2)+'\n')
print(json.dumps(result));print(log_path.read_text()[-6000:]);sys.exit(result['returncode'])
