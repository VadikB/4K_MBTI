# AC18-FIX-02 / P2-AC03 — безопасная причина отказа после reload

Статус: подготовка PR #186 к Ready после слияния #185. Base
`origin/main@edd3183357ef7c0dd80e8535e947796466e35df1` (2.0.77),
кандидат 2.0.78; ветка `codex/ac18-fix02-failed-readback`. Результат
не зависит от JS-правки #185 и остаётся отдельным PR.

## Результат и область

При terminal `failed` после reload `/acquaintance` возвращает ту же публичную
безопасную причину, что owned `GET /assessment/cycles/preparation/{operation_id}`.
Внутренний `error_message` и trace не выходят в ответ. Предметная политика
повторной подготовки, права, методология, snapshots, схема и API-форма не меняются.

## Источники и решения

Прочитаны `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
`verification-matrix.md`, `artifact-recipe.md`, архитектурные `context.md` и
`registry.md`, маршрут Change 01 и task manifest, `TASK.txt`/`SOURCES.md`/
`START_CODEX.txt` пакета (ред. 1.0, 07.11.2026), `docs/adr/002-cycle-as-dialogue-contracts.md`,
`docs/architecture/pilot-plan-start-admission-contract.md`,
`Api/product_cycle_preparation_queue.py`, `Api/acquaintance.py`, `Api/routes.py`,
`web/js/screens/onboarding.js` и адресные unit/integration/browser-тесты.
M1 v1.4 остаётся FROZEN/CURRENT=NO. Источник → правило: P2-AC03 требует
достоверного terminal failure после reload → owned operation/readiness →
`latest_scope_operation`/`public_operation` → unit и HTTP/PG регрессия.
Владение operation — серверная очередь; UI читает participant-safe projection.

Пробел на свежем main: `latest_scope_operation` выбирает лишь `operation_id,status`,
поэтому `public_operation` не видит `error_message` и после reload заменяет
специальный безопасный код на общий. Это не разрешение показывать raw error.
Принятый подход: выбрать `error_message` внутри сервера и немедленно пропустить
через существующий whitelist. Новая публичная схема не требуется.

Отдельный открытый вопрос P2-AC04: UI предлагает `retry` для всех terminal failed,
а сервер не публикует классификацию допустимости повтора и принимает новый ключ
после failed. Это изменение policy/API, не входит в данный PR; до решения владельца
его не реализовывать. Стоп-условия для текущей правки: смысл, PM, API, миграция,
артефакты, права, безопасность, откат — нет; для retry-policy — да.

## Реализация и проверки

`Api/product_cycle_preparation_queue.py` добавляет внутренний `error_message` в
SELECT последней scope-операции; наружу проходит только прежний whitelist
`public_operation`. `tests/unit/test_product_cycle_preparation_projection.py`
фиксирует специальный безопасный код и отсутствие внутренней диагностики;
`tests/integration/test_path29_participant_owned_stand.py` сравнивает owned GET и
`/acquaintance` после terminal failed на настоящем HTTP/PG.

- До исправления адресный unit-тест: **FAIL**, после reload получен общий код вместо
  `ASSESSMENT_CATALOG_NO_ADMISSIBLE_SPECIALIST_CASE`.
- После исправления unit-файл: **PASS**, 9/9.
- `npm run test:backend` сначала **NOT_RUN_ENV**: в отдельном worktree нет `.venv`.
  Эквивалентная команда с уже установленным Python основного workspace,
  `PYTHON_DOTENV_DISABLED=1 …/.venv/bin/python -m pytest -q -m 'not integration and not e2e and not llm'`:
  **PASS**, 957 passed, 354 deselected.
- Адресный `pytest --run-integration -q -s tests/integration/test_path29_participant_owned_stand.py`
  с `STAND_ADMIN_URL` и `TEST_DATABASE_URL` на собственном disposable PostgreSQL16,
  БД `agent4k_pytest`: **PASS**, 1/1. Marker-owned стенд создан и удалён штатным
  runner; контейнер с label `codex.owner=ac18-fix02-readback` после проверки остановлен.
- После обновления от #185: `npm run ready:prepare -- --candidate 2.0.78`
  **PASS**, `npm run lint:js` **PASS**, frontend 150/150 **PASS**,
  backend 957 passed / 354 deselected **PASS**; `git diff --check` **PASS**.
  Реальные LLM, письма и рабочая БД не использовались.
- Полный CI для обновлённого head: **PENDING**; обязателен перед merge.

Следующий шаг — commit/push подготовленного кандидата, Ready и полный CI
для точного head. Затем отдельный squash-merge после проверки актуального main.

Для последовательного merge владелец разрешил `branch_push=true`, `pr=true`,
`merge=true`, `deploy=true`, `version_bump=true`; `artifact_publish=false`,
`llm=false`.

## Риски и откат

Дополнительное серверное поле читается только внутри запроса, публично остаётся
`{operation_id,status,error:{code,message}}`. Секреты и персональные данные не
используются; integration — только owned изолированная БД. Откат — revert
проекции и регрессий, не удаляя сохранённые операции/оценки.
