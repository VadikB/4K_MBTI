"""Build an allowlisted, independently verifiable delivery ZIP from committed Git bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '053d1a58b46b5cfa7784d3d9ba6fd4785efed769'
DIAGNOSTIC = '4bab7230d8fa484fb8d922ee7d8b49b63674268d'

VERIFY = '''"""Verify the unpacked packet using Python's standard library only."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
manifest=json.loads((root/'MANIFEST.json').read_text())
expected=set(manifest['files']) | {'MANIFEST.json'}
actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
assert actual==expected, 'Unexpected or missing files'
for name,digest in manifest['files'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, name
print('PASS',len(manifest['files']),'files; implementation',manifest['implementation_sha'])
'''


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def build(directory):
    if git('status', '--porcelain').strip():
        raise ValueError('COMMITTED_CLEAN_WORKTREE_REQUIRED')
    head = git('rev-parse', 'HEAD').decode().strip()
    directory.mkdir(parents=True, exist_ok=False)
    packet = directory / ('4K_Synthetic_Contour_' + head[:12])
    packet.mkdir()
    def put(relative, data):
        file = packet / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data.encode() if isinstance(data, str) else data)

    changed = git('diff', '--name-only', '--diff-filter=ACMRT', BASE, head).decode().splitlines()
    for relative in changed:
        if not (relative in {'AGENTS.md', 'STATE.md'} or relative.startswith(('scripts/', 'tests/', 'docs/evc/'))):
            raise ValueError('UNEXPECTED_SCOPE:' + relative)
        if Path(relative).name in {'.env', 'state.json'}:
            raise ValueError('SECRET_STATE_CANNOT_BE_PACKAGED')
        put('repository/' + relative, git('show', head + ':' + relative))
    source_paths = [
        'assessment_definitions/cases/competencies_4k/functional-personalization/0.5/case-package.json',
        'assessment_definitions/cases/competencies_4k/functional-personalization/0.5/manifest.json',
        'assessment_definitions/cases/competencies_4k/functional-personalization-runtime/1.2.0/manifest.json',
        'assessment_definitions/providers/deepseek/v1/manifest.json',
        'assessment_definitions/catalog_contracts/competencies_4k/1.0/catalog-integrity-policy.json',
    ]
    for relative in source_paths:
        if git('show', BASE + ':' + relative) != git('show', head + ':' + relative):
            raise ValueError('PUBLISHED_SOURCE_WAS_CHANGED:' + relative)
        put('source-inputs/' + relative, git('show', head + ':' + relative))
    put('diff/main-to-final.patch', git('diff', '--binary', BASE, head))
    put('diff/after-4bab723.patch', git('diff', '--binary', DIAGNOSTIC, head))
    put('diff/after-4bab723.stat.txt', git('diff', '--stat', DIAGNOSTIC, head))
    bundle = packet / 'git' / 'commits.bundle'
    bundle.parent.mkdir()
    subprocess.run(['git', 'bundle', 'create', str(bundle), BASE + '..HEAD'], cwd=ROOT, check=True)
    subprocess.run(['git', 'bundle', 'verify', str(bundle)], cwd=ROOT, check=True, capture_output=True)
    put('VERIFY.py', VERIFY)
    put('HANDOFF.md', f'''# Постоянный синтетический контур — пакет передачи

Implementation SHA: `{head}`; ветка `codex/assessment-first-case`.
Base/main: `{BASE}`. Реальный отрицательный прогон: `{DIAGNOSTIC}`.
PATH-START-01 не исполнялся. Новых платных LLM-вызовов при сдаче нет.

## Проверка без рабочей директории

Распакуйте ZIP и выполните `python3 VERIFY.py` из этой папки. MANIFEST.json
содержит SHA-256 каждого файла (кроме самого манифеста); внешний .zip.sha256
контролирует целиком ZIP. Проверка не требует PostgreSQL, секретов или проекта.

## Состав

- `repository/docs/evc/assessment-first-case-profile.md` — профиль и команда запуска.
- `repository/scripts/assessment_first_case.py` — постоянный runner.
- `repository/docs/evc/tasks/assessment-first-case-contour.md` — полный отчёт и
  соответствие восьми пунктам первоначальной настройки.
- `repository/docs/evc/evidence/assessment-contour-2026-11-04/` — первичные
  source-provenance, code-identity, run, runner-result, cleanup, отрицательный
  real-provider receipt, screenshot и отдельная бесплатная регрессия экспортёра.
- `source-inputs/` — точные неизменённые JSON-источники для независимого пересчёта.
- `diff/after-4bab723.patch` и `.stat.txt` — все изменения после реального прогона.
- `diff/main-to-final.patch` — полный diff настройки к main.
- `git/commits.bundle` — коммиты настройки с prerequisite main `{BASE}`.

Для восстановления кода используйте существующий clone Product 4K с этим base:
`git fetch /path/to/commits.bundle HEAD`;
`git switch --detach {head}`. Сам пакет уже содержит все изменённые файлы;
исходные зависимости Python/npm устанавливаются по README проекта.

## Результат и ограничения

Настройка и бесплатная регрессия экспортёра проверены. Реальный сценарий вернул
`M5_FUNCTIONAL_AS_NOT_ADMITTED:INCOMPLETE`: AS/start отсутствуют, ответов 0.
PREP-DIAG-01 сохранён для следующего пакета; конкретные check ID/причины старого
отказа UNKNOWN, потому что старая выгрузка их не сохранила, а БД уже удалена.
Синтетическая negative-export regression не реконструирует этот отказ.

Исходный Case QA в seed — ЯВНАЯ ТЕСТОВАЯ ПОДСТАНОВКА. Она не доказывает
реальный human review, методологическое согласование или допуск целевой пилотной
программы. Методология/admission/repair/M0–M8 не изменены.

State, env-файлы, пароли, SSH/API keys и сырые LLM prompts/responses не включены.
В пакете есть только код, опубликованные источники и разрешённые safe evidence.
CI текущей ветки NOT_RUN (PR/push не выполнялись). Main и публичное развёртывание
не обновлялись; наблюдавшаяся версия test — 2.0.61.
''')
    manifest = {'schema_version': 1, 'implementation_sha': head, 'branch': 'codex/assessment-first-case',
        'base_main_sha': BASE, 'real_diagnostic_sha': DIAGNOSTIC,
        'diagnostic_result': 'FAIL_INCOMPLETE', 'root_cause': 'UNKNOWN', 'new_paid_llm_calls': 0,
        'files': {str(file.relative_to(packet)): hashlib.sha256(file.read_bytes()).hexdigest()
                  for file in sorted(packet.rglob('*')) if file.is_file()}}
    put('MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    subprocess.run(['python3', str(packet / 'VERIFY.py')], check=True)
    archive = directory / (packet.name + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        for file in sorted(packet.rglob('*')):
            if file.is_file():
                output.write(file, str(file.relative_to(directory)))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (directory / (archive.name + '.sha256')).write_text(digest + '  ' + archive.name + '\n')
    print(json.dumps({'archive': str(archive), 'sha256': digest, 'implementation_sha': head,
                      'file_count': len(manifest['files'])}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    build(parser.parse_args().directory.resolve())
