"""Offline current-source continuity; prior immutable evidence is not rewritten."""
import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PRIOR = HERE.parent / 'path-harness-release-2070'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest = json.loads((HERE / 'manifest.json').read_text())
for name, expected in manifest['files'].items():
    target = (HERE / name).resolve()
    assert target.is_relative_to(HERE) and sha(target) == expected, name
identity = json.loads((PRIOR / 'source-identity.json').read_text())
unit = 'tests/unit/test_assessment_first_case.py'
for name, expected in identity['source_files'].items():
    if name == unit:
        expected = '2dc58966e1e7f92a1d51ba45f43cf6e4a6eb6cc9523ef18a81a1bae0db090a55'
    assert sha(REPO / name) == expected, name
prior_manifest = json.loads((PRIOR / 'manifest.json').read_text())
for name, expected in prior_manifest['files'].items():
    assert sha(PRIOR / name) == expected, name
for name, count in [('targeted.xml', 35), ('shallow-after.xml', 2),
                    ('verified-on-db790.xml', 35), ('backend.xml', 922), ('http.xml', 108)]:
    root = ET.parse(HERE / name).getroot()
    assert len(root.findall('.//testcase')) == count
    assert not root.findall('.//failure') and not root.findall('.//error') and not root.findall('.//skipped')
before = ET.fromstring(gzip.decompress((HERE / 'shallow-before.xml.gz').read_bytes()))
assert len(before.findall('.//failure')) == 1
assert 'origin/main' in gzip.decompress((HERE / '1cd972f-pytest-log.txt.gz').read_bytes()).decode()
print('PASS: current355 source hashes (one explicit unit delta), immutable134 evidence; backend922/HTTP108/targeted35/shallow2; negative retained')
