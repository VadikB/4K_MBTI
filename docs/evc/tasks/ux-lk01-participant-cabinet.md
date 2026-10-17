# UX-LK01 — личный кабинет участника

## Результат

Личный кабинет «Мои оценки» показывает server-owned назначения и Cycle: текущие
оценки, подтверждённый прогресс по позициям сохранённого route, эффективный deadline
после старта и по одной карточке каждого закрытого Cycle. Из кабинета участник явно
возвращается в знакомство, подготовленный/начатый Cycle, E02 или разрешённый M8 Report.
Чтение кабинета не создаёт Cycle/AS и не меняет время.

## Область

- Включено: read model кабинета, карточки текущих/закрытых Cycle, переходы, пустые
  состояния, мобильная компоновка и адресные регрессии.
- Не входит: содержание UX-REP01, новая самостоятельная оценка, каталог продуктов,
  административная аналитика, изменение M5–M8 предметной логики, миграция legacy Session.

## Источники и решения

- Постановка владельца: `UX-LK01_Participant_Cabinet_2026-10-16.txt`, редакция 1.0.
- База: `origin/main` / `ba4f544`, PR #58 UX-E02, версия приложения 2.1.37.
- Прочитано: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `verification-matrix.md`, `artifact-recipe.md`, `task-template.md`, `review-checklist.md`;
  Registry/context, Change 01 README и manifest, ADR-002, traceability и
  `m8-partial-result-contract.md`; отчёты UX-E01/UX-E02.
- `P4K_Product_Development_Principles.txt` не найден в репозитории и доступном
  `Downloads`; не использован как источник. Заданные LK01 правила и действующие
  контракты достаточны для read-only UI/read-model изменения.
- Применимый комплект: Change 01 WORKING; M1 v1.4, M5 v1.1, M7 v1.3, M8 v1.2
  FROZEN; CURRENT не присваивается, runtime publication не расширяется.
- Переиспользовано: owner scope и дедупликация Cycle из `m8_results.list_owned_cycles`,
  E02 status/failure priority, M7 `route_progress` и effective calendar deadline.

## Прослеживаемость

| Правило | Контракт/данные | Реализация | Проверка |
| --- | --- | --- | --- |
| Один факт состояния, один Cycle | owner-scoped Cycle/M8 history | `Api/routes.py::_build_dashboard` | frontend + HTTP/CI |
| Прогресс не по AS count | M7 saved route positions | `m7_route_positions` aggregation | LK01 regression + integration |
| Один закрытый Cycle, не версии Report | M8 owner history | `completed_assessments` | owned-stand integration |
| Явные переходы E01/E02/M8 | Cycle ID + action | `web/js/screens/dashboard.js` | frontend/browser |
| Deadline только после старта | M7 effective deadline | `m7_completion.read_status` | integration/browser |

## Стоп-условия и границы решения

- Новая схема/таблица, предметный fallback, новые права и mutating API не вводятся.
- Legacy поля `active_assessment`/`reports` временно сохранены для совместимости,
  но новый экран их не использует как источник состояния.
- Несколько текущих Cycle не объединяются; выбранный `cycle_id` сохраняется перед
  переходом. Не создаётся действие «пройти снова».
- Пользовательский untracked `docs/evc/timer-and-configuration-storage.md` не менять
  и не включать в результат.

## Проверки

- `PYTHONPYCACHEPREFIX=/tmp/4k_lk01_pycache .venv/bin/python -m py_compile Api/routes.py Api/schemas.py` — PASS.
- `npm run lint:js` — PASS.
- `node --test tests/frontend/*.test.mjs` — PASS, 38/38.
- `python -m pytest -q tests/unit/test_participant_dashboard.py tests/unit/test_user_journey.py tests/e2e/test_m10_processing_recovery_http.py tests/e2e/test_m5_runtime_http.py` — PASS, 20/20.
- `npm run build:web` — PASS.
- `npx playwright test tests/browser/auth-r03.spec.mjs --grep "LK01 renders selected Cycle cards|refresh obeys server journey|E02 shows ready"` — PASS, 3/3 в Chromium desktop/mobile; первичный sandbox-запуск был заблокирован `listen EPERM`, повтор с разрешённым loopback прошёл.
- `git diff --check` — PASS.
- `npm run test:backend` — 423 PASS, 13 FAIL в существующих M6
  provider/admission fixtures (`DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED` /
  `INPUT_NOT_READY`); адресный LK01/E02/runtime набор PASS, обязательный чистый
  PostgreSQL backend/integration остаётся CI gate.
- `tests/integration/test_profile_to_m4_owned_stand.py` — NOT_RUN: локально нет
  изолированного `TEST_DATABASE_URL` с `test`/`pytest` в имени; pytest корректно SKIP.
- Реальные iOS Safari, Android/Windows/Яндекс и macOS Safari/Яндекс — NOT_RUN;
  содержательная пригодность Cases/AI/GC и реальные LLM — NOT_RUN и не доказываются UI fixtures.

## Откат и передача

Откат — revert единственного squash-коммита UX-LK01. Схема и сохранённые Cycle,
Results/Report, snapshots и интервалы времени не меняются. Перед merge обязательны
полный GitHub CI (`frontend`, `pytest`), review и приёмка владельцем.

- Ветка: `codex/ux-lk01-participant-cabinet`.
- PR/SHA/CI: заполняются после завершения локальной проверки и публикации PR.
