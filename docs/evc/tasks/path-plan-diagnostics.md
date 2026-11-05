# PATH-PLAN-01 — бесплатная сверка и сохранение диагностики

## Действующее продолжение05.11.2026

После остановки владелец разрешил только проверку прежнего основания и подготовку
ограниченного пилота на существующих девяти Cases. Полный M2=61 сохраняется;
расширение каталога исключено. Промежуточный незакоммиченный выбор расширения
сохранён как история, не методологический допуск. Новое поручение и план работ:
[PATH-PILOT-01](path-pilot-admission-proposal.md). Исторические checkpoints ниже
не отменяют эти границы. Никаких LLM/публикаций/изменений постоянной БД/merge/deploy.

Дата: 05.11.2026. Основание: продолжение владельца «идем дальше» после одного
контролируемого PATH и предложения бесплатной сверки READY/LIMITED.

## Результат и границы

Установить фактическую семантику планов и расхождение PM-04/API/UI/runner;
сохранять безопасный readback причин и состава плана до штатного owned cleanup.
Это не повтор PATH и не разрешение старта с LIMITED. Код продукта, validator,
методология, цели, опубликованные пакеты, prompts, admission и repair не меняются.
Новых LLM-вызовов нет. Восстановление БД вне задачи, permanent DB защищена.

Ветка `codex/path-plan-diagnostics` от отчётного b5b7ba34c66f8bb2fff97d78730bb81661549e9a;
runtime base и свежий origin/main — 2dc98c6b5b2637c6c505a90686e82f5e4274e763 / 2.0.64.
Предыдущая ветка, ZIP и первичные receipts не переписываются. Три чужих untracked
документа root main сохранены. Единственная область кода — tests-only collector.

## Источники и решения

Прочитаны/повторно использованы неизменённые README.md, CONTRIBUTING.md, AGENTS.md,
EVC workflow/matrix/recipe/review/template, архитектурный context/Registry,
Change 01 README/источник И-2/3/6, task SourceSet manifest, ADR-002 C-24/C-34/C-46.
M1 v1.4 FROZEN/CURRENT=NO; M7 v1.3, original SHA-256
50a0d53a3aaf6258957ecc6d9e89f27d922bfbe4cd55668185d475c87f4e2f10,
derived §§2.2/4.1–4.6/5.1. M2 K1/K3 v1.1, K2/K4 v1.0; M5 v1.1.
Также прочитаны M7 Cycle Planning v1 (draft QA), M7 Task05, исходная PATH 1.3,
предыдущий отчёт и VERIFY, реальные PM-04, HTTP start, acquaintance/UI, admin stage,
collector, persistence/cleanup и адресные unit/integration tests.

Трассировка: M7.2.2/4.3/5.1 → frozen plan/допустимый маршрут PM-04 →
`Api/m7_cycle_planner.py`, `Api/m10_product_flow.py`, `Api/routes.py`,
`Api/acquaintance.py`, `web/js/onboarding-flow.js` → tests-only receipt collector
и регрессии. Сохраняются различия планового и фактического покрытия и admission AS.

Пробел: явного технического контракта admissibility LIMITED для опубликованной
specialist_pilot@1.1 и предварительного обоснования сокращённого состава не найдено.
M7 сохраняет известные ограничения условных ветвей, но это не автоматическое
разрешение любого заведомо неполного начального маршрута. Технический QA Task05
не является методологическим допуском пользовательского пилота.

Стоп-условия 1/4: ДА для изменения старта/ослабления READY — требуется решение
владельца допустимого состава; зависимая реализация остановлена. Для независимого
экспортёра 2/3/5/6/7/8: НЕТ — API/схема/нормы/права не меняются, только owned
синтетические данные, безопасный откат и бесплатные проверки в текущих границах.

## План

1. DONE: read-only сверка статусов и источников; полный PATH по-прежнему не PASS.
2. DONE: регрессии и additive safe plan export: refs/revision, сохранённый checksum
   и его readback, отдельный checksum диагностической проекции, targets/gaps,
   route/catalog eligibility/reasons. Без UserContext/ответов/prompts/credentials.
3. DONE: новые regressions до/после, backend, HTTP, Node receipt/validator,
   actual SQL на новой isolated test DB, persistence перед owned cleanup, diff/review.
4. DONE техническая передача и решение владельца по составу. Не менять
   исторический отрицательный receipt и PREP-DIAG-01 (root_cause=UNKNOWN).

