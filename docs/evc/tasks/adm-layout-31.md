# ADM-LAYOUT-31 — кабинет подготовки организации

## Результат

Организационный администратор получает единую адаптивную композицию подготовки:
шапку аккаунта, участников, сведения организации, анкету, предпросмотр и подтверждение
без изменения методологии, прав или правил назначения.

## Область

- Включено: org-admin UI, существующие операции участников и анкеты, регрессии UI/браузера.
- Не входит: superadmin UI, публикация программ, scoring/timers, новые права,
  конкретные получатели сверх действующего контракта. P06 включает минимальную
  совместимую связь поколения назначения с M5 Cycle и запрет старта после отмены.

## Контекст

- Основание: запрос владельца 2026-10-31 и пакет
  `P4K_Admin_Layout_Audit_Tasks_2026-10-31_v1.zip` (MANIFEST проверен PASS).
- Значимые точки входа: `web/index.html`, `web/js/screens/admin/organizations.js`,
  `web/styles/screens/admin-organizations.css`, `tests/browser/auth-r03.spec.mjs`.
- Архитектура/ADR: Product 4K context 1.0, Registry, ADR-003; PM/LU и runtime-контракты
  не меняются, это слой UI существующего org-admin API.
- Прослеживаемость: START_ARCHITECT/TASKS 01–06 и ADM-STATUS-01 → существующая
  серверная проекция → organizations.js/CSS → frontend/browser/HTTP проверки.
- Предметные артефакты: не создаются и не изменяются.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, EVC workflow/matrix/review,
  архитектурный context/registry, ADR-003; весь пакет задачи; ADMIN-2026-10-19
  DESIGN_CONTRACT; ADM-STATUS-01 START/ACCEPTANCE/STATUS_MATRIX.
- База реализации: `de8261d6455719d6c300554d01789118ec9c044c` / 2.0.44.
- Пакет аудировал более старый срез; все выводы повторно проверяются на базе выше.
- Принятые ранее решения не запрашиваются повторно. Прототипные данные и handlers
  не являются продуктовым контрактом и не копируются.
- Стоп-условия: методологическая неопределённость — нет; несовместимая миграция — нет;
  секреты/production данные — нет; расширение полномочий — нет. P06-ADD01 редакции 1.0
  явно разрешает отдельную cancel-operation и совместимое расширение хранения.
- Требуется решение владельца: нет.

## План и состояние

- Завершено: проверка пакета и источников; повторный аудит актуального main; shell;
  participant context/selection/status/action/menu; обновлённая серверная подпись готовности;
  frontend/build и browser viewport/keyboard регрессии.
- Активный шаг: полная регрессия P06 и I08 screenshots.
- Следующий шаг: обновить acceptance-артефакт, финальную сборку и выполнить CI.
- Ветка / implementation commit: `codex/adm-layout-31`, `aa46c97`, base `de8261d`.

## Действия выпуска

- `branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
  `version_bump=false`, `artifact_publish=false`.
- Меняются только по отдельному запросу владельца.

## Ограничения и риски

- Совместимость: публичный API и исторические данные сохраняются.
- Данные и миграции: совместимо добавляется `m5_cycles.assignment_id`; глобальная
  уникальность назначения заменяется частичной уникальностью одного активного поколения.
- Безопасность: только синтетические fixtures; реальные письма и LLM не запускаются.
- Откат: revert UI/test commit; серверные данные не преобразуются.

## Критерии приёмки

- [x] S01–S05: шапка независима от длины имени, semantic navigation, mobile без overflow.
- [ ] P01–P05: компактный participant layout, status/action/menu, selection и responsive.
- [x] P06 implementation: отдельная idempotent cancel-operation, аудит, точная связь
  assignment→Cycle, запрет старта, статус UI и повторное новое поколение реализованы.
- [ ] P06 acceptance: полный набор P06.01–12 и регрессия отзыва приглашения ещё проверяются.
- [x] D01–D06: сведения и readiness в принятой двухколоночной композиции.
- [x] Q01–Q05: анкета различает состояния и не смешивается с импортом участников.
- [x] C01–C06: dialog preview, cancel/Escape, stale/double-submit/focus сохранены.
- [ ] I01–I07: локальная сквозная приёмка пройдена; CI ещё NOT_RUN.
- [x] I08: воспроизводимые before `de8261d` / after screenshots приложены в
  `docs/evc/evidence/adm-layout-31`, включая P06 confirmation/conflict/success.

## План проверки

- UI/JS: `node --check`, frontend tests, `npm run build:web`, `git diff --check`.
- Browser: адресные Playwright-сценарии на 320/390/768/1100/1101/1120/1160/1440
  и эквивалент 200% zoom, клавиатура/Escape/focus.
- HTTP/integration: endpoint, идемпотентность/аудит/поколение, запреты и управляемая
  гонка независимых транзакций в изолированной pytest DB.
- CI: frontend, pytest и full-verification перед merge.

Фактические результаты 2026-10-31:

- `node --test tests/frontend/*.test.mjs` — PASS, 120/120.
- `npm run build:web` — PASS.
- `tests/browser/auth-r03.spec.mjs` — PASS, 74/74, 2 evidence-only skipped.
- `pytest tests/unit tests/e2e/test_adm27_assignment_http.py -q` — PASS, 678/678.
- `Api/routes.py` py_compile — PASS; `git diff --check` — PASS.
- P06 HTTP regression — PASS, `tests/e2e/test_adm27_assignment_http.py`.
- P06 isolated PostgreSQL — PASS, 16/16: аудит/idempotency/rollback, все started
  состояния, оба порядка cancel/start, parallel cancel/reassignment и новое поколение.
- CI — NOT_RUN на текущем незакоммиченном срезе; live-стенд I05 — NOT_RUN.
