# CI-GATE-03: автоматический полный CI для актуального head PR

## Результат

`Full verification` автоматически проверяет каждый актуальный head PR без ручной
метки. Отсутствие метки больше не создаёт заведомо красный required check, а ruleset
по-прежнему запрещает merge без успешных `frontend`, `pytest` и
`full-verification`.

## Область

- Включено: trigger `.github/workflows/full-verification.yml`, регрессионный тест
  конфигурации и действующие описания процесса CI.
- Не входит: product runtime, тестовые сценарии, схема/API, deploy, ruleset и
  исторические отчёты ранее принятых задач.

## Источники и решения

- Основание: явное решение владельца от 2026-10-30 выполнить процессное исправление
  отдельным PR.
- Base: `origin/main` `3e35937b55408424bc99d2b5baaa9499d6d43468`.
- Прочитано: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`,
  `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
  `docs/evc/task-template.md`, `docs/evc/tasks/ci-required-full-check.md`,
  `tests/README.md`, `.github/workflows/full-verification.yml`,
  `tests/unit/test_ci_verification_workflows.py`.
- Фактическая причина: `synchronize` запускал workflow для каждого нового head, но
  первый шаг завершал job ошибкой без `run-full-verification`. В PR №133 run
  `41091257134` упал на этом gate, а запущенный меткой run `41091995001` прошёл.
- Не найдено / противоречит: обязательных отсутствующих источников нет. Исторические
  task-записи сохраняют фактические решения своего времени и не редактируются.
- Стоп-условия: нет; предметный смысл, публичный API, данные, артефакты, права и
  граница развёртывания не меняются. Откат определён.

## План и состояние

- Завершено: локализована повторяющаяся причина ложного красного check.
- Завершено: автоматизирован полный прогон, новый контракт закреплён тестом и
  локально проверен.
- Активный шаг: передача отдельного PR и обязательный CI актуального head.
- Следующий шаг: review и решение владельца о merge после зелёных checks.
- Ветка: `codex/ci-auto-full-verification`.

## Действия выпуска

- `branch_push=true`: передать отдельную ветку на review.
- `pr=true`: отдельный независимо принимаемый процессный результат.
- `merge=false`: до успешного CI и решения владельца.
- `deploy=false`: изменение не разворачивается отдельно от принятия в `main`.
- `version_bump=false`: изменяются только `.github/`, `tests/`, `docs/` и
  `CONTRIBUTING.md`.
- `artifact_publish=false`: предметные артефакты не затронуты.

## Критерии приёмки

- [x] `Full verification` запускается для `opened`, `reopened` и `synchronize`.
- [x] Workflow не зависит от `run-full-verification` и не падает из-за её отсутствия.
- [x] Полный набор unit/HTTP/integration/browser сохранён.
- [x] Ruleset продолжает требовать успешный `full-verification` перед merge.
- [x] Product runtime, версия приложения, данные и deploy-script не изменены.

## Проверки

- `python -m pytest -q tests/unit/test_ci_verification_workflows.py`.
- YAML parse изменённого workflow.
- `scripts/check_release_version.py --base-ref origin/main`.
- `git diff --check`.
- PR CI: автоматические `frontend`, `pytest`, `full-verification` для head.

Локальный результат:

- `python -m pytest -q -p no:cacheprovider tests/unit/test_ci_verification_workflows.py tests/unit/test_release_version.py tests/unit/test_test_deploy_bootstrap.py`
  → `26 passed`.
- `yaml.safe_load(.github/workflows/full-verification.yml)` → PASS.
- `scripts/check_release_version.py --base-ref origin/main` →
  `Release check passed: 2.0.41`.
- `git diff --check` → PASS.
- PR CI → NOT_RUN до создания PR.

## Риски и откат

- Эксплуатационный эффект: полный CI расходует runner time на каждый PR head; это
  осознанная цена обязательного автоматического доказательства перед merge.
- Конфиг: новый PR сразу получает полный check; ручное действие владельца исключено.
- Схема, данные, безопасность и секреты: не затронуты.
- Откат: revert PR возвращает ручную метку. До отката required check должен быть
  получен для актуального head, иначе ruleset безопасно блокирует merge.
