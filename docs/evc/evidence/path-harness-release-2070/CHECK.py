"""Offline release evidence checks. No DB, provider or network access."""
import hashlib
import json
from pathlib import Path
import runpy
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]


def read(name):
    return json.loads((ROOT / name).read_text())


def main():
    manifest = read('manifest.json')
    for name, expected in manifest['files'].items():
        target = (ROOT / name).resolve()
        assert target.is_relative_to(ROOT)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == expected, name
    identity = read('source-identity.json')
    assert identity['source_sha'] == '4510aa4b7ac3db87f44cd422862a549d8c72c9a7'
    for name, expected in identity['source_files'].items():
        assert hashlib.sha256((REPO / name).read_bytes()).hexdigest() == expected, name
    for name, expected in [('backend', 921), ('http', 108), ('release-ci', 22),
                           ('verified-targeted', 34), ('http-pg', 1), ('frontend', 145)]:
        root = ET.parse(ROOT / (name + '.xml')).getroot()
        assert len(root.findall('.//testcase')) == expected, name
        assert not root.findall('.//failure') and not root.findall('.//error'), name
        assert not root.findall('.//skipped'), name
    checks = read('http-pg/checks.json')
    assert len(checks['events']) == 31 and checks['real_postgresql']
    assert checks['real_sessions'] and checks['real_resolvers']
    assert checks['external_credentials_absent'] and checks['synthetic_only']
    assert all(v == 0 for v in checks['runtime_activity'].values())
    denials = [e for e in checks['events'] if 'expected_status' in e]
    assert len(denials) == 25
    assert all(e['unchanged'] and e['before'] == e['after'] and
               e['status'] == e['expected_status'] for e in denials)
    stats = read('browser-results.json')['stats']
    assert stats['expected'] == 5
    assert all(stats[k] == 0 for k in ('unexpected', 'flaky', 'skipped'))
    for directory, passed in [('negative-io', 1), ('negative-rerender', 3)]:
        negative = read(directory + '/browser-results.json')['stats']
        assert negative['unexpected'] == 1 and negative['expected'] == passed
    for directory in ['http-pg', 'browser-admin', 'browser-component',
                      'negative-io/admin', 'negative-io/component',
                      'negative-rerender/admin', 'negative-rerender/component']:
        cleanup = read(directory + '/cleanup.json')
        assert cleanup['owner_verified'] and cleanup['database_absent'] and cleanup['state_absent']
        assert cleanup['force'] is False and not (ROOT / directory / 'state.json').exists()
    for directory, phase in [('browser-admin', 'superadmin-program'),
        *[('browser-component', p) for p in ('admin-questionnaire', 'admin-assignment',
                                            'participant-ready', 'first-as')]]:
        frames = read(directory + '/' + phase + '-viewports.json')
        assert [r['width'] for r in frames] == [1440, 320, 390, 768]
        for frame in frames:
            assert 'error' not in frame and frame['document']['visibility'] == 'visible'
            assert frame['document']['scrollWidth'] <= frame['width'] + 1
            assert (ROOT / directory / frame['screenshot']).is_file()
            for control in frame['controls']:
                geometry = control['geometry']
                assert geometry['visible_ratio'] > 0 and geometry['visibility'] == 'visible'
                assert geometry['box']['x'] >= -1
                assert geometry['box']['x'] + geometry['box']['width'] <= frame['width'] + 1
    events = read('browser-admin/events.json')
    assert [e['phase'] for e in events] == ['double_click', 'committed_response_aborted', 'reload_repeat_readback']
    assert events[0]['actual_post_requests'] == 1
    assert events[1]['real_response']['status'] == 200
    assert events[1]['sql'] == events[2]['sql'] and events[2]['sql']['cycles'] == 0
    replay = read('browser-component/post-start-assignment-replay.json')
    assert replay['result']['items'][0]['status'] == 'already_assigned'
    assert replay['participant_state'] == {'profiles': 1, 'cycles': 1, 'started': 1, 'operations': 1}
    assert read('browser-component/component-boundary.json')['product_admission_evidence'] is False
    cleanup = read('container-cleanup.json')
    assert cleanup['container_removed'] and cleanup['owner_label_verified']
    assert cleanup['owned_database_count'] == cleanup['owned_connection_count'] == 0
    runpy.run_path(str(ROOT.parent / 'path-ac06-ac10-proof/CHECK.py'), run_name='__main__')
    print(f'PASS: {len(manifest["files"])} release files; source identity, 5 browser, negatives, HTTP/PG, cleanup')


if __name__ == '__main__':
    main()
