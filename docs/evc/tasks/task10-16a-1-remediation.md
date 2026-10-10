# Task 10.16A.1 — remediation независимой проверки

## Результат

Исправить F-01–F-03 и предъявить адресные регрессии C4/C5/C7/C8/C9 для передачи
отдельно запускаемой 10.16B. Результат этой задачи не является методологической
приёмкой реальной AI-оценки.

## Область

- Включено: additive schema update для длительности; latest-wins M5 admission;
  единый frozen BaseRole между M7 plan и M5 AS; regression tests; краткий отчёт.
- Не входит: запуск 10.16B, реальные LLM-вызовы, version-aware PDF renderer,
  унификация версий M8, новые методологические рекомендации, изменение CURRENT.

## Контекст

- Основание: пакет `Task_10_16A_1_Package.zip`, manifest schema 1, task 10.16A.1.
- Defect source и начальный `main`: `8db9eb2de65766812c8ad03e5d76d3d702484596`.
- Архитектурный адрес: PM-02/03/04, C-23/C-24/C-34; PM-07 dashboard только читает
  фактическую длительность legacy assessment.
- Контракты: `m5-catalog-integrity-contract.md` 1.0,
  `m7-cycle-planning-contract.md` draft QA, ADR-002.
- Предметные артефакты не изменяются.

## Источники и решения

- Прочитано: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, EVC workflow/matrix/
  artifact recipe/task template/review checklist; Change 01; task SourceSet manifest;
  Product 4K context/Registry; ADR-002; M5 catalog integrity и M7 planning contracts;
  `package.json`, `tests/README.md`; применимые schema/runtime/tests; приложенный
  remediation и независимый отчёт. SHA-256 файлов пакета совпали с manifest.
- Change 01 WORKING; M1 1.4 и M3/M4/M5 выбранных версий FROZEN; runtime publication
  и CURRENT задачей не меняются.
- Решение владельца: выполнить F-01–F-04 в одном remediation PR; основание — запрос
  пользователя и приложенный пакет; 10.16B/F-05–F-07 остаются вне реализации.
- Стоп-условия: все восемь — нет. Смысл сущностей, публичный контракт, PM/LU,
  чувствительные данные и формат артефактов не меняются; schema change аддитивен,
  без backfill/удаления; откат определён. Действующий контракт явно требует
  latest evidence и frozen BaseRole.
- Пробел: локальный owned PostgreSQL URL проверяется перед integration; его отсутствие
  будет отмечено как BLOCKED, а не PASS.

## План и состояние

- Завершено: разведка, проверка пакета, fetch, сверка `main` и defect SHA,
  локализация F-01–F-03.
- Активный шаг: реализация F-01–F-03 и адресных регрессий.
- Следующий шаг: targeted tests, затем полный backend/HTTP/integration и H8 на
  финальном дереве; review/diff; заполнение фактических результатов.
- Ветка: `codex/task10-16a-1-remediation`.

## Ограничения и риски

- Совместимость: старые строки сохраняются; неизвестная длительность остаётся `NULL`.
- Данные и миграции: только nullable `session_cases.actual_duration_seconds`; без backfill.
- Безопасность: только синтетические fixtures; секреты/токены/PII не сохраняются.
- Внешние сервисы/LLM: не используются.
- Производительность: latest определяется индексируемым DB `id`; новых сетевых вызовов нет.

## Критерии приёмки

- [x] F-01: fresh/repeat bootstrap дают admin login/dashboard без UndefinedColumn;
  additive update покрывает существующую schema без backfill.
- [x] F-02: latest FAIL/NOT_RUN/mismatch блокирует старый PASS; valid latest допускает.
- [x] F-03: frozen BaseRole Cycle используется в planner и direct AS.
- [ ] C4/C5/C7/C8/C9 имеют адресные test nodes и assertions: C4/C5/C8/C9 закрыты;
  C7 сохраняет существующие frozen profile/catalog/report проверки, но exact switch
  A → B для двух опубликованных catalog refs отдельным тестом ещё не предъявлен.
- [x] Backend, HTTP, integration/H8 и `git diff --check` имеют честный статус.
- [x] Новое предметное содержание не встроено в исходный код или генератор пакета.
- [ ] Исторические snapshots и потребители контрактов проверены.

