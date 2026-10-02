# M7 Task 07 — завершение, продолжение и C-46

Дата: 2026-10-02. Статус: **IMPLEMENTED — local technical QA**.
Ветка: `codex/m7-task07-completion`. База: Task 06 commit `164c029`.

## Результат

Реализован единый completion service поверх существующего M5/M7 runtime: final
закрытие AS/Dialogue, Session и Cycle; pause/resume; прерывание и Additional Session;
два лимита времени и blocking waits; фоновое закрытие; final C-45/outbox; versioned
C-46 и composition-checked reconciliation. Product endpoints используют владельца
Cycle и не раскрывают служебные C-xx.

Не входят: агрегация Task 08, Results/Report Task 09, новый evaluator и перенос
legacy `user_sessions`. M6 product consumer ещё отсутствует; outbox сохраняется как
`pending`, без подмены QA-механизмом.

## Источники и трассировка

Прочитаны AGENTS, README, CONTRIBUTING, EVC workflow/matrix/recipe; Tasks 01–07;
M1 v1.4, M7 v1.3 SHA-256
`50a0d53a3aaf6258957ecc6d9e89f27d922bfbe4cd55668185d475c87f4e2f10`,
Change 01, ADR-002, Registry и фактические M5/M6/M7 контракты/тесты.

- M7.5.3–5.6 → frozen budget/deadline, persisted intervals и expiry worker;
- M7.7 → единое завершение, фактический материал, processing отдельно от collection;
- M7.8 → continuation intent и Additional Session без переноса Dialogue;
- M6.6.9 → final C-45/outbox, исход оценки остаётся у PM-05;
- Change 01 И-4/И-5 → Cycle composition и C-46 для PM-06.

Стоп-условий для collection/runtime нет. Ограничение M6 product consumer сохранено
видимой зависимостью и не мешает надёжно зафиксировать закрытие и pending processing.

## Проверки

- `npm run test:backend`: PASS, 304 passed, 92 deselected;
- `npm run test:backend:http`: PASS, 26 passed;
- полный PostgreSQL integration: PASS, 63 passed, 334 deselected;
- адресные PostgreSQL сценарии normal completion, terminal C-45, outbox/C-46,
  reconciliation conflict, interruption/Additional Session и paused deadline:
  PASS, 6 passed, включая blocking wait и неизменный deadline;
- unit GC + HTTP owner/foreign/QA scope и superadmin boundaries: PASS, 44 passed;
- frontend CI-equivalent: audit 0 vulnerabilities, lint PASS, 3 tests PASS,
  build PASS и `web/dist` без diff; `py_compile` и `git diff --check`: PASS;
- real provider, утверждённые GC, pilot времени и GitHub CI: NOT_RUN.

## Риски и откат

Worker имеет техническую задержку до 30 секунд, но серверные входы проверяют границу
синхронно. Product processing останется pending до подключения разрешённого PM-05
consumer. Откат: остановить worker и новые endpoints; не удалять immutable history,
C-45/C-46 или outbox, закрытые Cycle не открывать.
