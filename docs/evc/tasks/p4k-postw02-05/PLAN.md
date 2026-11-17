# P4K-POSTW02-05 — неотправленный ответ

Основание: прямое поручение пользователя «запусти 5 задание… reference, используй его»,
17.11.2026. Приложенные P4K_POSTW02_05_Unsent_Draft.txt и REFERENCE_POSTW02_04_05.txt
задают требования; сами по себе не являются отдельным разрешением внешних операций.
Рабочая ветка codex/p4k-postw02-05; исходный свежий main
4170fc0d358708ab55e74264b666ef8a02c544ed, версия 2.1.21. 04 уже в базе.
03/PR231 на старте OPEN; пользователь выполняет его merge параллельно и прямо
попросил продолжить 05, затем перепроверить сочетание. Старые checkout не меняются.

## Прочитанные основания

AGENTS.md; README.md; CONTRIBUTING.md; docs/evc/{agent-workflow,verification-matrix,
artifact-recipe,review-checklist,decision-register}.md; контекст и Registry Product4K;
Change01 WORKING 01.10.2026 И-2/4/6 (source.md), manifest SourceSet2026-10-01;
M7v1.3 FROZEN §§5.3–5.6,6.3 (derived/M7-v1.3.md); глоссарий WORKING30.09
по сохранённому извлечению 04/evidence/glossary-sections.txt (Dialogue/Turn/Response/W064);
ADR002; m7-return-time-integration; текущие Api/assessment_answer_status.py,
m5_scenario_runtime.py,m5_cycle_runtime.py,m7_clarification.py, routes и interview.js,
тесты EXEC01/03. Статусы источников/CURRENT не меняются. LU означает Local Unit;
Component — компонент навыка. Подтверждённый серверный черновик в базе не найден.
SYN-CONTOUR-OWNERSHIP: новая owned p4k_postw05_pytest, localhost:55435, отдельный
кластер /tmp/p4k-postw05-pg. Не используются рабочие БД, secrets, LLM, почта или Docker.

## Результат и границы

Один результат: отдельный изменяемый приватный draft, CAS, точный слот, localStorage,
короткий debounce750ms/maxWait3000ms, явные статусы у существующего textarea,
устойчивый pending/readback исходной отправки. PM04/runtime и инфраструктура хранения;
оценка PM05, M6, profile, Evidence, Recommendations, Report не получают черновик.
Затронуты runtime ввод/восстановление Dialogue (LU04.2–04.7 в применимой карте),
owner API, repository, session logout и существующий maintenance worker.
Управляющие документы, методология, immutable snapshots и отправленные Turns неизменны.

Стоп-условия: новая предметная норма не вводится; API/schema additive, отдельное
хранилище и совместимость прямо предусмотрены принятой задачей. Миграция только
на synthetic test-БД; реальный migration/deploy/merge не входят. Внешняя передача
оценивается отдельно после конкретного diff/проверок; локальные branch/commits разрешены.
Границы: branch_push/pr — после проверки прямого допуска; merge/deploy/version_bump/
artifact_publish=false. Не переносить старый допуск других задач автоматически.

## Шаги

1. Разведка и план — выполнены.
2. Серверная область/хранение/CAS, устойчивый буфер, pending и UI — выполнены.
3. Адресные unit/HTTP/PostgreSQL/browser fixtures desktop/mobile и review гонок — выполнены.
4. Применимый набор EVC/сборка/dist/отчёт выполнены; сверка main после03 ожидает его merge.

## Проверки

05A–F: точные переносы и отсутствие новых Turns; close-before-debounce; другой
browser context; CAS двух клиентов/clear/late ack; раздельный ASK и основной вопрос;
readback без дубликата; R1/deadline/cancel/logout; storage/network failure.
Node frontend suite, lint/build/dist; backend unit и HTTP; targeted real PostgreSQL
integration с подставными providers/часами. Browser fixture реального web bundle,
1440/390, скриншоты. Full paid assessment, реальные письма/LLM, prod/manual acceptance NOT_RUN.

## Совместимость и откат

assessment_answer_drafts создаётся additive/idempotent ensure_m5_runtime_schema.
Старые строки/таблицы/Turns не переписываются. Schema сначала, backend затем,
frontend затем; старый frontend продолжает работать без нового API. Текст не
переносится из legacy sessionStorage, если точный вопрос и владелец недоказуемы.
Deadline хранения — уже зафиксированный крайний срок Cycle; maintenance удаляет
истёкшие строки. Состоявшиеся ответы имеют прежнюю политику хранения.
Откат кода сохраняет новую таблицу; DROP возможен только отдельным допуском после
срока хранения, не как автоматическая часть rollback. Pending keys сохраняют
исходные request/turn IDs и прежний readback, без нового автоповтора анализа.
