"""Offline handoff probe; no DB, provider, .env, publication or PATH execution."""
from __future__ import annotations

import ast
import hashlib
import importlib.abc
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
BASE = '3385145201d5d365e08e9e8a6a6fb7e12a0aa258'


def require(value, code):
    if not value:
        raise AssertionError(code)


class NoInfrastructure(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname in ('Api.config', 'Api.database') or fullname.startswith('Api.llm'):
            raise AssertionError('OFFLINE_INFRASTRUCTURE_FORBIDDEN')


def main():
    sys.meta_path.insert(0, NoInfrastructure())
    sys.path.insert(0, str(ROOT))
    from tests.path_start_release_source import load_release_receipt, DEFAULT_RECEIPT
    from tests.path_start_release_inputs import reserve_release_ids
    from scripts.assessment_first_case import select_release

    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()

    require(not git('diff', BASE, '--', 'Api', 'assessment_definitions', 'web', 'pyproject.toml', 'uv.lock'),
            'PRODUCT_OR_SOURCE_DIFF_OUT_OF_SCOPE')
    source, ref = load_release_receipt()
    baseline_bytes = subprocess.check_output(['git', 'show', BASE + ':tests/browser/fixtures/path-start-release.json'], cwd=ROOT)
    require(DEFAULT_RECEIPT.read_bytes() == baseline_bytes, 'LEGACY_SOURCE_CHANGED')
    require(source['program']['version'] == '1.1', 'LEGACY_VERSION_CHANGED')
    require(select_release('published-pilot') == ref, 'RUNNER_SOURCE_PIN')
    try:
        select_release('published-pilot', version='1.2')
    except ValueError as error:
        require(str(error) == 'RELEASE_RECEIPT_COMPLETE_SELECTOR_REQUIRED', 'WRONG_SELECTOR_ERROR')
    else:
        raise AssertionError('PARTIAL_SELECTOR_ACCEPTED')

    code = git('show', BASE + ':tests/path_start_release_inputs.py')
    tree = ast.parse(code)
    definition = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'reserve_release_ids')
    namespace = {'os': os}
    exec(compile(ast.Module(body=[definition], type_ignores=[]), '<pinned-baseline-function>', 'exec'), namespace)

    class Connection:
        def __init__(self):
            self.statements = []
        def execute(self, statement, params=None):
            self.statements.append((statement, params))
            return self
        def fetchone(self):
            return {'name': 'product4k_pytest_offline_probe', 'n': 0}

    old = os.environ.get('AGENT4K_ISOLATED_STAND')
    os.environ['AGENT4K_ISOLATED_STAND'] = '1'
    try:
        before = Connection()
        try:
            namespace['reserve_release_ids'](before, 'assessment_program_definitions', 1)
        except AssertionError:
            require(not before.statements, 'BASELINE_REACHED_SQL')
        else:
            raise AssertionError('BASELINE_DEFECT_NOT_REPRODUCED')
        after = Connection()
        reserve_release_ids(after, 'assessment_program_definitions', 1)
        require(after.statements[-1][1] == ('assessment_program_definitions', 'id', 1), 'FIX_NOT_EFFECTIVE')
    finally:
        if old is None:
            os.environ.pop('AGENT4K_ISOLATED_STAND', None)
        else:
            os.environ['AGENT4K_ISOLATED_STAND'] = old

    receipts = [json.loads(path.read_bytes()) for path in (Path(__file__).parent / 'owned-bootstrap').glob('*.json')]
    require(len(receipts) == 3 and len({row['run_id'] for row in receipts}) == 3, 'OWNED_RUNS_MISSING')
    require({row['mode'] for row in receipts} == {
        'EXACT_EXISTING_1_1_SOURCE', 'SYNTHETIC_FUTURE_METADATA', 'NEGATIVE_CHANGED_SOURCE'}, 'RUN_SCOPE_MISMATCH')
    for row in receipts:
        cleanup = row['cleanup']
        require(row['status'] == 'ASSERTIONS_COMPLETED' and row['provider_calls'] == 0
                and row['database'] == 'product4k_pytest_' + row['run_id']
                and cleanup['database'] == row['database'] and cleanup['run_id'] == row['run_id']
                and all(cleanup[key] is True for key in ('owner_verified', 'database_absent', 'state_absent'))
                and cleanup['force'] is False, 'OWNED_CLEANUP_NOT_PROVED')
    paths = ['scripts/assessment_first_case.py', 'tests/path_start_release_source.py',
             'tests/path_start_release_inputs.py', 'tests/path29_browser_inputs.py',
             'tests/browser/fixtures/preparation-receipt.mjs', 'tests/browser/path29-participant.spec.mjs']
    return {'status': 'PASS_OFFLINE_HARNESS_PROBE_NOT_PATH', 'base_sha': BASE,
            'head_sha': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'),
            'baseline_program_reservation': 'REPRODUCED_REJECTION_BEFORE_SQL',
            'fixed_program_reservation': 'PASS_FAKE_CONNECTION_NO_SQL',
            'legacy_receipt_sha256': ref['sha256'], 'owned_bootstrap_runs': 3,
            'permanent_database_writes': 0, 'provider_calls': 0,
            'source_files_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'PREP_DIAG_01_root_cause': 'UNKNOWN',
            'limitations': ['Future metadata is SYNTHETIC, not a publication or new human QA',
                            'This script rechecks files and evidence, not live DB or paid PATH',
                            'Separate backend/Node/integration/browser logs carry actual execution results']}


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False, indent=2))
