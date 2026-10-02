# M6-A Доказательная цепочка одной AS

Статус: **COMPLETE — technical QA scope**; локальные проверки PASS.
По решению владельца от 02.10.2026 задание завершено без ожидания экспертных заключений.
Provider smoke и методологическая приёмка GC — NOT_RUN, пользовательский допуск отсутствует.
Это первая часть задачи 3 очереди из постановки от 02.10.2026, не новая параллельная задача.
Основание: пользователь согласовал завершение задачи 1; [контракт](../../architecture/m6-a-contracts.md).

## Результат и область

Реальный потребитель сохранённого C-45 строит Fragment/BS/Evidence/EB через существующий
AI-контур, сохраняет immutable revision и восстанавливает доказательные связи по правам.
Один независимо принимаемый PR. IA/C-54/Score/M7/Report в него не входят.
M6 — самостоятельный PM-05, не часть M5 semantic_decision.

## Файлы и шаги

1. Api/m6_contracts.py и Api/m6_input_resolver.py: валидированные типы, адаптер C-45,
   frozen refs, M2, безопасная проекция; tests/unit/test_m6_input_resolver.py.
2. assessment_definitions/prompts/m6_evidence/v1/ и Api/m6_package.py:
   manifest/loader/snapshot по контракту; tests/unit/test_m6_package.py.
3. Api/m6_evidence_service.py: реальный AI adapter, semantic output и техническая
   валидация цепочки; tests/unit/test_m6_evidence.py. При выделении общего AI executor
   регрессия потребителей Api/m5_rule_engine.py обязательна.
4. Api/m6_repository.py, Api/m6_worker.py, expand schema в Api/database.py:
   request/attempt/revisions, lease и recovery; tests/integration/test_m6_evidence_db.py.
5. Api/routes.py: отдельное действие существующего QA-контура и авторизованное чтение;
   tests/e2e/test_m6_evidence_http.py. Новый Prompt Lab не создаётся.
6. tests/llm/test_m6_evidence_smoke.py: отдельный синтетический provider smoke.
   Контрактные fixtures не называются утверждёнными GC.

## Приёмка

| ID | Проверка и свидетельство |
| --- | --- |
| T-A1 | Подмена checksum/schema/AS/Cycle/M2 и неизвестная цель отклоняются до AI; unit + DB |
| T-A2 | quote/span восстанавливают исходный пользовательский Turn; Unicode, границы, системное авторство; unit |
| T-A3 | Пустой EB сохраняется/read-back без вымышленных Fragment/BS и без IE/L0; DB |
| T-A4 | Повтор/конфликт payload, concurrent workers, истечение lease и crash до/после commit дают один принятый эффект; DB |
| T-A5 | Смена текущих prompt/M2/Case/profile не меняет frozen обработку; missing frozen input явно отклонён; unit + DB |
| T-A6 | timeout/invalid JSON/невалидные ссылки сохраняют attempt failure, без оценочного результата; fake gateway + DB |
| T-A7 | HTTP права на создание и чтение; чужой ID не раскрывает Dialogue/trace; атомарный read-back цепочки |
| T-A8 | Реальный adapter на синтетическом входе, provider/model/schema/prompt/response trace и фактический статус; llm отдельно |

Запускать адресные тесты, затем npm run test:backend, npm run test:backend:http,
TEST_DATABASE_URL=… npm run test:backend:integration на isolated test/pytest DB,
валидацию файлов/ссылок/checksum и git diff --check. URL в отчёте редактировать.
CI frontend/pytest обязателен перед merge. Реальный smoke требует отдельного бюджета/
конфигурации; если не выполнен — NOT_RUN. QA правильности атрибуции, авторства,
Simple/Composite/пустого EB — независимые экспертные ожидания по M6.9, с указанием
области и трёх повторов обязательных GC. Технический PASS не равен методологической приёмке.

## Владельцы и зависимости

Техническая реализация Evidence/EB — один модуль M6-A; IA добавляется к нему задачей 4.
Общая основа владеет F01/F02 и исправлениями времени/закрытия, основным маршрутом.
Не переносить их в этот PR. До schema изменений проверить текущий HEAD и активные
изменения владельца общей основы, чтобы не создать конкурирующие таблицы.
Нет обязательного материала → блокируется конкретный handoff. Нет GC → ограничена
методологическая приёмка. Полный M7/M8 и M0 не блокируют технический QA этого среза.
Продуктовый допуск требует отдельной интеграции основного маршрута и допуска Cases.

## Миграция, риски и откат

Только expand: новые таблицы M6. Нет TRUNCATE/backfill, старые данные не превращаются
в Evidence M6. Конфиг нового механизма explicit QA, не default. Публичные legacy API
не меняются. LLM без открытой транзакции; лимит контекста не разрешает усечение Dialogue.
PII/секреты не передаются, QA smoke синтетический; серверные права проверяются при чтении.
Откат — остановить новые requests/worker, сохранить таблицы/revisions и совместимый reader.
Fallback к старому evaluator запрещён. До запуска миграции проверить этот план на test DB.

## Передача

