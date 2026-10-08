# Task-10-12 — технический сбой обработки и восстановление

## Результат и критерии

Реализовано разделение collection, предметного результата M6, processing и
presentation. Технический admission failure больше не маскируется `report_ready`:
Report может сохраниться как ограниченный, owner status/history остаются `failed`.
Авторизованный retry создаёт новые immutable revisions на сохранённом входе.

| ID | Статус | Доказательство |
| --- | --- | --- |
| F1 | PASS | fault matrix individual/joint: timeout, invalid JSON, schema, foreign ref |
| F2 | PASS | `m6_cycle_aggregation` не изменён; processing вынесен отдельно |
| F3 | PASS | unit matrix и C-67 limitation: failure не становится L0/IE/NOT_COMPARABLE |
| F4 | PASS | product integration сохраняет Dialogue/IA; owner scope и foreign-org HTTP |
| F5 | PASS | две Calculation/Results revisions, новый Report, старый Report неизменён |
| F6 | PASS | GET/PDF остаются pure reads; Cycle/Session не открываются, Turns не добавляются |
| F7 | PASS | C-67 и PDF получают одно processing limitation; stacktrace/PII отсутствуют |
| F8 | BLOCKED | accepted 10.11 разрешает fixture/synthetic origin только для `qa`, а production orchestration обрабатывает только `assessment`; менять origin на human или ослаблять guard запрещено |
| F9 | BLOCKED | product failure доказан через обычные workers/admission, но fixture использует legacy isolated-test compatibility, поэтому полное доказательство цепочки после catalog-bound M5 gate зависит от решения F8 |
| F10 | PARTIAL | frozen recovery input и неизменность catalog ref проверяются, но валидный synthetic catalog snapshot отсутствует из-за F8 |
| F11 | PASS | individual failed basis не создаёт рекомендаций; при joint failure сохраняются только рекомендации с ранее admitted individual basis |

## Branch и область

Branch `codex/task10-12-processing-failures`, base
`1dd8fc0dc79142db8da93c1181599b4d9b5ac2c9`. Пакет r2 SHA256:
`3d4cb6d60c3ba6db0f5a653f85357bebb107f256435426207bc5857c45f7ddcf`.
UX merge, push, deploy, общая SQL и внешние AI-вызовы не выполнялись.

## Изменения

- `Api/m10_orchestration.py`: processing revisions, recovery queue, frozen input,
  failure-aware finalize и idempotent worker.
- `Api/m8_results.py`: failure-priority history, C-67 processing projection и
  сохранение существенного ограничения.
- `Api/routes.py`, `Api/schemas.py`: owner read contract и авторизованный admin retry.
- `Api/pdf_templates/m8_basic_report.typ`: одинаковое существенное ограничение в PDF.
- unit/HTTP/integration tests и evidence этой задачи.

## Источники и решения

Прочитаны пакет r2, handoff 10.10B, полный отчёт/контракт/evidence Task-10-11,
M6 v1.8 §§6.6–6.8, применимые M7/M8 разделы, ADR-002, фактические M6/M8/M10
consumers и recovery tests. Зависимость 10.11 принята по фактическому commit и
локальному коду, не по краткому summary.

Предметные правила не менялись. Новое право не вводилось: recovery использует
существующее `configuration.publish` и organization scope. Участнику retry не
показывается. Открытое решение владельца: разрешённый технический способ получить
catalog-bound QA Cycle через product orchestration без допуска synthetic evidence
в ordinary assessment.

## Проверки

- fault unit matrix → PASS, `18 passed` в адресном прогоне;
- recovery HTTP → PASS, `3 passed` после корректировки fixture;
- product/M6/M8 integration → PASS, `17 passed`;
- полный backend → PASS, `372 passed, 143 deselected`;
- полный HTTP → PASS, `45 passed`;
- полный PostgreSQL integration → PASS, `94 passed, 421 deselected` на
  disposable PostgreSQL 16 с явными `TEST_DATABASE_URL`/`STAND_ADMIN_URL`;
- `py_compile`, JSON validation и `git diff --check` → PASS.

CI не запускался: ветка не push, PR не создан. Перед merge обязательны jobs
`frontend` и `pytest` на актуальном head.

## Схема, безопасность и откат

Схема аддитивна: `m10_pipeline_revisions`, `m10_processing_recoveries`.
Terminal recovery и pipeline revisions неизменяемы. Frozen input содержит только
технические refs/checksums, без Dialogue/PII. Provider text и stacktrace не
сохраняются. Откат — возврат runtime к base commit; новые таблицы остаются audit
trail и не удаляются без отдельной миграции.

## Следующий минимальный шаг и блокер

Владелец архитектуры должен выбрать узкое решение F8: отдельный явно разрешённый
QA orchestration mode для catalog-bound Cycle рекомендуется; расширять ordinary
assessment origin policy не рекомендуется. До решения F8 нельзя объявить полную
приёмку 10.12, хотя независимая failure/recovery реализация и проверки выполнены.
