import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from scripts.owned_process import run_bounded
mode=sys.argv[1]
evidence=Path('docs/evc/tasks/p4k-postw02-01/evidence') / mode
evidence.mkdir(parents=True,exist_ok=True)
progress=evidence/'progress.json'
env={**os.environ,'POSTW02_EVIDENCE':str(evidence.resolve()),'POSTW02_PROGRESS':str(progress.resolve()),'POSTW02_BEFORE':'1' if mode=='before' else '0'}
with (evidence/'browser.log').open('w') as log:
    result=run_bounded(['node_modules/.bin/playwright','test','tests/browser/postw02-cabinet.spec.mjs',*sys.argv[2:]],registry=f'.test-stand/postw02-{mode}-owner.json',deadline_seconds=180,no_progress_seconds=60,progress_file=progress,env=env,stdout=log,stderr=log)
(evidence/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));print((evidence/'browser.log').read_text()[-7000:])
sys.exit(result['returncode'])
