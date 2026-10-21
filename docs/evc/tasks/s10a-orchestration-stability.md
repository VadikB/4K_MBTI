# S10-A: стабильная browser-приёмка orchestration

## Результат

S10-A не зависит от планирования фонового потока GitHub runner: после `scenario_end`
тест явно дренирует очередь только собственного isolated browser stand и затем проверяет
тот же пользовательский clarification-flow. Production/test runtime не меняется.

## Область

- Включено: `scripts/test_stand.py`, S10-A в `tests/browser/runtime.spec.mjs`.
- Не входит: production orchestration, методология, публичный API, схема БД, deploy.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
  `docs/evc/review-checklist.md`, `tests/README.md`, Change 01 README и manifest.
- Основание: post-merge run `39562625000`, commit `2279a509`; 50 browser PASS,
  S10-A timeout при ожидании clarification, backend/integration PASS.
- Владелец поручил исправление в текущем чате 21.10.2026.
- Стоп-условия: нет; предметный смысл, API, данные, права и контуры не меняются.

## План и состояние

- Завершено: локализация зависимости S10-A от фонового scheduler.
- Завершено: isolated drain, защитный unit-тест и локальная регрессия.
- Активный шаг: PR и обязательный CI.
- Следующий шаг: после положительного CI — squash merge и post-merge deploy-test.
- Ветка: `codex/s10a-orchestration-stability`.

## Критерии приёмки

- [x] `drain` разрешён только owned isolated browser acceptance stand.
- [x] S10-A проходит повторно без увеличения wall-clock timeout.
- [x] PostgreSQL integration продолжает проверять асинхронную orchestration.
- [x] Production/test runtime и публичные контракты не изменены.

## Проверки

- `git diff --check`.
- `python -m py_compile scripts/test_stand.py`.
- целевой S10-A несколько раз на временной PostgreSQL 16;
- backend, HTTP и integration по матрице;
- полный browser suite; обязательный GitHub CI.

Фактически выполнено:

- S10-A до изменения: PASS, 1 прогон; после изменения: 3/3 PASS и финальный 1 PASS;
- полный browser suite: 51 PASS;
- backend: 476 PASS; HTTP: 61 PASS;
- PostgreSQL integration: 139 PASS в полном прогоне; 5 тестов первоначально FAIL
  из-за отсутствующего локального `STAND_ADMIN_URL`, повтор с корректным maintenance URL:
  6 PASS (два кейса находятся в одном файле). Код по этому сбою не менялся;
- `tests/unit/test_test_stand.py`: 11 PASS;
- `py_compile`, `node --check`, `git diff --check`: PASS.

## Риски и откат

Риск ограничен test harness. Откат — revert коммита; данные и миграции отсутствуют.