База проектирования dd3d2cadd90a31e3b7b3141ed6a0984afbd11ef6.
Шаги 1–5 реализованы; для шага 6 добавлен opt-in llm smoke, но реальный вызов NOT_RUN.
Фактические проверки и ограничения — ниже. Прочитанные источники, решения и проверки
документального шага — в [отчёте задачи 1](m6-task01-completion.md).

## Отчёт реализации от 02.10.2026

Основание: пользователь «идем дальше» после задачи 1. Ветка
codex/m6-task01-contracts, HEAD dd3d2cadd90a31e3b7b3141ed6a0984afbd11ef6,
результат находится в рабочем diff, нового commit/PR нет.

Прочитанные источники задачи 1 переиспользованы без изменения; дополнительно
проверены действующие M5 handoff/storage, M2 package/manifest, gateway, schema setup,
HTTP auth, unit/integration fixtures и tests/conftest.py. Нормы не расширялись.
Schema expand и QA API реализованы внутри согласованной карточки; удаления данных,
миграции legacy в M6, изменения состояний PM-04 и публикации CURRENT не выполнялись.

Изменены Api/database.py (additive schema), Api/routes.py (QA HTTP), main.py (worker);
добавлены Api/m6_contracts.py, m6_input_resolver.py, m6_package.py,
m6_evidence_service.py, m6_repository.py, m6_worker.py. Prompt/manifest находятся
в assessment_definitions/prompts/m6_evidence/v1. Тесты: unit/test_m6_evidence.py,
e2e/test_m6_evidence_http.py, integration/test_m6_evidence_db.py,
llm/test_m6_evidence_smoke.py. Документация задачи 1 и её источники остаются в том же
рабочем дереве; это не новые изменения runtime данного шага.

Прослеживаемость: M6.1.3/Change01 C-45 → resolver/criteria/snapshot → DB tests
real_c45, unknown_schema; M6.2–5 → contracts/evaluate/prompt → unit spans/author/refs,
DB empty/nonempty read-back; Change01 И-6 → request/attempt/lease/revisions →
DB failure_retry, concurrent_claim, snapshot_survives_source_change, restart_recovery;
LU-05.6 → superadmin HTTP → e2e all_endpoints_require_admin.
T08 в целом не закрыт: IA относится к следующему шагу. T11/12 не реализовывались.

Команды и результаты:

- npm run test:backend — PASS, exit 0, 250 passed.
- npm run test:backend:http — PASS, exit 0, 24 passed.
- TEST_DATABASE_URL=postgresql://pytest@127.0.0.1:55487/agent4k_m6_pytest npm run test:backend:integration — PASS, exit 0, 42 passed.
- После добавления непустого read-back повторён только затронутый набор:
  .venv/bin/python -m pytest --run-integration -q tests/integration/test_m6_evidence_db.py
  с тем же isolated TEST_DATABASE_URL — PASS, exit 0, 9 passed.
- git diff --check и compileall шести модулей M6 — PASS, exit 0.

PostgreSQL 15.16 создан во временном отдельном кластере /tmp/agent4k_m6_pytest_pg,
localhost:55487, БД agent4k_m6_pytest; данные синтетические, тесты удаляют свои схемы.
Это не рабочая/production БД. CI использует PostgreSQL 16; CI на данном diff NOT_RUN.
Начальная попытка initdb через libpq не имела postgres binary; полноценный
postgresql@15 потребовал разрешения sandbox на shared memory. Первый порт был занят,
поэтому использован отдельный 55487; существующий сервер не затрагивался.

Два промежуточных test failures локализованы и исправлены: тест пытался менять
неизменяемый M5 snapshot; тестовый rollback сбрасывал search_path. Защиты runtime
не отключались. HTTP-тест сначала не учитывал общий /users prefix, затем исправлен.

Реальный LLM/provider smoke T-A8 — NOT_RUN: нет отдельного согласованного бюджета
реального прогона. Добавленный тест требует RUN_M6_PROVIDER_SMOKE=1 и маркер llm.
Экспертные GC/три прогона и Reliability — NOT_RUN; fixtures не являются эталонами.
Основной пользовательский маршрут и F01/F02 не изменялись. Новый UI не добавлялся;
операция доступна через авторизованный QA HTTP. Содержательная пригодность, пилот,
CI/deploy и выпуск не заявляются.

Review: фрагменты адресуют реальный пользовательский текст; разные AS/Cycles не
сливаются; пустой EB не создаёт IE/L0; сбои сохраняются отдельно; старый технический
C-54 не меняет смысла; предметный prompt вынесен; новые snapshots immutable;
LLM вне транзакции; права применяются на POST/GET, trace не выдаётся обычным status.
Стоп-условий для реализованного QA среза не выявлено; новый допуск реальных данных
или публикация требуют отдельного решения. ART-04 целиком не закрывается.

Откат: отключить вызов нового POST и запуск M6 worker, дождаться/остановить активные
попытки, сохранить совместимый reader и новые таблицы/историю. Старый evaluator не
подставлять. Новые запросы создаются только явным QA действием; пользовательские
оценки на новый механизм не переключены. Секреты и данные сред не читались.
Текущая техническая задача завершена. Методологическая приёмка кандидатов и отдельная
реализация IA/C-54 относятся к будущим задачам. Перед расширением проверить актуальный
main и решения общей основы.
