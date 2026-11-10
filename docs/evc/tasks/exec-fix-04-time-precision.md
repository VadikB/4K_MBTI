# EXEC-FIX-04: точная граница учитываемого времени

## Результат и область

До фактического исчерпания сохранённого бюджета Cycle сервер допускает новый M5 Turn
и ответ на уже предъявленный вопрос M7; на границе и после неё запись запрещена.
Целочисленные `consumed_seconds` и `remaining_seconds` остаются проекциями для
клиента. Дробные длительности суммируются до сравнения, а `effective_at` закрытия
вычисляется из точных интервалов.

Изменяются только серверный учёт времени и регрессии. Не изменяются схема БД,
публичные поля/API, источник или значения `7200`/`259200`, календарное окно,
published definitions, snapshots, R1, provider/model/prompts и правила replay.
Откат: revert этого изменения кода и тестов; данные и записанные интервалы не
удаляются. Для выпущенных в промежутке Cycle уже принятые Turns сохраняются.

## Источники и решения

Основание: прямой запрос владельца 10.11.2026 и пакет `EXEC-FIX-04` редакции 1.0.
Аудит `8e3fb851f7920d3eee31312932057f035068422a` / 2.0.91 — исторический
срез; фактическая база кандидата — `48e175da2a5dffd27e0722e0f50588f87a88fdbf`.
На базе воспроизведено: точные `7199.60` и `7199.90` секунд отклоняются из-за
`SUM(...)::BIGINT`. Исходная проба и новая проверка сохранены в пакете передачи.

Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
`docs/evc/{agent-workflow,verification-matrix,artifact-recipe,decision-register,task-template,review-checklist}.md`;
`docs/architecture/product-4k/{1.0/context,registry}.md`, Change 01 `README.md`
и применимые И-1/И-2/И-5/И-6/И-7 из `source.md`; SourceSet
`docs/methodology/source-sets/2026-10-01/manifest.json`; M1 v1.4 §M1.6–1.10;
M5 v1.1 §5.5.7–5.5.9; M6 v1.8 §6.6.6–6.6.9; M7 v1.3 §§M7.5.3, M7.6, M7.7;
M8 v1.2 Results/Report; ADR-002; `m7-clarification-contract.md`,
`m7-completion-contract.md`; `sls04-sales-return-budget.md`,
`fix-return-heartbeat-race.md`, `path-pilot-approved-design.md`,
`assessment-first-case-profile.md`, `exec-contour-01.md` и H1–H12;
`assessment_definitions/planning/m7_return_integration/v2/policy.json`.
M5, M6, M7 и M8 имеют выбранные FROZEN-оригиналы и SHA-256 в task SourceSet;
M0 original там помечен unavailable, но прямое правило времени задано M7/Change 01.
Предметное содержание пакетов не меняется. В `decision-register.md` применим
`PILOT-120`: ровно `7200` секунд фактического прохождения и `259200` секунд окна
в указанной области; число не переносится на другие программы.

Прослеживаемость: M7 §M7.5.3 / Change 01 И-2 → общий бюджет и исключённые интервалы
→ PM-04/LU-04.6, C-46 → `m5_cycle_runtime._remaining_collecting_seconds`,
`_can_continue`, `read_cycle`; M5 §5.5.7 и M6 §6.6.6–9 → M7 вопрос/ответ
→ `m7_clarification`; M7 §7 и C-46 → точный момент закрытия
→ `m7_completion._effective_limit`; регрессии — `test_exec_fix04_time_precision*`.

Стоп-условия рабочего цикла: смены предметной нормы, API/владения данными,
миграции, нового артефакта, доступа, удаления данных и границы деплоя нет.
Откат кода определён. Обязательная норма доступна. Открытых решений для локальной
реализации нет; выпуск и приёмка остаются у архитектора/владельца.

## План, полномочия и проверка

Один исполнитель, ветка `codex/exec-fix-04-time-precision`, worktree
`USER_WORKTREES/exec-fix-04-time-precision`, сессия `P4K-EXEC-04-USER`.
Прямой запрос разрешает локальную ветку, код, бесплатные тесты на собственном
PostgreSQL и пакет передачи. `branch_push=false`, `pr=false`, `merge=false`,
`deploy=false`, `version_bump=false`, `artifact_publish=false` в этой передаче.
Внешний пакет описывает отдельный PR архитектора; существующий PR #205 остаётся
draft до совместимости и финального H7 после включения FIX04 в main.

Проверки: детерминированные unit для точного допуска, проекции, минимума M7 и
`effective_at`; owned PostgreSQL и HTTP для ответа, границы, нескольких интервалов,
accepted replay/конфликта и ожидания lock; полный `npm run test:backend`,
`npm run test:backend:http`, адресный M5/M7 integration, `git diff --check`.
Frontend-код не меняется; обязательные CI jobs `frontend`, `pytest`,
`full-verification` и human review выполняются для PR архитектора. Реальные LLM
и платные прогоны не разрешены и не нужны. Результаты точного candidate SHA,
команды, measured before/after и хеши — в отдельном handoff-пакете.

Существенный риск: целочисленный остаток показывает `1` при положительной доле
секунды; сервер отдельно проверяет точное время и не даёт округлённой льготы.
Минимум времени для нового M7 вопроса сравнивается по точному остатку.
