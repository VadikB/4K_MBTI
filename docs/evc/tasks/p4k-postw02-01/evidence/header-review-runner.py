import json, os, sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from scripts.owned_process import run_bounded
mode=sys.argv[1] if len(sys.argv)>1 else 'header-review'
assert mode in {'header-review','header-review-refine','release-header'}
evidence=Path('docs/evc/tasks/p4k-postw02-01/evidence')/mode
evidence.mkdir(parents=True,exist_ok=True);progress=evidence/'progress.json'
env={**os.environ,'POSTW02_EVIDENCE':str(evidence.resolve()),'POSTW02_PROGRESS':str(progress.resolve()),'POSTW02_REFERENCE':str(Path('../outputs/p4k-postw02-01-20261116/reference-v10/.sites-checkout').resolve())}
with (evidence/'browser.log').open('w') as log:
 result=run_bounded(['node_modules/.bin/playwright','test','tests/browser/postw02-header-review.spec.mjs',*sys.argv[2:]],registry=f'.test-stand/{mode}-owner.json',deadline_seconds=180,no_progress_seconds=60,progress_file=progress,env=env,stdout=log,stderr=log)
(evidence/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));print((evidence/'browser.log').read_text()[-9000:]);sys.exit(result['returncode'])
