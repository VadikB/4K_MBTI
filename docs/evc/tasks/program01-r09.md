# PROGRAM01 R09 — доказательства итогового кандидата

## Результат

Для точного кандидата после R01–R08 и R10 собран воспроизводимый пакет
доказательств по 16 критериям `PROGRAM_ACCEPTANCE` и 26 критериям
`STATUS_ACCEPTANCE`. Каждый критерий получает фактический статус
`PASS` / `FAIL` / `NOT_RUN`, условия и ссылку на доказательство. Исторические
результаты аудита не выдаются за новый прогон.

## Область

- Включено: lint/build и соответствие `web/dist`; frontend, backend и HTTP;
  адресная PostgreSQL integration; browser-сценарии ролей и затронутые
  viewport/accessibility; сценарии двух назначений, последнего profile/job и
  legacy `Cycle.assignment_id=NULL`; заполнение матриц доказательств.
- Не входит: исправление новых дефектов в том же PR; реальные персональные данные,
  письма и живые приглашения; изменение M6–M8, предметных источников, API или схемы;
  присвоение baseline/CURRENT/FROZEN; merge и deploy без отдельного решения владельца.

## Контекст

- Основание: `P4K_PROGRAM01_AUDIT_2.0.47_2026-11-02.zip`, `START.txt`,
  `REMAINING_TASKS.txt` R09, SHA-256 пакета
  `5cc38524ec2f3c152f7acbb721eb93155c3862673a0a431414f6ef051533d31b`.
- Base: `origin/main@d33670f2e662ed7fc9018721ab3d8f3bb7d517c3`.
- Архитектура/ADR: Change 01 WORKING; ADR-002; `docs/evc/change01-traceability.md`.
- Применимый комплект: task SourceSet 2026-10-01; M1 v1.4, M2 K1/K3 v1.1,
  K2/K4 v1.0, M3/M4 v1.0, M5 v1.1, M6 v1.8, M7 v1.3, M8 v1.2.
- Архитектурный адрес: проверяется существующий путь PROGRAM01 и ADM-STATUS;
  новые PM/LU, предметные правила и владельцы данных не вводятся.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
  `docs/evc/task-template.md`, `docs/evc/review-checklist.md`, архитектурный
  context/Registry, Change 01 README, task manifest, ADR-002, относящиеся строки
  traceability, `tests/README.md`, `package.json`, START и R09 внешнего аудита.
- Не найдено / противоречит: не выявлено. Живая пользовательская приёмка не
  подменяется автоматическими fixtures и будет отмечена отдельно.
- Стоп-условия: все восемь — нет; задача только проверяет существующее поведение.
  Если прогон выявит дефект, он фиксируется как `FAIL` и выносится в отдельную задачу.
- Требуется решение владельца: нет для выполнения проверок и подготовки Draft PR.

## План и состояние

- Завершено: создана чистая ветка от актуального `origin/main`; прочитаны источники;
  зафиксированы границы, проверки и откат.
- Завершено: перенесены 42 критерия в `docs/evc/evidence/program01-r09/acceptance-evidence.xlsx`;
  выполнены lint/build, frontend, backend, HTTP, PostgreSQL integration и browser.
- Активный шаг: независимое review evidence и подготовка Draft PR.
- Следующий шаг: проверить diff/ссылки, закоммитить evidence и передать Draft PR.
- Ветка / commit / PR: `codex/program01-r09`; commit и PR ещё не созданы.

## Действия выпуска

- `branch_push=true`: после завершения локального evidence.
- `pr=true`: Draft PR для независимого review.
- `merge=false`.
- `deploy=false`.
- `version_bump=false`: R09 не меняет продуктовый runtime.
- `artifact_publish=false`.

## Ограничения и риски

- Совместимость: runtime не меняется.
- Данные и миграции: схема не меняется; integration только в изолированной БД
  с `test`/`pytest` в имени.
- Безопасность: без секретов, production/test пользовательских данных и PII.
- Внешние сервисы/LLM: реальные LLM-вызовы не выполняются.
- Эксплуатация: CI, merge, deploy и живая приёмка фиксируются отдельными фактами.

## Критерии приёмки

- [x] Все 16 + 26 критериев имеют фактический статус, условия и доказательство.
- [x] Исторические PASS/числа привязаны к исходному SHA и не выданы за новый прогон.
- [x] Выполнены lint/build/dist, frontend/backend/HTTP, адресная PostgreSQL
  integration и применимые browser/viewport/accessibility проверки.