Все release flags false: branch_push/pr/merge/deploy/version_bump/artifact_publish.
CI для новой ветки NOT_RUN; main/test отдельно остаются выпущенным 2dc98c6.

## Совместимость и откат

Receipt расширяется полями, старые plan refs/status/checksum сохраняются. Hash
диагностической проекции не сравнивается с hash другого объекта полного плана.
Raw plan/profile не передаются: allowlist сохраняет необходимые технические поля,
неизвестные/чувствительные поля исключаются. Отсутствующий readback — UNKNOWN,
не пустой достоверный план. Неполнота исторического evidence не исправляется задним числом.
Синтетические QA fixtures не подтверждают human review или допуск программы.
Откат — revert только tests-only export/test changes, без изменения БД/истории.

## Checkpoint по запросу статуса 05.11.2026

Реализован additive tests-only `plan_receipt` и его подключение к actual collector;
политика READY/admission и продукт не изменены. Новые unit regressions до реализации
7 FAIL (отсутствовал helper), после — 7 PASS; совместно с исходными harness suites
45 PASS. Node persistence/validator 38 PASS. Полный backend:
`/Users/vadim_bogachev/Developer/4K/.venv/bin/python -m pytest -m 'not integration and not e2e and not llm' -q`
→ exit0, 770 PASS / 324 deselected, 102.21s. Один существующий warning FastAPI/httpx.
Эти результаты применимы к текущим Python/Node files, не к будущим изменениям.

Следующий шаг не выполнен: actual SQL/integration и persistence→owned cleanup.
Локальный libpq содержит initdb, но не postgres; попытка initdb не создала кластер.
Docker socket недоступен в sandbox. Это ограничения локального окружения, не FAIL
продукта и не выполненная integration. Для проверки доступен прежний isolated
PostgreSQL-контур; рабочая БД сервиса не используется. HTTP и итоговый review ещё
NOT_RUN. Ветка пока uncommitted поверх b5b7ba3; нет PR/нового CI/deploy.

Сверка выявила разные требования: admin projection и runner READY-only;
participant UI считает готовым непустой маршрут с двумя положительными временами,
server start не содержит отдельного запрета LIMITED. Подтверждённого решения,
разрешающего этот неполный pilot состав как допустимый начальный маршрут, не найдено.
Ослабление гейта и изменение продукта остановлены до адресного решения владельца.
Исторический run96abd1… остаётся отрицательным; PREP-DIAG-01 UNKNOWN.

Продолжение 05.11: добавлены явные UNKNOWN/PARTIAL/missing fields и проверка
совпадения статуса таблицы с revision без изменения допуска. Адресные Python48
и Node38 PASS. Actual SQL fixture читает вторую сохранённую revision, не initial.
`RUN_FREE.py` в evidence использует только существующий test_stand: provider disabled,
из окружения исключены ключи и рабочая DB-конфигурация; отдельная owned-БД, реальные
SQL regressions, fsync/readback через общий Node helper и owned destroy только после
доказанной выгрузки. Это воспроизводитель проверки, не новый runtime подготовки.
Изменённые Python требуют повторного backend/HTTP на окончательном implementation.

## Итог 05.11.2026

Implementation1bc9d36834262ee9ad4591227d5ec876fea8e648. Backend773 PASS/324 deselected,
HTTP108 PASS/12 deselected, targeted Python48, Node38; реальный PostgreSQL43 PASS.
Run43d5ca0ac39e4b098ef5e7ea4d8829bc: provider disabled, LLM0, latest revision2
readback + durable export до cleanup, exact owner database_absent/state_absent,
force=false, тот же receipt после cleanup. Primary JSON/logs переданы allowlist.
Отчёт: [результат и остаток](../reports/path-plan-diagnostics.md).

Tests-only диагностика завершена, ограничения admission/READY сохранены. Для
следующей работы владелец 05.11.2026 явно выбрал: «Сохранить полный M2; отдельно
доработать покрытие каталога». Выбор закрыт; новая постановка
[CAT-COVERAGE-01](catalog-coverage-01.md) сохранена как NOT_STARTED, не исполняется
внутри этой доработки. Целевой состав, READY/admission не ослабляются. Исторические
PATH FAIL_PLAN_NOT_READY и PREP-DIAG-01 UNKNOWN не переклассифицируются.
Main/test остаются2dc98c6 / 2.0.64 (post-cleanup readback ready/active); новый
CI NOT_RUN, branch local-only, все release flags false. Откат/данные без изменений.
