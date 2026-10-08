# Task-10-14 — неполное прохождение и частный результат

## Результат

На базе `7c0dfb2` добавлен `m8-partial-result/1.0.0`: Results/C67/PDF объясняют
прогресс по frozen plan и lifecycle AS, сохраняют четыре M6 outcomes и различают
пять причин ограничения. Status показывает новую оценку только как явное действие;
сам GET Cycle не создаёт. Template `m8_basic_report/1.3.0` хранит тексты вне кода.

## Приёмка

- R2–R7, R11: PASS — PostgreSQL/HTTP receipts в `artifacts/task10-14/receipts.json`.
- R1/R8: BLOCKED — five-case product route нельзя честно создать: synthetic catalog
  допускается для `qa`, product orchestration использует `assessment`. Guard не ослаблен.
- R9/R10: PARTIAL — immutable old Report, owner/tenant scope, BaseRole/config checks
  существуют; полный A→B маршрут зависит от R8.

Это не утверждение GC, catalog acceptance или semantic quality. Real AI не запускался.

## Изменения

Изменены `Api/m8_results.py`, report loader/PDF, owner status API; добавлена новая
неизменяемая версия report template и unit/integration/e2e regression. Schema/SQL
не менялись. Старые report revisions остаются неизменными; новая версия применяется
только при явном создании новой revision.

## Источники и границы

Прочитаны AGENTS/EVC, Change 01, SourceSet, ADR-002, M6 v1.8 §§6.6.9/6.7.3–4,
M7 v1.3, M8 v1.2, UX3.6/UX4.2/D14/D16, контракты и код 10.11–10.13.
Пакет r2: SHA-256 `06091bb0d9870974c79e12515f90c61966e07c09627d59d18baafe1d51fedcd3`, CRC PASS.
Нормы AI-time и обновления кейса после 3 минут не вводились.

## Проверки

- `py_compile` — PASS.
- backend без integration/e2e/llm — PASS: `378 passed, 143 deselected`, 16.03 s.
- HTTP targeted — PASS: `4 passed`, 4.32 s.
- owned PostgreSQL targeted — PASS: five named receipts; БД `agent4k_pytest_1014`.
- `git diff --check` — PASS.
- CI/full integration/browser/real LLM — NOT_RUN; CI обязателен до merge.

## Передача и откат

Branch `codex/task10-14-partial-results`; implementation commit `c72c5c3ef87da3a239e13ae78e2c157aaa6c5cca`.
Откат: revert commits задачи; существующие snapshots/Results/Reports не изменять.
Новый UX не реализовывался. Следующая задача не запускалась.
