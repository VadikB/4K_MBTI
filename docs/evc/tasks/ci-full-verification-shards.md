# CI: параллельная полная проверка PR

## Результат

Сократить критический путь `full-verification` с текущих ~11 минут до целевых
4–6 минут без уменьшения набора integration- и browser-проверок.

## Область

- Включено: разбиение CI на параллельные integration/browser jobs, четыре shard
  runtime browser-набора, кэш Chromium, итоговый обязательный check и CI-регрессия.
- Не входит: product runtime, предметные пакеты, схема/данные, deploy, ruleset,
  версия приложения и изменение состава тестов.

## Контекст

- Основание: решение владельца в чате 03.11.2026 — «4-6 минут это хорошая цель делаем».
- База: `origin/main` / `f57fc97`.
- Значимые точки входа: `.github/workflows/full-verification.yml`,
  `playwright.config.mjs`, `tests/unit/test_ci_verification_workflows.py`.
- Архитектурный адрес: CI/инфраструктура проверки; PM/LU и владельцы продуктовых
  данных не затрагиваются.
- Существующий контракт: required checks `frontend`, `pytest`,
  `full-verification`; browser-тесты работают только с synthetic-данными и
  создают собственные `product4k_pytest_*` БД.
- Предметные артефакты и записи artifact debt: не применимо.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`,
  `docs/evc/review-checklist.md`, `docs/architecture/product-4k/1.0/context.md`,
  `docs/architecture/product-4k/registry.md`, `tests/README.md`,
  `tests/browser/README.md`; база `f57fc97`.
- Change 01/M1/M5: не применимы к изменению CI; предметный смысл и runtime не меняются.
- Пробел: фактическое время нового графа подтверждается только GitHub-hosted runner
  после публикации PR; локально проверяются структура workflow и неизменность набора.
- Решение: integration выполняется отдельно; browser matrix содержит один fast lane
  и четыре runtime shards. Каждый matrix job имеет отдельный runner/PostgreSQL,
  поэтому фиксированные browser-порты между shard не конфликтуют.
- Стоп-условия: все восемь — нет; публичный API, данные, PM/LU, артефактный контур,
  чувствительные данные и границы deploy не меняются. Откат — revert одного PR.
- Требуется решение владельца: нет.

## План и состояние

- Завершено: разведка, параллельный граф, CI-регрессия, документация и локальные
  структурные проверки.
- Активный шаг: повторный CI после фиксации фактического результата в отчёте.
- Следующий шаг: человеческое review и merge владельцем после зелёного CI head SHA.
- Ветка: `codex/full-verification-shards`; PR
  [#159](https://github.com/VadikB/4K_MBTI/pull/159).

## Действия выпуска

- `branch_push=true`, `pr=true`, `merge=false`, `deploy=false`.
- `version_bump=false`, `artifact_publish=false`.
- Изменение флагов требует отдельного фактического действия; CI-оптимизация не
  является product-изменением и не требует нового номера версии.

## Ограничения и риски

- Совместимость: имя итогового job/check `full-verification` сохраняется.
- Данные и миграции: нет; только временные test/pytest БД на CI-runner.
- Безопасность и ПД: тестовые synthetic-данные, credentials/traces не публикуются.
- Производительность: runner-minutes могут вырасти из-за повторной установки
  окружения, но критический путь сокращается параллельным выполнением.
- GitHub может ограничить фактический параллелизм доступной квотой runner.

## Критерии приёмки

- [x] Integration и browser заданы независимыми jobs без `needs` между ними.
- [x] Все 14 runtime browser-тестов распределяются по четырём shards (4+4+3+3).
- [x] Остальные 83 browser-теста выполняются fast lane без исключений.
- [x] Итоговый `full-verification` требует success обоих обязательных jobs.
- [x] Browser evidence публикуется отдельно для каждого lane/shard.
- [x] Первый фактический CI `e64e207` прошёл за 4:10; integration — 4:00,
  браузерные lanes завершились раньше.

## План проверки

- `git diff --check`.
- YAML parse `.github/workflows/full-verification.yml`.
- `.venv/bin/python -m pytest tests/unit/test_ci_verification_workflows.py`.
- `npx playwright test --list` для fast lane и каждого runtime shard; объединение
  списков должно покрывать browser suite ровно один раз.
- Полный фактический прогон — GitHub Actions PR.

## Откат

Revert PR возвращает последовательный workflow. Product runtime, данные и версия
не изменяются; восстановление данных не требуется.

## Проверки (локально)

- `/Users/vadim_bogachev/Developer/4K/.venv/bin/python -m pytest tests/unit/test_ci_verification_workflows.py tests/unit/test_release_version.py tests/unit/test_test_deploy_bootstrap.py`
  → PASS, 38 тестов.
- `npx playwright test ... --list` для fast lane и runtime shards → PASS:
  fast 83; runtime 4+4+3+3; всего 97 тестов, каждый spec включён один раз.
- YAML parse через `yaml.safe_load` → PASS.
- `node --check playwright.config.mjs` → PASS.
- `git diff --check` → PASS.
- `actionlint` → NOT_RUN: утилита локально не установлена; синтаксис и expressions
  дополнительно проверит GitHub Actions на head PR.
- Полный browser/integration локально → NOT_RUN: изменение не затрагивает тестовый
  runtime, а доказательство параллелизма и целевого времени возможно только на
  GitHub-hosted runners.
- [GitHub Actions run 41638207277](https://github.com/VadikB/4K_MBTI/actions/runs/41638207277)
  для `e64e207` → PASS, 4:10 total; integration 4:00; пять browser artifacts.
  Повторный CI требуется для head после добавления этого доказательства в отчёт.
