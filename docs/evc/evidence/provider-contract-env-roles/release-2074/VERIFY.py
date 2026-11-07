"""Offline candidate integrity. No app imports, env, network, PostgreSQL or LLM."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def main():
    record = json.loads((HERE / 'result.json').read_bytes())
    assert record['candidate'] == '2.0.74'
    assert record['ready_preparation']['identical_49_hashes'] is True
    assert len(record['release_file_hashes']) == 49
    for collection in ('release_file_hashes', 'junit_file_hashes'):
        for relative, expected in record[collection].items():
            target = (ROOT / relative).resolve()
            assert target.is_relative_to(ROOT) and target.is_file()
            assert hashlib.sha256(target.read_bytes()).hexdigest() == expected, relative
    for name, expected in record['junit_counts'].items():
        cases = list(ET.parse(HERE / name).getroot().iter('testcase'))
        assert len(cases) == expected['tests'] > 0
        for key, tag in (('failures', 'failure'), ('errors', 'error'), ('skipped', 'skipped')):
            assert sum(case.find(tag) is not None for case in cases) == expected[key] == 0
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    assert version == record['candidate']
    assert not any(record['safety'].values())
    subprocess.run([sys.executable, str(HERE.parent / 'CHECK.py')], check=True)
    print('PASS: candidate2.0.74; 49 release hashes, 3 JUnit hashes, 145/66/116 cases; not CI/deploy/AC18')


if __name__ == '__main__':
    main()
