"""Run the documented entrypoint against independently empty databases."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/'scripts/test_stand.py'


def check(directory,port,keep=False):
    directory.mkdir(parents=True,exist_ok=True);state=directory/'state.json'
    def run(action):
        with (directory/(action+'.log')).open('a') as log:
            subprocess.run([sys.executable,str(CLI),action,'--state',str(state),'--port',str(port),'--gateway','1'],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=150)
    run('create')
    process=None;log=None
    try:
        run('bootstrap')
        value=json.loads(state.read_text());value.update(qa_orchestration=True,browser_scenario='acceptance-v1');state.write_text(json.dumps(value))
        run('seed')
        for iteration in range(2):
            log=(directory/'app.log').open('a')
            process=subprocess.Popen([sys.executable,str(CLI),'serve','--state',str(state)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            deadline=time.monotonic()+45
            while True:
                if process.poll() is not None:raise RuntimeError('main:app exited; inspect app.log')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/health/ready',timeout=2) as response:
                        assert json.load(response)['status']=='ready';break
                except OSError:
                    if time.monotonic()>deadline:raise RuntimeError('startup deadline')
                    time.sleep(.25)
            run('smoke')
            process.terminate();process.wait(timeout=20);process=None;log.close();log=None
            run('bootstrap');run('seed')
        print('PASS clean bootstrap, owner Report/PDF, repeat bootstrap/seed/restart:',directory)
    finally:
        if process is not None:
            process.terminate();process.wait(timeout=20)
        if log:log.close()
        if not keep:run('destroy')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--port',type=int,default=18520);p.add_argument('--keep',action='store_true')
    a=p.parse_args();check(a.directory.resolve(),a.port,a.keep)
