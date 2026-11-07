"""Offline release-source and free-test check. Never DB/provider/deploy."""
from pathlib import Path
import hashlib
import json
import runpy
import xml.etree.ElementTree as ET

assert __debug__, 'Assertions required; do not use -O'
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
runpy.run_path(str(HERE/'BUILD_APPLICABILITY.py'),run_name='__main__')
record=json.loads((HERE/'build-applicability.json').read_bytes())
for name,expected in record['source_hashes'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
for name,expected in record['after_dist_hashes'].items():
    assert hashlib.sha256((ROOT/'web/dist'/name).read_bytes()).hexdigest()==expected,name
counts={}
for name,expected in (('frontend.xml',146),('receipt.xml',66),('targeted.xml',24)):
    suite=ET.parse(HERE/name).getroot()
    assert not suite.findall('.//failure') and not suite.findall('.//error'),name
    cases=suite.findall('.//testcase')
    assert len(cases)==expected and not suite.findall('.//skipped'),name
    counts[name]=len(cases)
browser=json.loads((HERE/'browser-results.json').read_bytes())
assert browser['stats']['expected']==9
assert browser['stats']['unexpected']==browser['stats']['flaky']==browser['stats']['skipped']==0
assert json.loads((HERE/'browser-command-result.json').read_bytes())['exit_code']==0
decision=json.loads((HERE/'owner-version-decision.json').read_bytes())
assert decision['candidate']=='2.0.75' and decision['version_bump'] is True
assert decision['merge'] is False and decision['deploy'] is False and decision['paid_path'] is False
print(json.dumps({'result':'PASS_LOCAL_RELEASE_EVIDENCE','source_hashes':len(record['source_hashes']),
    'build_hashes':len(record['after_dist_hashes']),'junit':counts,'browser':9,
    'mandatory_ci':'SEPARATE','deployed_ac18_pass':False,'new_provider_or_database_calls':0}))
