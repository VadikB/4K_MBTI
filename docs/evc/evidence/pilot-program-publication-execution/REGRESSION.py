"""Положительный evidence и испорченные копии; публикация/сеть не запускаются."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

directory = Path(__file__).parent
spec = importlib.util.spec_from_file_location('published_evidence_check', directory / 'CHECK.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
positive = checker.check(directory)
mutations = [
    ('empty_receipt', 'published-release-source.json', lambda v: {}),
    ('wrong_program_id', 'published-release-source.json', lambda v: {**v, 'program': {**v['program'], 'id': 99}}),
    ('unexpected_activation', 'publication-result.json', lambda v: {**v, 'new_program_org_connections': 1}),
    ('wrong_publisher_scope', 'prepublication.json', lambda v: {**v, 'publisher': {**v['publisher'], 'not_suppressed': False}}),
    ('failed_test', 'retirement-regression.json', lambda v: {**v, 'exit_code': 1}),
    ('unowned_cleanup', 'cleanup.json', lambda v: {**v, 'owner_verified': False}),
    ('repeated_publisher', 'publisher-invocation.json', lambda v: {**v, 'invocations': 2}),
    ('no_owner_approval', 'owner-decision.json', lambda v: {**v, 'decision': 'PENDING'}),
]
rejected = []
for name, filename, mutate in mutations:
    with tempfile.TemporaryDirectory(prefix='pilotpub-evidence-negative-') as temporary:
        target = Path(temporary)
        for path in directory.iterdir():
            if path.is_file():
                shutil.copy2(path, target / path.name)
        value = json.loads((target / filename).read_bytes())
        (target / filename).write_text(json.dumps(mutate(deepcopy(value)), ensure_ascii=False) + '\n')
        # Обновление транспортного digest не должно скрыть смысловой дефект.
        remote = json.loads((target / 'remote-execution.json').read_bytes())
        for item in remote['stdout']['files']:
            if item['name'] == filename:
                item.update(bytes=(target / filename).stat().st_size, sha256=checker.sha(target / filename))
        (target / 'remote-execution.json').write_text(json.dumps(remote, ensure_ascii=False) + '\n')
        try:
            checker.check(target)
        except (AssertionError, ValueError, KeyError, TypeError):
            rejected.append(name)
        else:
            raise AssertionError('TAMPER_NOT_REJECTED:' + name)
optimized = subprocess.run([sys.executable, '-O', str(directory / 'CHECK.py')], capture_output=True, text=True)
assert optimized.returncode != 0 and 'PUBLICATION_EVIDENCE_REQUIRES_ASSERTIONS' in optimized.stderr
assert len(rejected) == len(mutations)
print(json.dumps({'result': 'PASS_PUBLICATION_EVIDENCE_REGRESSION', 'positive': positive,
    'tamper_cases_rejected': rejected, 'optimized_assertions_disabled_rejected': True,
    'database_connections': 0, 'provider_calls': 0}, ensure_ascii=False))
