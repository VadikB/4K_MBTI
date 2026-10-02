# M7 Task 05 — план Cycle и следующая AS

Дата: 2026-10-02. Статус: **IMPLEMENTED — local technical QA**.
Ветка: `codex/m7-task05-cycle-plan`. База: M6-B commit
`5c7dc7ba5bbe9bbba700806e195efdaf187d1846`.

## Результат

Реализован ограниченный QA-путь PM-04: план из полного выбранного M2, фиксированный
профиль и время, проверяемый каталог Cases, воспроизводимый маршрут, сохранённое
решение следующей AS, подготовка через PM-03 и предъявление через существующий M5
runtime. Текущий WORKING-каталог возвращает объяснимую нехватку допуска.

Вопросы уточнения, окончательное управление продолжением/закрытием, агрегаты M6 и
M8 Report не входят. Основной пользовательский путь не переключён.

## Источники и трассировка

Прочитаны Task 05 rev.1, M7 v1.3 (SHA-256
`50a0d53a3aaf6258957ecc6d9e89f27d922bfbe4cd55668185d475c87f4e2f10`),
M1 v1.4, Change 01, SourceSet, ADR-002, Registry, EVC workflow/matrix/recipe,
контракты и тесты M5 Cycle/Session/Case/AS и результаты M6-A/M6-B.

- M7.1–3 → M2 target composition, frozen profile/time/requirements и plan revision;
- M7.4 → versioned deterministic rules artifact, Case eligibility, route/gaps;
- M7.5 → текущий Cycle/Session/AS и оба лимита перед выбором/предъявлением;
- M7.6–8 → C-54 facts, отсутствие повторов ради повышения уровня, stop outcomes;
- Change 01 И-6 → idempotency, immutable history, assignment uniqueness, readback.

Контракт: [M7 Cycle Planning v1](../../architecture/m7-cycle-planning-contract.md).

## Проверки и ограничения

- `npm run test:backend`: **297 passed, 87 deselected**;
- `npm run test:backend:http`: **25 passed**;
- `TEST_DATABASE_URL=postgresql://pytest@127.0.0.1:55487/agent4k_m7_pytest npm run test:backend:integration`:
  **58 passed, 326 deselected**;
- совместный адресный M5/M6/M7 integration: **26 passed**;
- `py_compile`, artifact hashes, локальные ссылки и `git diff --check`: PASS.

Real M6→M7 provider flow, независимые GC, предметный допуск пяти Cases и
эмпирический пилот достижимости 60 минут и CI: `NOT_RUN`. Поэтому технический QA не
означает готовность коммерческой экспресс-оценки.

## Откат

Остановить новые QA планы/решения, не предъявлять подготовленные AS, сохранить новые
таблицы и readback. Старые Cycle/Session/AS и `target_set` не изменять и не backfill.
