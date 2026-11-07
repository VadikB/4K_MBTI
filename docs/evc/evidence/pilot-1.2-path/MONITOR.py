"""Safe read-only progress: owned harness GET and allowlisted log metadata."""
import json
from pathlib import Path
import re
from urllib.request import urlopen

directory = Path('/home/vadim_bogachev/evidence/path-pilot-1.2-run-qxzr56r9')
result = {'scope': 'READ_ONLY_OWNED_PATH_MONITOR', 'runs': []}
if (directory / 'controller-result.json').exists():
    result['controller'] = json.loads((directory / 'controller-result.json').read_bytes())
for path in sorted((directory / 'run').glob('*/run.json')):
    run = json.loads(path.read_bytes()); root = path.parent
    row = {'run_id': run['run_id'], 'database': run['database'],
        'completion_present': (root / 'completion.json').exists(),
        'cleanup_present': (root / 'cleanup.json').exists(),
        'cleanup_deferred': (root / 'cleanup-deferred.json').exists(),
        'failure_present': (root / 'failure.json').exists(), 'state_present': (root / 'state.json').exists()}
    completed = []
    if (root / 'server.log').exists():
        with (root / 'server.log').open() as stream:
            for line in stream:
                match = re.search(r'DeepSeek request completed duration_ms=([0-9.]+)[^\n]*routing_key=([a-f0-9-]{36}:[a-zA-Z0-9:_-]+)', line)
                if match:
                    completed.append({'duration_ms': float(match[1]), 'routing_key': match[2]})
    row['provider_completed_requests'] = len(completed)
    row['last_provider_completions'] = completed[-3:]
    if row['state_present'] and not row['completion_present']:
        try:
            with urlopen('http://127.0.0.1:18861/__pytest__/path-receipt', timeout=5) as response:
                receipt = json.load(response)
            program = receipt['program_definition']
            if (program['id'], program['version']) != (2, '1.2'):
                raise RuntimeError('WRONG_OWNED_HARNESS_PROGRAM')
            row['operation'] = receipt.get('preparation_operation')
            if row['operation']:
                row['operation'] = {key: row['operation'].get(key) for key in ('operation_id', 'status', 'attempts', 'error_code')}
            row['cycle'] = {key: (receipt.get('cycle') or {}).get(key) for key in ('id', 'status', 'started_at')}
            row['assessment_answers'] = receipt.get('assessment_answers')
            row['start_readiness'] = {key: (receipt.get('start_readiness') or {}).get(key) for key in ('can_start', 'reasons')}
        except (OSError, ValueError):
            row['phase'] = 'HTTP_NOT_READY_OR_ALREADY_STOPPED'
    result['runs'].append(row)
print(json.dumps(result))
