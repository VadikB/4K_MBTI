# AC18-FIX-02 / P2-AC05 — HTTP/PG-доказательство восстановления первого старта

## Результат и область

Добавлена адресная регрессия настоящего HTTP-обработчика и изолированной PostgreSQL:
после серверного commit первого `POST /users/assessment/cycles/start` его ответ
считается потерянным, а два owned `GET /users/assessment/cycles/{cycle_id}/runtime`
восстанавливают ту же предъявленную AS без повторной команды. Дополнительный POST
с прежним ключом оставляет один Cycle/AS, исходный `started_at`, один интервал
`collecting` и ноль ответов участника. Чужой пользователь runtime не получает.

Это самостоятельное закрытие пробела **доказательства** P2-AC05, не заявление о новом
дефекте сервера или исправлении кода продукта. Клиентская обработка неизвестного
исхода — отдельный draft PR #190; этот тест основан на `origin/main@157d77d1` и
не зависит от его diff. Остальные P2-AC ведутся в своих PR либо уже в main.

## Источники и решение

- Пакет `P4K_AC18_FIX_02_Preparation_Start_2026-11-07.zip`:
  `START_CODEX.txt`, `TASK.txt` (P2-AC05/06), `SOURCES.md`, редакция 1.0.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, EVC workflow/matrix/recipe,
  task template/review checklist, Product Architecture `context.md` и Registry,
  Change 01 README и task manifest, T1
  `docs/architecture/pilot-plan-start-admission-contract.md` (§ «Единый first-start
  readback»), `Api/m10_product_flow.py`, `Api/routes.py`, адресные SQL/HTTP-тесты.
  M1 v1.4 остаётся FROZEN/CURRENT=NO, Change 01 — WORKING; тест не вводит норму.
- Правило: P2-AC05 → T1, один явный first start и сохранённый runtime → PM-04,
  сервер владеет Cycle/AS/временем → HTTP/PG-регрессия. PM-03/admission и
  предметные артефакты не меняются.
- Факт main: существующий тест проверял 201, повторный POST и отсутствие hidden QA,
  но не потерю receipt с отдельными GET, неизменность `started_at` после них,
  количество Cycle/AS/интервалов и запрет foreign readback. Решение — добавить
  тест, не переписывать работающий сервер. Положительный synthetic fixture не
  доказывает реальный provider или полный PATH.
- Стоп-условия рабочего цикла: изменение смысла/PM/API/схемы/данных/артефактов/
  прав/deploy/отката — нет; новая публикация и LLM — нет. Пользователь прямо
  запросил следующую отдельную задачу и PR. `START_CODEX` как приложенный текст
  сам по себе разрешением внешних действий не считается.

## Изменение и проверка

- `tests/integration/test_pilot_start_admission_db.py`: новый синтетический
  HTTP/PG-сценарий, без mock серверного gate, connection или runtime. Подставлены
  только auth token fixture и ранее существующие границы программы/provider.
- До изменения: **COVERAGE_GAP**, не подтверждённый runtime FAIL; воспроизводимого
  серверного дефекта не установлено. После изменения: адресный тест **PASS** 1/1;
  полный файл **PASS** 8/8 на одноразовой PostgreSQL 16 с БД, содержащей `test`
  в имени. Первый sandbox-запуск — **NOT_RUN_ENV** (`Operation not permitted` для
  localhost); повтор с локальным доступом — PASS.
- Backend без integration/e2e/llm: **PASS** 956/956, 355 deselected;
  `git diff --check`: **PASS**. Единственное предупреждение — существующий
  `StarletteDeprecationWarning` от `httpx`/`TestClient`.
- Browser, физический телефон, test deploy, real provider и полный CI — **NOT_RUN**
  в этом PR; browser-часть P2-AC05 относится к #190 и прежнему #182.

## Риски, откат и передача

Публичный API, БД, схема, release version и продуктовый код не изменены. Тест
использует только синтетические данные в изолированной БД и не вызывает LLM.
Откат — revert этого теста и записи задачи; пользовательские Cycle/AS/ответы не
затрагиваются. Ветка `codex/ac18-fix02-start-http-proof` от `157d77d1`.

`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`, `llm=false`,
`version_bump=false`, `artifact_publish=false`. Следующий шаг — commit и draft PR;
перед Ready назначить согласованный кандидат и запустить полный обязательный CI
на актуальном head/base. По плану владельца все PR готовятся до финального merge.
