"""Compare release build to exact paid branch source; no DB/network/provider."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from collections import Counter

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BASE='38bf82448e63e55414ff55ac45fa126e9c4385f0'
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def digest(data): return hashlib.sha256(data).hexdigest()
def old(name): return git('show',BASE+':'+name)
assert __debug__
metadata=('pyproject.toml','uv.lock','web/js/config.js','web/index.html')
for name in metadata:
    actual=(ROOT/name).read_bytes()
    assert actual.replace(b'2.0.75',b'2.0.74')==old(name),name
changed=git('diff','--name-only',BASE,'--','Api','assessment_definitions','web/js','web/styles',
    'scripts','tests','package.json','package-lock.json').decode().splitlines()
assert changed==['web/js/config.js'],changed
before={Path(name).name:old(name) for name in git('ls-tree','-r','--name-only',BASE,'web/dist').decode().splitlines()}
after={file.name:file.read_bytes() for file in (ROOT/'web/dist').glob('*.js')}
assert len(before)==len(after)==45
ref=re.compile(rb'(?:/web/dist/|\./)([A-Za-z0-9_-]+-[A-Z0-9]{8}\.js)')
def normal(data):
    return ref.sub(lambda m:re.sub(rb'-[A-Z0-9]{8}(?=\.js$)',b'-HASH',m[0]),
        data.replace(b'2.0.74',b'APP_RELEASE').replace(b'2.0.75',b'APP_RELEASE'))
before_hash={name:digest(normal(data)) for name,data in before.items()}
after_hash={name:digest(normal(data)) for name,data in after.items()}
assert Counter(before_hash.values())==Counter(after_hash.values()),'NORMALIZED_CONTENT_CHANGED'
def graph(files,hashes):
    rows=[]
    for name,data in files.items():
        edges=[]
        for match in ref.finditer(data):
            target=match[1].decode()
            assert target in files,(name,target)
            edges.append(hashes[target])
        rows.append((hashes[name],tuple(sorted(edges))))
    return Counter(rows)
assert graph(before,before_hash)==graph(after,after_hash),'IMPORT_GRAPH_CHANGED'
identity=json.loads((HERE.parent/'ac18-branch38-path/remote/run-evidence/code-identity.json').read_bytes())
for name,expected in identity['files'].items():
    assert digest((ROOT/name).read_bytes())==expected,name
record={'result':'PASS_RELEASE_ONLY_DELTA','paid_path_sha':BASE,'release':'2.0.75',
    'unchanged_runtime_identity_files':len(identity['files']),'version_only_metadata':list(metadata),
    'dist_files_before':len(before),'dist_files_after':len(after),
    'normalization':'only release literal and generated hash in /web/dist or relative JS module refs',
    'normalized_content_multiset_equal':True,'import_graph_edges_bind_same_normalized_modules':True,
    'after_dist_hashes':{name:digest(data) for name,data in sorted(after.items())},
    'source_hashes':{name:digest((ROOT/name).read_bytes()) for name in
        (*identity['files'],'web/js/main.js','web/js/wiring.js',*metadata)},
    'new_provider_or_database_calls':0,'deployed_ac18_pass':False}
target=HERE/'build-applicability.json'
if target.exists():
    assert json.loads(target.read_bytes())==record,'RECORDED_BUILD_OR_SOURCE_CHANGED'
else:
    target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k not in ('after_dist_hashes','source_hashes')},ensure_ascii=False))
