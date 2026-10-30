# CI-GATE-01: полный CI один раз перед merge

## Результат

Каждое обновление PR автоматически получает быстрые `frontend` и `pytest`
(unit/HTTP). Полный unit/HTTP/integration/browser набор запускается владельцем один
раз для актуального head перед merge и становится отдельным required check.

## Область

- Этап 1 этого PR: быстрый PR CI, ручной workflow `Full verification`, тесты
  конфигурации и документация процедуры.
- Этап 2 после принятия: активный ruleset для `main` с обязательными checks
  `frontend`, `pytest`, `full-verification`; затем удаление повторного полного
  post-merge запуска отдельным PR.
- Не входит: Merge Queue (недоступна для user-owned repository), изменение
  product runtime, тестовых сценариев, схемы/API и deploy-скрипта.

## Контекст и решения

- Основание: решение владельца от 2026-10-30 отказаться от неэффективного
  параллельного CI PR №128 и перейти к быстрому PR + полному pre-merge check.
- PR №128 закрыт без merge; remote branch `codex/ci-parallel-tests` удалена.
- Base: `origin/main` `13e77ef2abebfe1be40d497963d80045db282e04`.
- Измерение №128: wall-clock 7m12s, runner time 14m11s; browser shards 1m56s/7m04s.
- GitHub settings: rulesets и classic branch protection отсутствуют.
- GitHub Merge Queue доступна только organization-owned repositories; репозиторий
  принадлежит личному аккаунту `VadikB`, правило в UI отсутствует.
- Безопасный порядок обязателен: сначала workflow попадает в `main`, затем создаётся
  ruleset; до его активации post-merge полный CI сохраняется как страховка.

## Прочитано

`AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
`docs/evc/verification-matrix.md`, `docs/evc/task-template.md`,
`docs/evc/review-checklist.md`, `tests/README.md`, `tests/browser/README.md`,
`.github/workflows/backend-tests.yml`, GitHub ruleset/branch settings и официальная
документация GitHub Merge Queue от 2026-10-30.

## Стоп-условия и границы

- Миграции, персональные данные, секреты, предметные артефакты и LLM не затронуты.
- Активация ruleset до появления workflow в default branch запрещена: она может
  заблокировать принятие самого изменения отсутствующим check.
- Удаление полного запуска на push в `main` запрещено до подтверждённого активного
  ruleset без bypass.
- Merge, deploy и включение ruleset требуют последовательного завершения этапов.

## Действия выпуска

- `branch_push=true` после локальной проверки.
- `pr=true` для этапа 1.
- `merge=false` до решения владельца.
- `deploy=false`.
- `version_bump=false`: только `.github/`, `tests/`, `docs/`.
- `artifact_publish=false`.

## Критерии приёмки этапа 1

- [ ] На `pull_request` integration/browser пропущены, unit/HTTP и frontend проходят.
- [ ] Ручной `Full verification` на head выполняет все четыре набора.
- [ ] Push в `main` пока сохраняет полный CI и допускает deploy только после него.
- [ ] Конфигурация защищена адресными unit-тестами.
- [ ] Product runtime, данные и deploy-script не изменены.

## Проверки

- YAML parse обоих workflows.
- `tests/unit/test_ci_verification_workflows.py`.
- `tests/unit/test_test_deploy_bootstrap.py` и release guard tests.
- `scripts/check_release_version.py --base-ref origin/main`.
- `git diff --check`.
- PR CI: быстрые jobs; ручной dispatch CI на head: полный набор.

## Откат

Revert этапа 1 возвращает полный автоматический `pytest` на PR. До этапа 2 ruleset
не активирован, схема данных и runtime не меняются.
