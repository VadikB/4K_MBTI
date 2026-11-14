# STATE REMAIN_04

- Исполнитель: Codex пользователя, машина Vadim/macOS; сессия P4K-REMAIN-04-v1.6. Один активный писатель этой ветки.
- Ветка codex/p4k-remain-04; worktree worktrees/p4k-remain-04. Base ae25fd5a (origin/main после fetch 14.11.2026; REMAIN_01 #215, 02 #216, 03 #217 уже включены).
- Корневой каталог другой задачи с dirty diff не изменяется.
- Общие функции до правки: Api/acquaintance.py early_readiness/late_readiness — владелец 04; source current_binding — контракт 01, точный активный assignment и revision; questionnaire_sources.assignment_readiness — владелец 02, latest по умолчанию для admin/new assignment, дополнительный exact revision для participant. router.openAcquaintanceWaiting и wiring click — владелец 04. Остальные функции routes/organizations не меняются.
- Завершено: разведка. Подтверждены latest revision drift, обязательная position, participant waiting→legacy chat. Активный шаг: адресные исправления и регрессии.

## Профиль до запуска

RUN_ID remain04-controlled-20261114; base/tested ae25fd5a + будущий diff (точный SHA записать после commit). Один worker, общий deadline 20 мин, preflight 120 с, тест 90 с, HTTP 15 с, no-progress 60 с, full retries 0, SDK retries 0, real LLM/mail 0. Browser ≤100 действий/сценарий, HTTP ≤40, readback ≤12/operation, доставки ≤4 только идемпотентность; teardown 60 с/grace 15 с. Логи ≤10 MiB/process, artifacts ≤100 MiB/run.

Конечные варианты: A/B revisions exact и org B; projection readonly/403; missing/unconfirmed/failed/late GET; минимальные ФИО + W02 + replay/rollback/new assignment/старый checksum; foreign/config/checksum; waiting login/directURL/reload/check/viewport/Tab; назначение во время ожидания, A→B, org-admin и superadmin регрессия. STOP profile readback.

Ресурсы до старта: собственных PID/container/DB/портов нет. Зависимости symlink .venv и node_modules на корневые установленные библиотеки; .env не копируется/не читается. План PG: один owned PostgreSQL 15 cluster /private/tmp/p4k-remain04-pg, порт 55444, роль remain04, DB agent4k_pytest, restart=no (без supervisor). initdb/pg_ctl, статус pg_isready и pg_ctl status; stop pg_ctl -D /private/tmp/p4k-remain04-pg -m fast stop. Server browser fixtures краткоживущие в Playwright beforeAll/afterAll, порт 18784. При аварии останавливать только свои PID из postmaster.pid / команд текущей сессии; чужие ресурсы не трогать. План test commands: npm scripts выше; targeted tests записать в CHECKS. Реальные secrets/PII не читать.

## Матрица проверок

PG PID 78017, порт 55444, каталог выше; restart supervisor отсутствует. initdb в sandbox отказал shared memory и удалил незавершённый каталог; повтор с разрешением успешен. Новый HTTP/PG 2 PASS; существующие M4/W02/scope 4 PASS; frontend 275 PASS; backend 1091 PASS, 85.60 с; lint/build PASS. Browser late logout PASS; directURL FAIL из-за отсутствия session-bootstrap в новой fixture, дополняется только fixture. Отменённые expectations position/email заменены на full_name в старой unit/HTTP negative matrix.

RUN_ID remain04-matrix-20261114: HTTP suite, полный isolated integration suite и адресный browser; один worker на suite, общий deadline 20 мин, test 90 с; существующие bootstrap component tests имеют проверенный subprocess timeout до 180 с (не повышение после timeout). Общий integration предел 1100 с, no-progress 60 с; runner PID 79515, PGID тот же, лог /private/tmp/p4k-remain04-integration.log. Контроль/stop: tool session 36333, SIGTERM только указанному PGID, grace 15 с. PG stop/status выше. Playwright afterAll закрывает сервер 18784; external preview не оставляется. Реальные LLM/mail 0. Новые 04 сценарии заканчиваются профилем; существующие downstream component-регрессии выполняют свои минимальные fixtures, не новый полный путь.

## Регрессия старого component-контура

Полный integration RUN: 399 PASS, 2 skipped, 5 FAIL за 674.50 с (старый seed ожидает consent без назначения). FAIL сохранён в /private/tmp/p4k-remain04-integration.log. Product guard не ослаблялся. Test-only legacy_acquaintance_fixture применяется только в старом E10.2 seed / M4 component / browser_component_app: disabled provider/gateway1/owned marker/product4k_pytest; actual legacy validator сохраняется, при наличии managed bindings выполняется обычный early_readiness. Это SYNTHETIC upstream source boundary, не доказательство F24/F26. В новом remain04 SQL/HTTP/browser её нет.

Адресный follow-up RUN_ID remain04-legacy-regression-20261114: тот же cluster/DB; targeted remain04/review_m4/w02/scope + пять упавших bootstrap/f02/path29/path_admin/profile_access и затронутый profile_to_m4. Общий срок 20 мин, inherited bootstrap test subprocess 240 с (проверенный до запуска existing profile), HTTP15 с, 1 worker, full retries0, llm/mail0. Стоп-команда SIGTERM только pytest PID/PGID данного tool session; grace15 с. Прогресс - окончание test или saved child stages; наблюдение max60 с между отчётами. После результата повторяется только реально затронутый browser runtime component, без длинного оценивания/Report ради 04.