## План проверки

- Unit: M5 admission latest/bindings; frozen cycle role resolver.
- Integration: current-schema catalog isolation/publication/snapshot/empty route;
  role plan → AS; clean bootstrap/admin flow.
- Полный минимум: `npm run test:backend`, `npm run test:backend:http`,
  `TEST_DATABASE_URL=… npm run test:backend:integration`, `git diff --check`.
- Frontend не меняется.

## Откат

Revert только commits remediation. Nullable schema extension не удалять и данные не
переписывать; старый runtime безопасно игнорирует колонку. Тестовые БД удалять только
через owner guard штатного disposable stand.

## Отчёт

### Результат и before/after

- F-01: before — fresh superadmin login `500 UndefinedColumn` сначала на
  `session_cases.actual_duration_seconds`; после устранения первой причины адресный
  прогон обнаружил и исправил `ssa.competency_name`. After — login и dashboard 200,
  duration берётся из nullable фактического поля, competency — из `skills`.
- F-02: latest выбирается по DB `id` до eligibility/binding validation;
  `evidence_considered` сохраняет выбранный id и причины, fallback к старому PASS нет.
- F-03: AS берёт BaseRole из frozen `m5_cycles.selected_role_ref_json`; legacy text ref
  сохраняется, организационный код не подменяет стабильную BaseRole.
- F-04: C4 — один latest FAIL блокирует planner и direct AS; C5 — два непересекающихся
  catalog/configuration refs; C8 — dry-run/replay/conflict/update/delete и HTTP auth/org;
  C9 — published empty catalog оставляет M4 ready и не создаёт Cycle. C7 exact A → B
  остаётся незакрытым адресным evidence gap, поэтому статус не READY_FOR_10_16B.

### Проверки (команда → результат)

- `.venv/bin/python -m pytest -q tests/unit/test_m5_catalog_integrity.py tests/unit/test_m5_storage.py`
  → PASS, 19.
- targeted F-02/C5/C8 PostgreSQL → PASS, 1; targeted F-03 → PASS, 2;
  targeted C4 → PASS, 1; owned profile/C9 → PASS, 1.
- H8 `test_two_empty_database_application_starts_and_owner_http_reports` → PASS после
  сохранённых первых FAIL; два fresh stand, повтор bootstrap/restart, superadmin 200,
  owner Results/Report/PDF readback.
- `npm run test:backend:http` → PASS, 51.
- `TEST_DATABASE_URL=<owned localhost pytest> STAND_ADMIN_URL=<localhost postgres>
  npm run test:backend:integration` → PASS, 95 selected.
- `npm run test:backend` → FAIL: 392 passed, 13 unrelated existing M6 failures из-за
  несогласованности provider operation `deepseek-chat` с manifest `deepseek-flash` и
  зависимых `INPUT_NOT_READY`; затронутые M5 tests PASS. В этой задаче M6/provider
  artifacts не менялись и критерий полного backend остаётся незелёным.
- `git diff --check`, `py_compile` изменённых Python-файлов → PASS.
- CI → NOT_RUN: PR не создан.

### Риски, остатки и откат

- F-05: historical PDF использует current package; text drift не доказан. Следующая
  коррекция — renderer по сохранённому template/package ref; тест — старый Results
  после публикации новой версии даёт байтово/содержательно ожидаемый historical PDF.
- F-06: report dependency/generator/architecture versions расходятся. Следующая
  коррекция — единый version binding C-67 с compatibility read; тест — mismatch fail-closed.
- F-07: старые evidence не полностью переносимы; новые regression nodes воспроизводимы,
  но старые отчёты не переписывались.
- Схема аддитивна, security/deploy/LLM не менялись. Откат — revert remediation commit;
  nullable колонку не удалять.

### Итоговый статус

`BLOCKED_FOR_10_16B`: core F-01–F-03 исправлены, C4/C5/C8/C9 закрыты; требуется
адресный C7 A → B test и устранение/отдельное принятое решение по предсуществующим
13 M6 unit FAIL. Final tested commit SHA и CI/PR заполняются при передаче commit/PR.
