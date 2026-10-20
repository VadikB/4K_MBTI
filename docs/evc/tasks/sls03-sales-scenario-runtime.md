# SLS03 — runtime девяти Sales-сценариев

Статус: реализация. Основание: `P4K_Sales_03_Scenario.txt`, редакция 2 от
19.10.2026. База реализации: `d0d74d25e82bb1cd10f7124953b72740cd637241`.

## Источники и границы

Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, применимые EVC workflow,
verification matrix, artifact recipe, Change 01, ADR-002, registry/traceability,
девять выбранных Sales Case/AS и SLS03. Используются неизменяемые author snapshots
из `m5-sales-pilot-cases/0.1`; правила исполнения вынесены в
`execution-rules.json`. Пакет остаётся `WORKING/draft/runtime_enabled=false` до
методологической проверки и admission. Общий Cycle budget 120 минут, авторские
диапазоны Case и pilot/production не меняются.

## Связь «источник → событие → наблюдение → проверка»

| Case | Авторское условие | Runtime-событие/реплика | Возможность наблюдения | Проверка |
|---|---|---|---|---|
| 01 | этапы S0–S5 выбранной AS | сохранённые ходы/переходы | работа с обращением и приоритетом | structured rule + integration trace |
| 02 | самостоятельная работа S0–S2 | материалы без character turn | анализ материалов без фиктивного собеседника | actorless assertion + C-45 |
| 03 | S2 реакции адресатов; S3 конкретный способ работы | отдельные `speaker_id`; однократный M04 | согласование вкладов и реакция на изменение | multi-address, mandatory update, retry |
| 04 | S1–S3 выбранной AS | сохранённые ходы/переходы | фактическая реакция на ситуацию | structured rule + integration trace |
| 05 | S1–S3 выбранной AS | сохранённые ходы/переходы | фиксация решения | structured rule + integration trace |
| 06 | S1–S3 выбранной AS | сохранённые ходы/переходы | работа с заданным материалом | structured rule + integration trace |
| 07 | самостоятельная работа S1–S3 | материалы без character turn | анализ материалов без фиктивного собеседника | actorless assertion + C-45 |
| 08 | S1–S3 выбранной AS | сохранённые ходы/переходы | фактическая последовательность действий | structured rule + integration trace |
| 09 | S1–S3 выбранной AS | сохранённые ходы/переходы | итоговая фиксация участника | structured rule + integration trace |

Таблица — карта трассировки, не доказательство методологической валидности.
Семантические условия исполняет bounded decision с `MATCH/NO_MATCH/UNKNOWN` и
source ref; `UNKNOWN` не вызывает эффект и передаётся в SLS06.

## Реализация и совместимость

- Новые AS фиксируют `m5_semantic_decision/v2` и
  `m5_character_response/v2`; начатые AS продолжают читать версию из snapshot.
- Character input содержит историю, события, карточку, известные факты и
  ограничения раскрытия. Participant API по-прежнему отдаёт только доставленные
  ходы/материалы.
- Effect key реакции включает trigger turn. Повтор того же request не создаёт ход
  или эффект; после технической ошибки допустима новая попытка той же операции с
  отдельным attempt trace.
- `after_first_substantive_turn` и Sales author conditions проходят semantic
  decision, а не `stage=active` или словарь ключевых слов.
- `scenario_ended`, clarification и `closed` остаются разными состояниями;
  pause/resume не удаляет clarification. В C-45 входят реальные turns/events.

## Проверки и откат

Минимум: `py_compile`, Sales builder `--verify-only`, unit, PostgreSQL integration
и HTTP-контракт на изолированной БД, затем обязательный CI. Реальный LLM-прогон
отмечается отдельно и не доказывает методологическую эквивалентность.

Откат: не создавать новые AS с execution-rules schema 2 / prompt v2 и вернуть
коммит. Существующие AS остаются воспроизводимыми по frozen execution snapshot;
изменение опубликованных prompt v1 и author source запрещено.

## Фактический отчёт перед PR

- `py_compile` затронутых Python-модулей — PASS.
- Sales builder `--verify-only` — PASS: 9 Case, 9 AS, 55 target occurrences.
- backend unit — PASS: 466; frontend node — PASS: 65.
- PostgreSQL target integration — PASS: 4; включает два хода одних персонажей,
  request retry, три `speaker_id`, M04, provider failure/retry и legacy-регрессию.
- M5 HTTP contract — PASS: 8.
- `build:web`, release consistency `2.0.3`, `git diff --check` — PASS.
- Реальный LLM — NOT_RUN: стандартный набор использует controlled/fake adapters;
  правдоподобие и методологическая эквивалентность не заявляются.
- Authenticated visual smoke / физические браузеры — NOT_RUN до deploy-test.
