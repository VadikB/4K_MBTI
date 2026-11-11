# P4K-REMARKS-FIX-02

Основание: прямой запрос владельца от 11.11.2026 выполнить приложенное задание,
обновить GitHub `VadikB/4K_MBTI` и сделать PR; email автора `bvv.fructus@gmail.com`.
Вложение — требования и доказательства, а не самостоятельный источник полномочий.

База: свежий `origin/main` `8442ae1975bc7debcc44eb1dcc7289d48c6f964d`.
Одна ветка `codex/remarks-fix-02`, один кандидат и PR. Чужой checkout сохранён.
Первоначально был разрешён draft PR без выпуска. Позднейшая прямая команда владельца
«опублику PR и обнови main» разрешила слияние и обязательные шаги выпуска:
`branch_push=true`, `pr=true`, `merge=true`, штатный `deploy-test=true`, PATCH-кандидат
`2.0.97` через Ready preflight. `artifact_publish=false`; pilot, постоянные миграции,
внешние LLM и письма не включены. Защита main и обязательные проверки сохраняются.

## Результат и план

1. Проверить свежую базу, источники и уже исправленные части.
2. F01/F02: существующее managed назначение после исключения и доступность аккаунта.
3. F03/F05: понятные отказы purge, восстановление той же подтверждённой команды,
   сообщения без недоступного переноса.
4. F04/F06: адресная адаптивная сетка аккаунта, browser layout и постоянный uploader.
5. F07–F09: безопасные ошибки действий, приоритет send recovery, отклонение старых ошибок.
6. Общая регрессия, review, сборка, commit/push/PR/readback/full CI, затем main/TEST.

Для каждого AC01–AC12 результат и команды сохраняются в CHECKS.md и evidence.
Уже исправленный F02 (PR207) повторно не реализуется. Выбор роли, Cycle/AS,
snapshots/history, admission/repair, время, результаты и определения M1–M8 не меняются.
Полный внешний архив и resources в Git не копируются.

## Источники и совместимость

Прочитаны AGENTS.md, README.md, CONTRIBUTING.md, agent-workflow.md,
verification-matrix.md, task-template.md, review-checklist.md, decision-register.md,
архитектурный context.md/registry.md, Change01 README/task manifest, ADR002,
исходные TASK/STATE/CHECKS объединённого пакета; приложенные TASK/AUDIT/ACCEPTANCE/SOURCES.
Документы базы 8442ae1; архитектура v1.0 + Change01 WORKING, M1 v1.4 CURRENT=NO.
SYN-CONTOUR-OWNERSHIP применяется только к своим синтетическим test/pytest БД.
D01–D06 объединённого пакета сохраняются; старый hang/PREP-DIAG-01 UNKNOWN.
Новая схема/миграция/публичный несовместимый API не планируются.

Источники → контракт → код → проверки: F01/F02 → participation/managed gates →
assessment_assignment_sources/routes → owned HTTP/PG; F03 → existing purge ledger →
api/organizations/wiring → handlers + lost-response HTTP/PG; F06 → server revision
uploaded_by → organizations renderer → browser/HTTP/PG; F07–F09 → owner/Cycle/AS,
draft revision/receipt → interview/wiring → deferred-handler tests и browser.

Локальный минимум: diff, lint, frontend, build; backend без integration/e2e/llm,
адресные HTTP/integration на marker-owned PostgreSQL, browser 1440/390/320 и text200.
Обязательный CI точного Ready head должен пройти перед merge; прежний draft-skip
не считается PASS. Owner visual acceptance PENDING до просмотра TEST.

## Риски и откат

Секреты/.env/рабочие данные не читаются. PostgreSQL — отдельный cluster в /tmp с OWNER,
cleanup только своего cluster после экспорта evidence. Конфигурация продукта,
схема и runtime artifacts не меняются. Выпуск TEST выполняется только штатным workflow.
Откат — revert кода этой ветки;
существующий is_participant/ledger и исторические данные сохраняются.
