# AC18-FIX-02 / P2-AC05 — безопасный readback неизвестного первого старта

## Результат и область

После потерянного ответа `POST /users/assessment/cycles/start` временный отказ
проверочного GET не объявляется отказом старта. Клиент сохраняет тот же
`idempotency_key` в `sessionStorage` для конкретного Cycle. Следующее явное
действие «Проверить состояние», в том числе после reload, только читает owned
runtime. Если первая AS уже предъявлена, открывается сохранённое состояние без
нового POST. Если сервер достоверно показывает ещё `admitted` AS, отдельно
появляется явное «Повторить старт» с прежним ключом. Неизвестный/чужой runtime
не подтверждает старт. HTTP 503 на POST также считается неопределённым исходом
до readback, а не доказанным отказом.

Затронут только клиент первого старта: методология, admission, repair,
серверный контракт, схема БД, опубликованные пакеты и snapshots не меняются.
P2-AC06 (повторная серверная проверка scope/admission) уже реализован и проверен
на `origin/main` тестами `test_pilot_start_admission_db.py`; этот PR его не
переписывает. P2-AC01–04 и P2-AC07/08 ведутся в отдельных PR либо уже слиты.

## Источники и решение

- База: `origin/main@157d77d1` (2.0.76), сверена с GitHub main 08.11.2026;
  ветка `codex/ac18-fix02-start-unknown-readback`, отдельный worktree.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, EVC workflow,
  verification matrix, artifact recipe, task template, review checklist,
  Product Architecture `context.md`/Registry, Change 01 README и адресные И-2/6/7,
  task SourceSet manifest, M7 v1.3 адресно, pilot first-start contract,
  `START_CODEX.txt`/`TASK.txt`/`SOURCES.md` пакета ред. 1.0,
  `web/js/product-cycle-start.js`, `web/js/screens/onboarding.js`,
  `web/js/screens/interview.js`, `Api/m10_product_flow.py`, `Api/routes.py`
  и адресные frontend/browser/HTTP-PG тесты.
- M1 v1.4 — FROZEN/CURRENT=NO; Change 01 WORKING, M7 v1.3 выбран в task
  SourceSet. Их статусы не меняются. Глоссарий WORKING из `SOURCES.md` не
  используется для введения новой нормы; правка только технического readback.
- Прослеживаемость: P2-AC05 и принятый T1 → один явный первый старт и
  авторитетный runtime → `startPreparedProductCycle` (PM-04, клиентский
  транспорт; сервер владеет Cycle/AS) → unit и browser регрессии. Данные
  участника и предметные значения в `sessionStorage` не записываются: только
  idempotency key, привязанный к ID Cycle.

| ID | Принятое поведение | Факт на main | Решение |
| --- | --- | --- | --- |
| P2-AC05 | Потерянный POST → readback, неизвестный исход не становится отказом; reload не создаёт новый старт | GET 503 пробрасывался как ошибка GET; после reload создавался новый ключ | Исправить здесь |
| P2-AC06 | Устаревший READY не обходит scope/admission | `start_prepared` повторно проверяет assignment/profile/readiness под lock; HTTP/PG негативные тесты есть | Уже исправлено; не дублировать |

## Проверки и ограничения

- До правки `node --test tests/frontend/product-cycle-start.test.mjs`: **FAIL**
  на GET 503 после потерянного POST (`ApiResponseError` вместо `AssessmentStartUnknown`).
- После правки адресные unit: **PASS**, 7/7; полный frontend:
  `node --test tests/frontend/*.test.mjs` — **PASS**, 154/154.
- `npm run lint:js` — **PASS**; `npm run build:web` — **PASS**;
  `git diff --check` — **PASS**.
- Синтетический Playwright на реальном UI и mock HTTP: прежний lost-POST и
  новый POST lost → GET 503 → reload → read-only проверка → AS — **PASS**, 2/2.
  Первый запуск нового теста в sandbox: **NOT_RUN_ENV** (`listen EPERM`),
  разрешённый localhost-прогон сначала выявил неполный test bootstrap и
  неверное ожидание общего числа GET; fixture исправлен, повтор PASS.
- Backend/БД/real-provider не меняются. Доказательство SQL допуска/двойного
  старта из `tests/integration/test_pilot_start_admission_db.py` применимо к
  неизменённому серверу базы, но не объявляется новым прогоном этого SHA.
  Реальный LLM, физический телефон, стенд и CI — **NOT_RUN**.

## Риски, откат и передача

Сервер по-прежнему окончательно проверяет право и допуск: локальный READY не
даёт обхода. Если `sessionStorage` недоступен, текущий readback остаётся, но
восстановление ключа после reload не гарантировано; серверная идемпотентность
и повторная проверка допуска сохраняются. Дополнительный GET происходит
только при ранее неопределённом старте. Данных/миграций/конфига нет.
Откат — revert клиентского адаптера, тестов и `web/dist`; сохранённые Cycle,
AS и ответы не удалять.

Локальный результат подготовлен, `branch_push=false`, `pr=false`, `merge=false`,
`deploy=false`, `version_bump=false`, `artifact_publish=false`, `llm=false`.
Следующий шаг: commit, отдельный draft PR после разрешения владельца; перед
Ready назначить согласованный номер кандидата после ранее открытых PR и пройти
полный CI на актуальном head/base. План владельца — подготовить все PR до
финального последовательного merge.
