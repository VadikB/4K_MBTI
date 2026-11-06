"""Offline primary-evidence checks; never connects to a DB or provider."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads((ROOT / path).read_text())


def main():
    index = read('evidence-index.json')
    checks = read(index['http_pg'] + '/checks.json')
    assert checks['real_sessions'] and checks['real_resolvers'] and checks['real_postgresql']
    assert checks['synthetic_only'] and checks['external_credentials_absent']
    assert all(n == 0 for n in checks['runtime_activity'].values())
    assert len(checks['events']) == 31
    denials = [e for e in checks['events'] if 'expected_status' in e]
    assert len(denials) == 25
    for event in denials:
        assert event['status'] == event['expected_status']
        assert event['before'] == event['after'] and event['unchanged']
        assert len(event['before']) >= 20
    positive = [e for e in checks['events'] if e.get('criterion') == 'AC07']
    assert len(positive) == 1 and positive[0]['positive_and_replay'] == 'PASS'
    assert len({positive[0][key] for key in ('exact_revision', 'stale_revision', 'foreign_revision')}) == 3
    repeats = [e for e in checks['events'] if 'mode' in e]
    assert {e['mode'] for e in repeats} == {'lost_reply', 'same_key_concurrent', 'different_key_concurrent'}
    for event in repeats:
        assert event['before'] == event['after']
        assert len(event['after']['assignments']) == len(event['after']['bindings']) == 1
        assert event['after']['cycles'] == 0
    fault = [e for e in checks['events'] if 'late_postgresql_fault_after_first_binding' in e]
    assert fault[0]['late_postgresql_fault_after_first_binding'] == {'last_value': 1, 'is_called': True}
    for directory in (index['http_pg'], index['admin_browser'], index['component']):
        cleanup = read(directory + '/cleanup.json')
        assert cleanup['owner_verified'] and cleanup['database_absent'] and cleanup['state_absent']
        assert cleanup.get('force') is False
        assert not (ROOT / directory / 'state.json').exists()
    admin = read(index['admin_browser'] + '/events.json')
    assert [e['phase'] for e in admin] == ['double_click', 'committed_response_aborted', 'reload_repeat_readback']
    assert admin[0]['actual_post_requests'] == 1
    assert len(admin[0]['sql']['assignments']) == len(admin[0]['sql']['bindings']) == 1
    assert admin[1]['real_response']['status'] == 200
    assert len(admin[1]['sql']['assignments']) == len(admin[1]['sql']['bindings']) == 2
    assert admin[1]['sql'] == admin[2]['sql'] and admin[2]['sql']['cycles'] == 0
    for directory, phase in [(index['admin_browser'], 'superadmin-program'),
        *[(index['component'], phase) for phase in ('admin-questionnaire', 'admin-assignment', 'participant-ready', 'first-as')]]:
        frames = read(directory + '/' + phase + '-viewports.json')
        assert [frame['width'] for frame in frames] == [1440, 320, 390, 768]
        for frame in frames:
            assert 'error' not in frame and frame['document']['visibility'] == 'visible'
            assert frame['document']['scrollWidth'] <= frame['width'] + 1
            assert (ROOT / directory / frame['screenshot']).is_file()
            for control in frame['controls']:
                assert control['box']['x'] >= -1
                assert control['box']['x'] + control['box']['width'] <= frame['width'] + 1
    replay = read(index['component'] + '/post-start-assignment-replay.json')
    assert replay['status'] == 200 and replay['result']['items'][0]['status'] == 'already_assigned'
    assert replay['participant_state'] == {'profiles': 1, 'cycles': 1, 'started': 1, 'operations': 1}
    assert read(index['component'] + '/component-boundary.json')['product_admission_evidence'] is False
    for log, expected in [('backend.xml', 921), ('http.xml', 108), ('integration.xml', 240)]:
        suite = ET.parse(ROOT / log).getroot().find('testsuite')
        assert int(suite.attrib['tests']) == expected
        assert all(int(suite.attrib[k]) == 0 for k in ('failures', 'errors', 'skipped'))
    browser = read('browser-results.json')
    assert browser['stats']['expected'] == 2
    assert all(browser['stats'][k] == 0 for k in ('unexpected', 'flaky', 'skipped'))
    cleanup = read('container-cleanup.json')
    assert cleanup['owned_database_count'] == cleanup['owned_connection_count'] == 0
    assert cleanup['container_removed'] and cleanup['owner_label_verified']
    print('PASS: 31 HTTP/PG events, 25 no-write denials, real races/fault rollback, browser+20 viewport frames, cleanup')


if __name__ == '__main__':
    main()
