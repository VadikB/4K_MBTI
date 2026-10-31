# CI-REL-01: release gate при готовности PR к review

## Результат

Draft PR проверяет код без преждевременного присвоения release-номера. Переход в
`Ready for review` повторно запускает обязательный CI и включает проверку нового
согласованного номера для продуктовых изменений.

## Область

- Включено: события PR в обоих workflow, условие release gate, регрессионный тест
  конфигурации и действующая документация процесса.
- Не входит: product runtime, схема/API, deploy, ruleset, присвоение версии любому
  существующему PR и предметные артефакты.

## Источники и решения

- Основание: решение владельца от 2026-10-31 исправить повторяющееся противоречие
  между draft-процессом и обязательным release gate отдельной процессной задачей.
- Base: `origin/main` `de8261d6455719d6c300554d01789118ec9c044c`.
- Прочитано: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`,
  `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
  `docs/evc/task-template.md`, `docs/evc/review-checklist.md`, `tests/README.md`,
  `.github/workflows/backend-tests.yml`, `.github/workflows/full-verification.yml`,
  `scripts/check_release_version.py`, `tests/unit/test_release_version.py`,
  `tests/unit/test_ci_verification_workflows.py`.
- Фактическая причина: `Verify application release` безусловно отклонял любое
  продуктовое изменение с версией base уже в draft, хотя процесс назначает номер
  только кандидату выпуска.
- Решение: draft откладывает только release gate; `ready_for_review` запускает
  обязательные jobs заново и включает gate. `converted_to_draft` также является
  явным событием, чтобы состояние checks соответствовало состоянию PR.
- Стоп-условия: нет. Изменение управляющих документов явно согласовано владельцем;
  runtime, данные, секреты, права, методология и deploy не затронуты.

## План и состояние

- Завершено: причина локализована, контракт согласован владельцем.
- Завершено: workflow, регрессия и документация процесса обновлены; локальный
  минимум прошёл.
- Активный шаг: отдельный draft PR и обязательный CI актуального head.
- Следующий шаг: review владельца, затем проверка перехода `Ready for review`.
- Ветка: `codex/ci-draft-release-gate`.

## Действия выпуска

- `branch_push=true`: передать отдельную ветку на review.
- `pr=true`: отдельный процессный результат.
- `merge=false`: требуется успешный CI и решение владельца.
- `deploy=false`: отдельное развёртывание не выполняется.
- `version_bump=false`: product runtime не меняется.
- `artifact_publish=false`: предметные артефакты не затронуты.

## Критерии приёмки

- [x] Draft запускает обязательные jobs, но release gate явно пропущен.
- [x] `Ready for review` повторно запускает оба workflow и включает release gate.
- [x] Возврат в draft снова отражается отдельным CI run.
- [x] Merge продуктового изменения без нового согласованного номера не разрешён.
- [x] Поведение закреплено адресным регрессионным тестом.
- [x] Runtime, данные, deploy и ruleset не изменены.

## План проверки

- YAML parse обоих workflow.
- `tests/unit/test_ci_verification_workflows.py` и `tests/unit/test_release_version.py`.
- `scripts/check_release_version.py --base-ref origin/main`.
- `git diff --check`.
- PR CI: draft показывает skipped release step; после `Ready for review` gate
  выполняется и остаётся обязательным для продуктовых изменений.

Локальный результат:

- `python -m pytest -q -p no:cacheprovider tests/unit/test_ci_verification_workflows.py tests/unit/test_release_version.py`
  → `9 passed`.
- YAML parse `.github/workflows/backend-tests.yml` и
  `.github/workflows/full-verification.yml` → PASS.
- `scripts/check_release_version.py --base-ref origin/main` →
  `Release check passed: 2.0.44`.
- `git diff --check` → PASS.
- PR CI → NOT_RUN до создания PR.

## Риски и откат

- Риск: ошибочная конфигурация событий могла бы оставить старый green check после
  смены статуса. Он закрыт явным `ready_for_review` и тестом обоих workflow.
- Данные, безопасность, персональные данные и внешние сервисы: не затронуты.
- Откат: revert процессного PR возвращает прежний безусловный gate в draft; данные
  и runtime не требуют восстановления.