- [x] Проверены два назначения одной конфигурации, выбор последнего profile/job и
  legacy `Cycle.assignment_id=NULL` по AC11/ST03/CA04.
- [x] CI, merge, deploy и живая приёмка отделены от локальных результатов.

## План проверки

- `git diff --check`; `npm run lint:js`; `npm run build:web`; проверка чистого dist.
- Frontend regression; `npm run test:backend`; `npm run test:backend:http`.
- `TEST_DATABASE_URL=… npm run test:backend:integration` на изолированной БД.
- Применимые Playwright-наборы PROGRAM01/ADM-STATUS, viewport и accessibility.
- Полный CI Draft/Ready относится к точному будущему head PR.

## Откат

Revert единственного evidence-коммита или закрытие PR. Runtime и данные не меняются.

## Результат

- Evidence workbook содержит 42 критерия: `40 PASS`, `0 FAIL`, `2 NOT_RUN`.
- `AC16 NOT_RUN`: исходный инцидент конкретной тестовой организации не
  воспроизводился повторно; реальные пользовательские данные и письма не использовались.
- `RG03 NOT_RUN`: независимое визуальное сравнение с `prototype.html` на R09 не
  повторялось. При этом затронутые viewport/accessibility browser-тесты прошли.
- Runtime не менялся; `web/dist` после повторной сборки совпал с Git.

## Проверки (команда → результат)

- `git diff --check` → PASS.
- `npm run lint:js` → PASS.
- `npm run build:web` → PASS; изменений `web/dist` нет.
- `node --test tests/frontend/*.test.mjs` → `131 passed`.
- `.venv/bin/python -m pytest -m "not integration and not e2e and not llm"`
  → `696 passed`, `317 deselected`.
- `.venv/bin/python -m pytest -m e2e tests/e2e` → `106 passed`, `12 deselected`.
- Полный integration с `TEST_DATABASE_URL=…/f22_integration_pytest` → первый
  sandbox-запуск не получил доступ к localhost; разрешённый повтор дал `199 passed`,
  `6 failed`, `2 skipped`. Все шесть падений имели общую причину: отсутствовал
  отдельный `STAND_ADMIN_URL=…/postgres`. Адресный повтор с ним → `7 passed`;
  итог всех `207` integration-тестов PASS, два explicit real-provider теста SKIP.
- Полный Playwright → `88 passed`, `16 failed` из-за отсутствующего `.venv` внутри
  worktree. Повтор 16 standalone-тестов с временной ссылкой → `15 passed`, один
  S10-A timeout на 5-секундном UI readback после уже сохранённых Report/PDF.
  Диагностический повтор S10-A на новом disposable-стенде → `1 passed`.
  Итог: все `104` browser-сценария подтверждены; нестабильность тайминга записана.
- Workbook: пересчёт, inspect ключевой области, поиск formula errors (0 совпадений)
  и render всех трёх вкладок → PASS.

## Непроверенное (что и почему)

- Живой повтор исходного инцидента тестовой организации: NOT_RUN, потому что R09
  не использует реальные пользовательские данные, приглашения и письма.
- Независимое сравнение с prototype: NOT_RUN; автоматические viewport и
  accessibility проверки не выданы за это сравнение.
- Новый CI R09: ожидается после создания PR. Исторический CI/deploy `d33670f`
  сохранён отдельным фактом, а не подменяет CI будущего head evidence-коммита.

## Риски: конфиг / схема / деплой / безопасность / откат

- Конфигурация, схема и runtime не меняются. Миграции и deploy не выполнялись.
- Все DB/browser данные синтетические; использованы только изолированные БД с
  `test`/`pytest` в имени. Секреты и персональные данные не сохранялись.
- Откат: revert evidence-коммита или закрытие PR; данные приложения не затронуты.

## Следующий минимальный шаг

Выполнить review workbook и task report, затем создать Draft PR. После CI владелец
отдельно решает, достаточно ли `AC16/RG03 NOT_RUN` или нужна живая ручная приёмка.

## Открытые вопросы (блокеры)

Нет для Draft PR. `AC16` и `RG03` блокируют заявление о полном закрытии всех
критериев, но не блокируют передачу честного evidence-пакета на review.
