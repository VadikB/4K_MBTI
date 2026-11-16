import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from scripts.owned_process import run_bounded
reference=Path(sys.argv[1]).resolve()
assert (reference/'dist/report-cabinet.css').exists()
phase=os.environ.get('POSTW02_AUDIT_PHASE', '')
assert phase in {'', 'probes', 'report'}
evidence=Path('docs/evc/tasks/p4k-postw02-01/evidence') / ('audit-v10' + ('-'+phase if phase else ''))
evidence.mkdir(parents=True,exist_ok=True)
progress=evidence/'progress.json'
env={**os.environ,'POSTW02_REFERENCE':str(reference),'POSTW02_EVIDENCE':str(evidence.resolve()),'POSTW02_PROGRESS':str(progress.resolve())}
with (evidence/'browser.log').open('w') as log:
    result=run_bounded(['node_modules/.bin/playwright','test','tests/browser/postw02-reference-audit.spec.mjs',*sys.argv[2:]],registry='.test-stand/postw02-audit-v10-owner.json',deadline_seconds=180,no_progress_seconds=60,progress_file=progress,env=env,stdout=log,stderr=log)
(evidence/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));print((evidence/'browser.log').read_text()[-7000:])
sys.exit(result['returncode'])
