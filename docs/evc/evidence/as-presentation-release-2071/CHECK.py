"""Offline evidence/continuity check. No Git refs, credentials, DB or provider."""
import hashlib
import gzip
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def value(path):
    return json.loads(path.read_bytes())


def xml(path):
    return ET.parse(gzip.open(str(path) + '.gz', 'rb') if not path.exists() else path)


def verify():
    manifest = value(HERE / 'manifest.json')
    for item in manifest['files']:
        path = HERE / item['path']
        assert not Path(item['path']).is_absolute() and '..' not in Path(item['path']).parts
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], item['path']
        if 'uncompressed_sha256' in item:
            assert hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest() == item['uncompressed_sha256']
    continuity = value(HERE / 'source-continuity.json')
    sources = value(HERE.parent / 'as-presentation-fix/source-identity.json')
    for item in continuity['files'] + sources['sources']:
        assert hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256'], item['path']
    for filename, count in {
        'as-presentation-release-2071-backend.xml': 937,
        'as-presentation-release-2071-http.xml': 108,
        'as-presentation-release-2071-targeted.xml': 50,
        'as-presentation-release-2071-browser.xml': 4,
        'frontend.xml': 145,
    }.items():
        tests = list(xml(HERE / 'primary' / filename).iter('testcase'))
        assert len(tests) == count, filename
        assert all(t.find('failure') is None and t.find('error') is None and t.find('skipped') is None for t in tests), filename
    old = list(xml(HERE / 'primary/as-presentation-before.xml').iter('testcase'))
    assert len(old) == 11 and sum(t.find('failure') is not None for t in old) == 9
    old = list(xml(HERE / 'primary/as-presentation-browser-suite.xml').iter('testcase'))
    assert len(old) == 120 and sum(t.find('failure') is not None for t in old) == 1
    legacy = {'initial_situation', 'trigger', 'assessee_position', 'participants_and_positions',
              'assessee_task', 'conditions_and_constraints'}
    records = list((HERE / 'primary/source-postgresql').glob('*.json'))
    assert len(records) == 5
    for path in records:
        item = value(path)
        assert item['scope'] == 'SYNTHETIC_PROVIDER_AND_UPSTREAM_ADMISSION_REAL_POSTGRESQL_HTTP'
        assert item['persisted_public'] == item['http_public']
        assert not legacy & item['http_public'].keys()
        assert item['candidate_checksum'] == item['accepted_as_checksum']
        assert item['assignment_count'] == 1 and item['http_status'] == 200
        assert item['assessment_answers_at_readback'] == 0
    for suffix in ('01', '02'):
        case = HERE / 'primary/browser' / ('CASE.SPEC.' + suffix)
        readback = value(case / 'readback.json')
        assert readback['scope'] == 'SYNTHETIC_COMPONENT_PRESENTATION_NOT_PILOT_ADMISSION'
        assert readback['assessment_answers'] == 0 and not readback['mutation_requests']
        assert not legacy & readback['participant_payload'].keys()
        rows = value(case / 'first-as-viewports.json')
        assert [r['width'] for r in rows] == [1440, 320, 390, 768]
        for row in rows:
            assert row['document']['scrollWidth'] <= row['width'] + 1
            for control in row['controls']:
                assert control['geometry']['visible_ratio'] > 0
        last = value(case / 'last-material-geometry.json')
        assert last['visible_ratio'] > 0 and last['screenshot_mode'] == 'viewport'
    release = value(HERE / 'release-idempotence.json')
    assert release['candidate'] == '2.0.71' and release['identical_files'] == 49
    for filename, checksum in release['sha256'].items():
        assert hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == checksum, filename
    cleanup = value(HERE.parent / 'as-presentation-fix/cleanup.json')
    assert cleanup['evidence_copied_before_removal'] and not cleanup['permanent_database_accessed']
    print(json.dumps({'status': 'PASS', 'evidence_files': len(manifest['files']),
        'source_hashes': len(continuity['files']) + len(sources['sources']),
        'postgresql_readbacks': 5, 'public_viewports': 8, 'real_llm_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    verify()
