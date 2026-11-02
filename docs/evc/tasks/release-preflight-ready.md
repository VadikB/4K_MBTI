# REL-PREFLIGHT-01: подготовка кандидата до Ready for review

## Результат и область

Единая команда до смены статуса PR заранее обнаруживает product-изменения без
нового номера, показывает следующий кандидат и после решения владельца выполняет
идемпотентную подготовку версии, frontend build и release-check.

Включено: локальный preflight, npm-команда, регрессии и явно согласованное изменение
`CONTRIBUTING.md`/шаблона задачи. Не входят: ослабление CI gate, автоматическое
решение типа версии, commit/push, Ready, merge и deploy.

## Источники и решения

- Основание: решение владельца 2026-11-02 устранить повторяющиеся поздние падения
  release gate без снятия контроля версии.
- Исходный base: `origin/main@0e18d31497736c54c5cc9517451fc8f9f7c4030a`;
  перед выпуском ветка перебазирована на
  `origin/main@a5934dd33f97a58532522fe747d03aa44140417d`.
- Прочитано: `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `verification-matrix.md`, `task-template.md`, `review-checklist.md`, архитектурные
  `context.md` и `registry.md`, workflow, release scripts и их unit-тесты.
- Предметная методология, PM/LU, данные, API, права и runtime не затронуты.
- Стоп-условия: нет; управляющие документы меняются отдельной явно согласованной
  задачей. Откат — revert этого PR, прежний CI gate продолжает защищать `main`.

## Действия выпуска

- `branch_push=true`, `pr=true` после локальной проверки.
- `merge=false`, `deploy=false`, `artifact_publish=false`.
- `version_bump=true`: после merge PR #148 владелец подтвердил продолжение;
  подготовлен следующий свободный PATCH-кандидат `2.0.49` перед Ready.

## Критерии приёмки

- [x] Docs/tests/CI-only diff проходит без требования нового номера (unit-контракт).
- [x] Product diff с версией base завершается до Ready и показывает следующий номер.
- [x] Согласованный кандидат готовится, frontend пересобирается, release gate проходит
  (unit-контракт subprocess orchestration).
- [x] Уже подготовленный кандидат проверяется идемпотентно существующим release-контрактом.
- [x] Обязательный CI gate и человеческое решение `version_bump` сохранены.

## Проверка

- `python -m pytest -q -p no:cacheprovider tests/unit/test_release_version.py`
- `python -m pytest -q -p no:cacheprovider tests/unit/test_ci_verification_workflows.py`
- `python scripts/prepare_ready_release.py --base-ref origin/main`
- `git diff --check`

Фактически в Draft: release/unit workflow tests — `14 passed`; живой preflight —
ожидаемый exit `2` с подсказкой `2.0.47 → 2.0.48`. После merge PR #148 ветка
перебазирована на `2.0.48`; `npm run ready:prepare -- --candidate 2.0.49` — PASS,
версия назначена, frontend пересобран, release gate пройден. Итоговые проверки
перед commit: release/unit workflow tests — `14 passed`, `npm run lint:js` — PASS,
`npm run build:web` — PASS, `git diff --check` — PASS. GitHub CI фиксируется
после commit/push для точного release SHA.
