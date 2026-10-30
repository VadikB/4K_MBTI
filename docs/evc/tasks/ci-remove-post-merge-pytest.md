# CI-GATE-02: убрать повторный полный CI после merge

## Результат

После squash merge проверенный commit сразу разворачивается на test без повторного
unit/HTTP/integration/browser прогона. До merge GitHub требует успешные `frontend`,
`pytest` и `full-verification` для актуального head PR.

## Область и основание

- Решение владельца от 2026-10-30: быстрый обязательный PR CI и тяжёлый ручной
  required check перед merge; ветка `codex/ci-parallel-tests` удалена.
- Этап 1 принят PR №129, commit `e08c6f51acaf5a59b08b73cc98f05e9d03be0bd4`.
- Ruleset `Protect main and require full verification` (ID `26191885`) активен для
  `main`, bypass отсутствует, разрешён только squash, требуется актуальный head и
  checks `frontend`, `pytest`, `full-verification` от GitHub Actions.
- Меняются только CI workflow, адресные тесты и документация процедуры. Product
  runtime, схема/API, данные, тестовые сценарии и deploy-script не меняются.

## Прочитано

`AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
`docs/evc/verification-matrix.md`, `docs/evc/task-template.md`,
`docs/evc/review-checklist.md`, `tests/README.md`,
`.github/workflows/backend-tests.yml`, `.github/workflows/full-verification.yml`,
`tests/unit/test_ci_verification_workflows.py`,
`tests/unit/test_test_deploy_bootstrap.py` и сохранённый GitHub ruleset.

## Стоп-условия и границы

- Предметные нормы, PM/LU, персональные данные, секреты, миграции и LLM не затронуты.
- Удаление post-merge проверок разрешено только после подтверждения активного
  ruleset без bypass; условие выполнено 2026-10-30.
- `deploy-test` по-прежнему принимает точный `github.sha`, проверяет его принадлежность
  `origin/main` и сохраняет существующий rollback deploy-скрипта.

## Критерии приёмки

- [ ] `frontend` и `pytest` workflow `CI` запускаются только на `pull_request`.
- [ ] Integration и browser acceptance находятся только в `Full verification`.
- [ ] Push в `main` запускает `deploy-test` без зависимости от повторных test jobs.
- [ ] Адресные тесты конфигурации и deploy bootstrap проходят.
- [ ] На актуальном head PR успешны required checks, включая ручной
  `full-verification`.

## Проверки

- YAML parse обоих workflows.
- `tests/unit/test_ci_verification_workflows.py`.
- `tests/unit/test_test_deploy_bootstrap.py` и release guard tests.
- `scripts/check_release_version.py --base-ref origin/main`.
- `git diff --check`.
- PR CI: `frontend`, `pytest`; ручной `Full verification` на точном head.

## Риски и откат

- Конфиг: merge заблокирован, если ручной `full-verification` не запускался для head.
- Deploy: после merge повторной проверки нет; безопасность обеспечивают required
  checks до merge и существующий rollback `deploy-test`.
- Схема, данные, безопасность: не применимо, изменения отсутствуют.
- Откат: revert этого PR возвращает полный post-merge CI и зависимость deploy от
  `frontend`/`pytest`; ruleset можно оставить активным.

## Состояние

- Ветка: `codex/ci-remove-post-merge-pytest` от `origin/main` `e08c6f5`.
- Реализовано: быстрые jobs ограничены `pull_request`, тяжёлые шаги удалены из
  `CI`, `deploy-test` отвязан от повторных jobs, процедура и регрессия обновлены.
- Локальные проверки: YAML обоих workflows PASS; 26 адресных тестов PASS за
  38.58s; release guard `2.0.38` PASS; `git diff --check` PASS. Pytest не смог
  записать необязательный `.pytest_cache` в managed worktree, на результат тестов
  это не повлияло.
- Текущий шаг: commit и PR.
- Следующий шаг: автоматические checks, ручной `Full verification`, review владельца.
- Открытые вопросы: нет.
