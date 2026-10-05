"""Read-only hashes for G10.7; never reads environment secrets or database rows."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def manifest():
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    paths=set(p for p in tracked if p and (p.startswith(('Api/','web/','assessment_definitions/','tests/','scripts/'))
        or p in ('main.py','package.json','package-lock.json','pyproject.toml','.github/workflows/backend-tests.yml')))
    # Include new intended tests/scripts while preparing a candidate, exclude caches.
    paths.update(str(p.relative_to(ROOT)) for folder in ('tests/fixtures/integrated_acceptance',) for p in (ROOT/folder).rglob('*') if p.is_file())
    paths.update(('tests/integration/test_integrated_acceptance_db.py','scripts/integrated_acceptance_manifest.py'))
    files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(paths) if (ROOT/p).is_file()}
    return {'schema_version':1,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'runtime_tree_sha256':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),
        'missing_tracked_files_excluded':[p for p in sorted(paths) if not (ROOT/p).is_file()],
        'files':files,'environment':{'python':platform.python_version(),'platform':platform.platform(),
            'node':subprocess.check_output(['node','--version'],cwd=ROOT,text=True).strip(),
            'python_packages':{name:importlib.metadata.version(name) for name in ('typst','psycopg','fastapi','pydantic','pytest')},
            'playwright':json.loads((ROOT/'node_modules/@playwright/test/package.json').read_text())['version']},
        'ai_modes':{'M5_semantic_and_character':'owned synthetic acceptance-v1 gateway',
            'M6_evidence_and_indicator_assessment':'owned synthetic acceptance-v1 gateway',
            'M6_substantive_admission':'real producer/resolver, scripted AI transport admission-v2.json',
            'M7_clarification':'owned synthetic acceptance-v1 gateway',
            'M7_planning_completion':'deterministic runtime','M8_recommendations':'deterministic versioned rules',
            'real_provider':'NOT_RUN; no authorized provider/cost limit'}}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.write_text(json.dumps(manifest(),ensure_ascii=False,indent=2)+'\n')
