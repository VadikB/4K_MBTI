# M6-B — промежуточный разбор и Indicator Assessment

Дата: 2026-10-02. Статус: **IMPLEMENTED — local technical QA**.
Ветка: `codex/m6-task04-indicator-assessment`. База:
`01411ebc77b0b8b154f7a83c576a91b3c231ee41` (Draft PR #24, M6-A).

## Результат и границы

Реализовано продолжение M6-A внутри PM-05: interim без IA, final IA по каждой цели,
разделение L0–L3/IE/отсутствия оценки/технического сбоя, immutable revisions,
семантический C-54 и readback. Добавлен draft prompt package и restricted superadmin
QA API. Основной пользовательский маршрут не переключён.

M7-вопрос, решение о продолжении AS, Cycle aggregation и M8 не входят в задачу.
Существующая M6-A остаётся владельцем Evidence/EB; параллельная модель данных не создана.

## Источники и трассировка

Прочитаны `README.md`, `CONTRIBUTING.md`, обязательные EVC-документы, Change 01,
SourceSet manifest, ADR-002, Registry, контракты/код/тесты M5 C-45/C-54 и M6-A,
M1 v1.4 и относящиеся разделы M6 v1.8. Исходник M6: SHA-256
`2e5f60a5f1c430458a253ec0bb4638555de1bec704ea02f1e5c2127a3abd39b4`.

- M6.6.1–6.6.9 → `m6_assessment_contracts.py` и draft prompt → levels/IE/L0,
  whole EB, uncertainty, qualitative confidence;
- M6.8.1–8.3 → repository/worker → IA identity/revisions, retry, lease, readback;
- C-45/C-54 и Change 01 И-4 → вход из сохранённой M6-A revision и запись
  `m5_c54_receipts` в одной транзакции;
- И-6 → frozen mechanism/input snapshots, hashes, immutable triggers и attempts.

Технический контракт: [M6-B v1](../../architecture/m6-b-contracts.md).

## Проверки

- `py_compile` изменённых Python-модулей: PASS;
- `npm run test:backend`: **295 passed, 85 deselected**;
- `npm run test:backend:http`: **25 passed**;
- `TEST_DATABASE_URL=postgresql://pytest@127.0.0.1:55487/agent4k_m6_pytest npm run test:backend:integration`:
  **56 passed, 324 deselected**, в том числе полный M6 набор **22 passed**;
- адресный M6/GC/unit/HTTP набор после расширения кандидатов: **64 passed**;
- `py_compile`, `git diff --check`, hashes пакета и локальные ссылки: PASS.

Секреты, production/test пользовательские данные и developer DB не использовались.
Real provider smoke, методологическая semantic acceptance и CI: `NOT_RUN`.

## Риски, стоп-условия и откат

GC остаются кандидатами, `approved_gc_count=0`; технический PASS не разрешает
оценивание пользователей. Draft package нельзя публиковать без отдельной приёмки.
Сбой отдельной цели сохраняется как технический, без person-result; request-level
сбой не создаёт assessment revision и C-54.

Откат: остановить новые M6-B QA requests и worker, дождаться активных leases,
сохранить immutable историю и reader. Новые таблицы не удалять автоматически,
legacy evaluator не включать как fallback.
