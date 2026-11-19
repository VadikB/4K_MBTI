# Admin 03 — обращение участника, 19.11.2026

## Результат и полномочия

Ветка `codex/admin-appeals-03` создана от `d17fba6432faf8567f4001369e9853671561a138` (main, 2.1.38), затем перенесена на `302bf576` (main, 2.1.39). Участник может отправить обращение о неточности данных, администратор организации видит его в карточке участника, берёт в работу и отправляет ответ. Участник читает ответ в «Мои оценки» после нового входа. Исходное сообщение, профиль и оценка не меняются ответом.

Пользователь прямо поручил «Реализовать Admin 03 и подготовить отдельный PR». Текст `TASK.md` внутри архива — требования и пример промпта, не самостоятельное разрешение на push/merge/deploy. 20.11.2026 владелец отдельно разрешил кандидат `2.1.40` по плану «остановить запись обращений старым API → применить схему → развернуть новый API → возобновить запись» с восстановлением через новую версию или совместимый hotfix без потери данных. `branch_push/pr/version_bump/Ready=true`, `merge/deploy/artifact_publish=false` до отдельного решения после полного CI.

## Источники и границы

- Архив `/Users/vadim_bogachev/Downloads/P4K_Admin_03_Appeals_2026-11-19.zip`, SHA-256 `a3c20e10509772bc263c5d6fd44983210dff49d876183e3317d4f0b7b240405d`: `TASK.md`, `reference/README.md`, `reference/SOURCE_IDENTITY.json` (edition 3, 19.11.2026). Offline reference — пример интерфейса, не runtime-норма.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`, `task-template.md`, `docs/architecture/product-4k/1.0/context.md`, `registry.md`, Change 01 README, task manifest и относящиеся к границам данных/повторов разделы ADR-002. Change 01 WORKING; M1 v1.4 FROZEN/CURRENT=NO. Предметных правил оценивания эта задача не вводит.
- Точки входа: `Api/acquaintance.py`, `Api/appeals.py`, `Api/routes.py`, `Api/database.py`, `Api/schemas.py`, participant onboarding/dashboard, карточка участника в Admin Organizations. Контракты Cycle/AS/Results и фиксированный профиль не изменяются. Обращение — административный процесс поверх данных назначения, не новый PM-04/PM-05 факт.
- Пробел: у старой таблицы уникальность `(user_id,organization_id,message)` и нет контекста назначения, владельца обработки или ответа. Данные старых строк о назначении объективно неизвестны; backfill не выполняется.

## Реализация и трассировка

| Требование архива | Контракт/данные | Код и проверка |
| --- | --- | --- |
| Одинаковый текст по разным назначениям | `scope_key` содержит assignment ref, revision и ID; старые строки получают `legacy` | `report_issue`, unique index; integration миграции |
| Один ответственный и передача после отзыва роли | атомарный `UPDATE` с проверкой прежнего владельца; проверка текущего права при каждом HTTP-запросе | `Api/appeals.py`, HTTP/integration и конкурентный тест |
| Ответ отдельно от обращения с автором/временем | `participant_data_issue_replies`, уникальный `issue_id` | повтор ответа возвращает прежнюю запись; HTTP/PG readback |
| Участник видит ответ после нового входа | owner-only GET по `user_id`, без административных полей | Dashboard, HTTP owner isolation |
| Неизвестный исход не теряет текст | readback по собственному обращению; форма ответа сохраняет ввод при ошибке | onboarding/admin UI |
| Права и данные другой организации | org admin + current membership, target member, owner-only participant API | HTTP 401/403/404; tenant integration |

## Миграция, совместимость, восстановление

Expand: добавляются `scope_key`, `assignment_ref`, `assignment_id`, `questionnaire_revision_id`, поля claim и отдельная таблица ответов. Старые сообщения, статусы и время сохраняются; `resolved` остаётся читаемым как «Обработано ранее». Старое уникальное ограничение снимается по определению из `pg_constraint` (его имя сокращается PostgreSQL), создаётся уникальность по `scope_key`. Повтор expand проверен.

После снятия старого уникального ограничения прежняя версия API с `ON CONFLICT(user_id,organization_id,message)` не может принимать новые обращения. Поэтому выпуск требует остановить старые writers до применения expand и развернуть новый API до возобновления записи. Штатный test deploy на переходе `2.1.39 → 2.1.40` явно останавливает старый service до запуска нового. Если после запуска могла примениться схема, отказ health-check сохраняет новый checkout и не возвращает несовместимый код 2.1.39. Восстановление — вернуть проверенную новую версию или выпустить совместимый hotfix записи, сохранив расширенную схему и все обращения; при сбое может потребоваться ручное восстановление доступности test. Down migration и удаление записей запрещены. Владелец явно допустил этот порядок 20.11.2026; фактическая миграция и deploy ещё не выполнялись.

## Проверки и состояние

- `git diff --check` — PASS.
- `npm run lint:js`, `npm run build:web` — PASS; сборка `web/dist` включена в diff.
- `node --test tests/frontend/*.test.mjs` — 476 PASS после `npm ci --offline` по lockfile. Первые 4 FAIL локализованы: 3 из-за нового параметра фильтра в изолированном VM тесте (исправлено), 1 из-за устаревшего `node_modules` вне worktree (переустановлено по lockfile).
- `pytest -m 'not integration and not e2e and not llm'` — финальный повтор после переноса на 2.1.39 с разрешённым `ps`: 1299 PASS, 698 deselected. Первый sandbox-прогон: 1290 PASS и 9 FAIL только из-за запрета `ps`; адресный повтор `tests/unit/test_synthetic_limits.py` — 19 PASS.
- `pytest -m e2e tests/e2e` — 218 PASS, 15 deselected.
- `TEST_DATABASE_URL=…p4k_admin03_test… pytest --run-integration` на локальной изолированной PostgreSQL 15 — 7 PASS: миграция старых строк, повторы, HTTP→PG, tenant/owner isolation, concurrent claim, отзыв роли. CI проверит PostgreSQL 16.
- `npx playwright test tests/browser/admin-appeals.spec.mjs` — 2 PASS: UI карточки, claim, потерянный ответ после commit и readback, отказ сохранения без потери текста. Визуально проверены снимки 1440 и 390 px с проектными CSS; поля и действия не обрезаны.
- `TEST_DATABASE_URL=…p4k_admin03_test… ADMIN03_PYTHON=…/.venv/bin/python node tests/browser/admin-appeals-live.mjs` — PASS на изолированной PostgreSQL 15: форма участника отправила обращение через реальный POST, карточка администратора выполнила claim и reply через реальные HTTP routes, таблицы показали `answered` и отдельный ответ с автором, новая браузерная сессия участника увидела ответ; чужой участник получил 403. GET готовности знакомства в стенде заменён синтетическим fixture только для входа в форму. Временный HTTP сервер и схема создаются тестовым harness и удаляются после прогона. Реальные LLM и внешняя почта не применимы.
- Draft PR #256 на `96186c01`: быстрый CI frontend/pytest — 2 PASS, 4 ожидаемых SKIP (full-verification и deploy для draft).
- 20.11.2026 `npm run ready:prepare -- --candidate 2.1.40` — PASS на актуальной `origin/main=302bf576`; повтор `node --test tests/frontend/*.test.mjs` — 476 PASS, `npm run lint:js`, `git diff --check` — PASS. Release commit и полный CI Ready фиксируются далее.
- Ready CI на `e4dd6e2d`: frontend, pytest, integration и четыре runtime browser shards — PASS; fast browser — FAIL (367 PASS, 7 FAIL, 41 SKIP). Все семь сбоев — строгие синтетические fixture, которые ещё не знали новый GET `/users/8/acquaintance/issues`; продуктовый код не падал. В трёх fixture добавлен ответ `{items: []}`. Адресный повтор `npx playwright test tests/browser/f05-f09-next-layout.spec.mjs tests/browser/postw02-cabinet.spec.mjs tests/browser/postw02-qa-state.spec.mjs --reporter=line` — 11 PASS. Полный CI нового head обязателен.
- Ready CI на `42b8dbf0`: frontend, pytest, integration, fast browser, четыре runtime shards и `full-verification` — PASS; PR mergeable/clean на base `302bf576`. После человеческого ревью обнаружен несовместимый code-only rollback штатного test deploy; скрипт скорректирован для точного перехода `2.1.39 → 2.1.40`. `sh -n scripts/deploy_test_remote.sh` и 24 адресных unit-теста deploy/asset retention — PASS. Новый полный CI обязателен после коммита этого исправления.

## Приёмка и продолжение

- [x] Старые обращения читаются без выдуманного назначения; один и тот же текст допустим в разных назначениях.
- [x] Текущие права проверяются на сервере; одновременно обращение получает один владелец.
- [x] Ответ и повтор сохраняются отдельно, автор/время не переписываются; участник читает свой ответ после смены сессии.
- [x] Визуальный и browser путь карточки с потерянным ответом; HTTP→PG проверен отдельно.
- [x] UI→HTTP→PG обращение в двух браузерных сессиях на изолированной БД; синтетический GET готовности использован только для входа в форму.
- [x] Отдельный draft PR #256 и быстрый CI для head `96186c01`; после документального коммита CI повторяется.
- [x] Решение владельца по миграции и версии `2.1.40` получено 20.11.2026.
- [ ] Полный CI точного release head после Ready.

Изменённые предметные артефакты: нет. Отношение «M1 → контракт → код» ограничено инвариантом неизменности фиксированного профиля и оценки; Admin 03 не претендует на соответствие всего продукта M1. Следующая задача зависит от решения о миграции и успешного полного CI; merge/deploy не входят в данный этап.
