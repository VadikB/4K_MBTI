"""Offline file/JUnit integrity; no app imports, dotenv, network or database."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    record = json.loads((HERE / 'result.json').read_bytes())
    assert record['result'] == 'PASS_LOCAL_NOT_RELEASED'
    for relative, expected in record['source_hashes'].items():
        target = (ROOT / relative).resolve()
        assert target.is_relative_to(ROOT) and target.is_file()
        assert hashlib.sha256(target.read_bytes()).hexdigest() == expected, relative
    suites = [check for check in record['checks'] if 'file' in check]
    for check in suites:
        if 'member' in check:
            with ZipFile(HERE / check['file']) as archive:
                assert archive.namelist() == [check['member']]
                data = archive.read(check['member'])
            assert hashlib.sha256(data).hexdigest() == check['uncompressed_sha256']
            suite = ET.fromstring(data).find('testsuite')
        else:
            suite = ET.parse(HERE / check['file']).getroot().find('testsuite')
        assert suite is not None
        for key in ('tests', 'failures', 'errors', 'skipped'):
            assert int(suite.get(key)) == check[key], (check['id'], key)
    assert record['offline_model_readback']['provider_calls'] == 0
    assert not any(record['safety'].values())
    print(f"PASS: {len(record['source_hashes'])} file hashes, {len(suites)} JUnit records; LOCAL ONLY, not AC18")


if __name__ == '__main__':
    main()
