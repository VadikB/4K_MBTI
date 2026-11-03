# CI: автоматическое включение новых browser spec

## Результат и область

- Результат: новый `tests/browser/*.spec.mjs` автоматически попадает в fast lane
  `full-verification`; `runtime.spec.mjs` остаётся единственным шардируемым набором.
- Основание: решение владельца в чате после merge PR #159 — «делаем».
- База: `origin/main` / `89a2d1d`.
- Включено: отдельный test-owned Playwright CI profile, workflow, документация и
  CI-регрессия. Корневой локальный Playwright config не меняется.
- Не входит: состав/поведение тестов, product runtime, данные, deploy, ruleset и версия.

## Источники и решения

- Прочитано ранее в связанной задаче #159: `README.md`, `CONTRIBUTING.md`,
  обязательные EVC workflow/matrix/review/artifact документы, архитектурный context,
  Registry, Change 01/manifest/ADR/traceability, `tests/README.md` и
  `tests/browser/README.md`. В `89a2d1d` эти источники по области задачи не менялись.
- Техническое решение: `BROWSER_SUITE=fast` использует общий `*.spec.mjs` и
  исключает только `runtime.spec.mjs`; `BROWSER_SUITE=runtime` выбирает только
  `runtime.spec.mjs`; без переменной локально сохраняется полный suite.
- Стоп-условия: все — нет. Публичный API, PM/LU, схема/данные, предметные
  артефакты, безопасность и deploy не меняются. Откат — revert PR.
- Открытые решения: нет.

## План и состояние

- Завершено: анализ, реализация, документация и локальные проверки selection.
- Активный шаг: commit, PR и обязательный CI.
- Следующий шаг: фактический GitHub Actions run и человеческое review.
- Ветка: `codex/browser-auto-discovery`.

## Действия выпуска

- `branch_push=false`, `pr=false`, `merge=false`, `deploy=false`.
- `version_bump=false`, `artifact_publish=false`.

## Критерии приёмки

- [x] Fast lane автоматически видит все spec, кроме runtime: 83 теста/3 файла.
- [x] Runtime lane видит только runtime и сохраняет 4+4+3+3.
- [x] Локальный default видит полный browser suite: 97 тестов/4 файла.
- [x] CI-регрессия запрещает возврат явного списка fast-spec.
- [ ] Обязательный CI актуального head успешен.

## План проверки

- `git diff --check`.
- `node --check tests/browser/playwright.ci.config.mjs`.
- CI unit regression.
- `BROWSER_SUITE=fast npx playwright test --list`.
- `BROWSER_SUITE=runtime npx playwright test --fully-parallel --shard=N/4 --list`.
- `npx playwright test --list` для полного локального набора.

## Риски и откат

- Новый тяжёлый spec по умолчанию попадёт в fast lane. Если он требует шардирования,
  его следует осознанно перенести в runtime-контур отдельным изменением.
- Откат: revert PR; данные и runtime не затрагиваются.

## Проверки (локально)

- `node --check tests/browser/playwright.ci.config.mjs` → PASS.
- `.venv/bin/python -m pytest tests/unit/test_ci_verification_workflows.py` →
  PASS, 9 тестов.
- Расширенная CI-регрессия с release/deploy тестами → PASS, 38 тестов.
- YAML parse `.github/workflows/full-verification.yml` → PASS.
- `npx playwright test --list` → PASS, 97 тестов/4 файла.
- `BROWSER_SUITE=fast npx playwright test --list` → PASS, 83 теста/3 файла.
- Четыре `BROWSER_SUITE=runtime ... --shard=N/4 --list` → PASS, 4+4+3+3.
- `git diff --check` → PASS.
- Полный browser/integration → локально NOT_RUN; фактический изолированный прогон
  выполняется обязательным CI PR и остаётся критерием готовности.
- Первый CI `ab87a9f` → FAIL до тестов: корневой `playwright.config.mjs` был
  корректно классифицирован release-gate как product change без новой версии.
  Исправление: selection вынесен в `tests/browser/playwright.ci.config.mjs`;
  release-контракт и версия не ослабляются.
- Второй CI `07d1523`: frontend/release-gate → PASS; runtime shard 3 завершил
  browser step, но evidence upload → FAIL, потому что относительные output/reporter
  пути разрешились от каталога CI-config. Исправление: оба пути закреплены абсолютно
  от workspace root; отсутствие evidence по-прежнему считается ошибкой.
