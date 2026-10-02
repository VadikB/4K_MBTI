# M7 Task 06 — оценочные уточнения

Дата: 2026-10-02. Статус: **IMPLEMENTED — local technical QA**.
Ветка: `codex/m7-task06-clarifications`. База: `e17e2412a3bbfdbb633b264c38a806c5503a3d07`.

## Результат и область

Реализован ограниченный superadmin QA-путь PM-04: решение по актуальной interim
C-54, один нейтральный вопрос в том же Dialogue, ответ/отказ/отсутствие ответа,
новая interim C-45 и повторный полный анализ M6. Статусы решения, input/mechanism
snapshots, доставка и исход неизменяемы и читаются из PostgreSQL.

Основной пользовательский UI, автоматическое закрытие AS/Cycle, создание новой AS,
Task 07/08, утверждение GC и реальный provider не входят.

## Источники, решения и трассировка

Прочитаны Task 06, README/CONTRIBUTING/AGENTS, EVC workflow/matrix/recipe, Change 01,
SourceSet manifest, M1 v1.4, M6 v1.8, M7 v1.3, ADR-002, Registry, контракты и тесты
M5/M6/M7. M7 v1.3 имеет SHA-256
`50a0d53a3aaf6258957ecc6d9e89f27d922bfbe4cd55668185d475c87f4e2f10`.

- M6 §§6.6–6.9 → semantic interim C-54 и uncertainty → `m7_clarification_decisions`;
- M7 §§5–7 → состояние/время/полезность/допустимость → пять статусов решения;
- M5.5.7 → нейтральность и та же задача → draft prompt + deterministic guards;
- M1.6/ADR-002 → тот же AS/Dialogue, новая C-45 после ответа;
- Change 01 И-6 → immutable history, idempotency, stale checks и readback.

Legacy follow-up обследован и не переиспользован по совпадению имени. Новый вопрос
имеет автора `assessment`; M6-A не считает его пользовательским evidence. Решение
владельца не требуется: источник и граница QA определены, стоп-условий нет.

## Проверки

- `py_compile` новых backend-модулей и routes: PASS;
- `npm run test:backend`: PASS, 303 passed, 88 deselected;
- `npm run test:backend:http`: PASS, 25 passed;
- `TEST_DATABASE_URL=postgresql://pytest@127.0.0.1:55487/agent4k_m7_pytest npm run test:backend:integration`:
  PASS, 59 passed, 332 deselected;
- адресный unit/GC/HTTP-набор: PASS, 44 passed;
- адресный PostgreSQL integration полного `M6→M7→M6`, включая `no_answer` без Turn:
  PASS, 1 passed на `agent4k_m7_pytest`;
- frontend CI-equivalent: `npm audit --audit-level=high` — 0 vulnerabilities;
  lint PASS; 3 regression tests PASS; build PASS и `web/dist` без diff;
- `git diff --check`: PASS. GitHub CI: NOT_RUN до push текущего commit;
- real provider, независимое утверждение GC и pilot: NOT_RUN; технический QA не
  подтверждает методологическую приемлемость формулировок.

## Риски и откат

Схема расширяет допустимых авторов Dialogue значением `assessment`; старые значения
совместимы. Вызов provider выполняется синхронно в QA-транзакции, поэтому путь не
переключён в продуктовый runtime до эксплуатационной проверки latency/retry.
Персональные данные и production/test базы не использовались.

Откат: запретить новые QA create/present/answer операции; не удалять историю,
доставленные Turns или snapshots. Следующий шаг — Task 07 и отдельная методологическая
проверка clarification candidates.
