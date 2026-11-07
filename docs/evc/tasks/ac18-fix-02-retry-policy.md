# AC18-FIX-02 / P2-AC04 — серверный допуск повторной подготовки

Статус: подготовка PR #187 к Ready после слияния #186; base
`origin/main@79d8b5091f32e579d79641ec63962236cb9fd38b` (2.0.78),
кандидат 2.0.79. Решение владельца от 07.11.2026:
явный новый запуск допустим после технического сбоя; после недопуска AS или отсутствия
допустимой ситуации сервер отклоняет повтор, а участник обращается к ответственному.

## Результат и граница

Сохранённая операция остаётся авторитетной: чтение и повтор с тем же idempotency key
возвращают её, новый ключ после предметного отказа даёт `409
PRODUCT_CYCLE_PREPARATION_RETRY_NOT_ALLOWED`. Только явно классифицированный
технический отказ разрешает новый запуск. Новый `retry_allowed` в participant-safe
projection управляет кнопкой; отсутствие поля для старой операции трактуется UI как
запрет. Неизвестная ошибка также закрыта для повтора. Внутренний `error_message`
и trace не выходят наружу. Автоматических LLM-повторов нет.

Этот PR не меняет admission/repair, опубликованные артефакты, содержание AS,
профиль, права или схему. Потерянный ответ первоначальной команды исправляется
отдельно в #185; safe failure после reload — зависимость #186. Ветка
`codex/ac18-fix02-retry-policy` первоначально основана на `f221f3e6` (#186).
После слияния #185 и #186 ветка обновлена от текущего `main`; PR должен иметь
base `main`, содержать только retry-policy и пройти полный CI на новом head.

## Источники и решение

Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
`docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`,
Product Architecture `context.md`/`registry.md`, Change 01 README и task manifest,
`docs/adr/002-cycle-as-dialogue-contracts.md`,
`docs/architecture/pilot-plan-start-admission-contract.md`, `TASK.txt` и
`SOURCES.md` пакета AC18-FIX-02 ред. 1.0 от 07.11.2026, а также адресные очередь,
owned API, onboarding и unit/HTTP-PG/browser-тесты. M1 v1.4 остаётся
FROZEN/CURRENT=NO; task manifest — выбранные источники, не runtime publication.

Цепочка: P2-AC04 и решение владельца → owned operation/idempotency contract →
`Api/product_cycle_preparation_queue.py` (`enqueue`, `public_operation`) →
`web/js/screens/onboarding.js` → unit, HTTP/PG и browser регрессии.
PM-03 подготавливает AS, PM-04 исполняет; исправляется только orchestration,
не предметная оценка. Технические типы ограничены `TimeoutError`,
`ConnectionError`, `LlmGatewayError`; для ошибок вне перечня повтора нет.
Дополнительно известные `M5_FUNCTIONAL_AS_NOT_ADMITTED` и
`M7_NO_ADMISSIBLE_CASE` имеют приоритет запрета. Это fail-closed правило не
объявляет все ошибки провайдера временными и не гарантирует успешный новый запуск.

## Изменённые файлы

- `Api/product_cycle_preparation_queue.py`: безопасный признак и проверка под
  существующей user/operation advisory lock; старый ключ сохраняет идемпотентность.
- `web/js/screens/onboarding.js` и `web/dist/`: запрещённый повтор не предлагается;
  технический повтор остаётся явным, без скрытого POST при readback.
- `tests/unit/test_product_cycle_preparation_projection.py`,
  `tests/integration/test_m10_product_path_db.py`, `tests/browser/auth-r03.spec.mjs`:
  классификация, приватность, HTTP/PG новый/старый ключ и browser-кнопки.

## Проверки

- Unit projection: PASS, 16/16 на окончательном коде.
- `npm run lint:js` и `npm run build:web`: PASS.
- `node --test tests/frontend/*.test.mjs`: PASS, 150/150.
- Playwright адресный сценарий с синтетическими HTTP и реальным UI: первый
  запуск NOT_RUN_ENV (`listen EPERM` в sandbox), повтор на localhost: PASS, 1/1.
  Один промежуточный FAIL был неверным ожиданием общего счётчика POST после
  добавления явного разрешённого retry; исправлен и повторён.
- HTTP/PG integration на собственной disposable PostgreSQL 16,
  `agent4k_pytest`: PASS, 1/1. Запрещённый новый ключ — 409, технический — 202,
  конкурирующий ключ возвращает ту же queued operation; число операций — 2.
- Полный backend без integration/e2e/llm: PASS, 964 passed, 355 deselected
  на окончательном коде.
- `git diff --check`: PASS.
- После обновления от #186: `npm run ready:prepare -- --candidate 2.0.79`
  PASS; unit projection 16/16, lint, frontend 150/150 и адресный browser 3/3
  PASS. Полный CI нового head — PENDING.
- Реальный LLM, рабочая БД, письма, physical phone и deploy: NOT_RUN.
  Этот тест не доказывает качество real-provider AS.

## Риски и откат

Публичный API расширен необязательным булевым `retry_allowed` только для failed;
старый клиент без поля продолжит читать operation, новый клиент со старым
сервером fail-closed. Конфиг, схема, published snapshots не меняются. Новый
полный запуск после разрешённого технического отказа использует существующие
scope/advisory locks и сохраняет прежнюю failed operation; test не стирает
evidence. Откат — revert этого PR, не удаляя операции/Cycle/AS. Такой откат
вернёт прежнюю универсальную кнопку и потому требует отдельного решения при
регрессе; более безопасная временная мера — скрыть retry в UI.

## Передача

Владелец подтвердил приёмку PR #185–191 и последовательный squash-merge с
`branch_push=true`, `pr=true`, `merge=true`, `deploy=true`,
`version_bump=true`. `artifact_publish=false`, `llm=false`. После финальной
локальной проверки: commit/push, base `main`, Ready, полный CI точного head,
проверка свежего `main`, затем squash-merge. Технический PASS не равен
real-provider проверке.
