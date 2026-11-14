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

## Итог рабочего цикла и передача

- **Результат:** REMAIN_04 v1.6 реализован. F24/F25/F26 — 9 технических AC PASS в комбинации настоящих HTTP/SQL и controlled VM/browser; ограничения отдельно в CHECKS. Participant exact binding, admin latest; optional position/email не блокируют; waiting check/error/late owner без legacy, start и мутаций. Новое назначение даёт новый профиль; прежний snapshot неизменен.
- **Git:** base `ae25fd5a5347ecfb3383e4632e1450a06b9f4a60`; code candidate/tested `57f56f863ad9535045b758ae6f2b1d451d9ff177`; первый рабочий commit `24c4d0e631fbd06474a1fe5e76c676bfa2aac55c`. Финальный commit после него содержит только отчёт/первичные receipts. `origin/main` повторно fetched перед передачей — тот же ae25fd5a, конфликтов нет. Ветка `codex/p4k-remain-04`.
- **Проверки:** exact code SHA: backend1092 PASS, HTTP153 PASS, frontend275 PASS, lint/build/diff PASS; финальные PostgreSQL/HTTP3 PASS; browser04 2 PASS + регрессии admin/superadmin/W02 3 PASS. Первичный полный integration399 PASS/2 skipped/5 FAIL сохранён; все пять FAIL закрыты адресными повторами, 399 PASS переиспользованы по неизменённой области. Нет заявления «полный run exit0» после исправлений. В CHECKS — команды, область повторного использования и первичные receipts.
- **Профиль:** real LLM/mail0; новый browser/SQL STOP на readback профиля, без AS/Cycle/Report. Старые downstream component integration — отдельные минимальные регрессии, с явной synthetic legacy source boundary и прежним component upstream plan gate; не доказывают продуктовый допуск/GC.
- **Изменённые пути:** Api/acquaintance.py, assessment_assignment_sources.py, questionnaire_sources.py; web/js/router.js, wiring.js, screens/onboarding.js, styles/screens/auth.css и собранный dist. Регрессии: frontend/remain04-waiting, browser/remain04-waiting, integration/remain04_acquaintance, старые path_start_readiness unit/HTTP. Совместимость fixture: scripts/test_stand_seed.py, tests/legacy_acquaintance_fixture.py, browser_component_app.py, browser/runtime.spec.mjs, integration/profile_to_m4_owned_stand и path_admin_contract_owned_stand; unit guard fixture. Документы задачи/receipts — этот каталог. Несвязанный refactor, управляющие документы, runtime-артефакты, конфиг и схема не менялись.
- **Риски:** test-only legacy substitution сохраняет прежние component-проверки, но не является современным назначением. CI full-verification должен проверить точный будущий PR head. Native zoom/физический телефон, человеческое review и визуальная приёмка TEST NOT_RUN. CURRENT/методологический статус не повышались.
- **Откат:** revert собственных code commits 57f56f86 затем 24c4d0e6; не менять сохранённые профили, source bindings и старые Cycle. Миграция/восстановление данных не требуются.
- **Ресурсы:** nested product4k_pytest DB count0; agent4k_pytest удалена отдельно успешным dropdb. pg_ctl fast stop exit0; pg_isready no response (ожидаемый exit1), postmaster.pid отсутствует; собственный cluster directory удалён. LISTEN на 55444/18784/18764/18730/18731 отсутствует. Все test/Playwright процессы завершены, servers закрыты afterAll. restart=no/supervisor отсутствует, Docker не создавался. Логи synthetic controlled run сохранены в /private/tmp и безопасные выбранные receipts — здесь; running=false. Временные symlink .venv/node_modules удаляются после последней команды проверки.
- **Действия выпуска:** branch_push=false, pr=false, merge=false, deploy=false, version_bump=false, artifact_publish=false. Номер main 2.1.3 не изменялся; `ready:prepare` NOT_RUN, потому что это передача кода, не разрешённый выпуск. Baseline не присваивался. Bundle: `/private/tmp/p4k-remain-04.bundle`, base..HEAD, без корневого dirty diff и без секретов.
- **Следующий шаг:** архитектор импортирует bundle/ветку, сверяет base/candidate/tested SHA и общий helper с main, утверждает продуктовый номер, создаёт PR своим аккаунтом; затем обязательные frontend/pytest/full-verification, human review и отдельная приёмка. PM-03/REMAIN_05 получает immutable profile и exact readiness; start транспорт не менялся. Следующая карточка не запускалась.
- **Вопросы владельцу:** новых предметных/архитектурных блокеров нет. Выпуск и приёмка остаются отдельными полномочиями.

## Выпуск архитектором

- 14.11.2026 пользователь сообщил, что является архитектором, и разрешил подготовить
  и задеплоить PR. Независимые флаги изменены на `branch_push=true`, `pr=true`,
  `merge=true`, `deploy=true`, `version_bump=true`, `artifact_publish=false`.
- Выбран PATCH `2.1.4`, непосредственный преемник `main@2.1.3`; несовместимого API,
  миграции данных и нового предметного пакета нет.
- Fresh `origin/main` перед preflight остался `ae25fd5a`; `npm run ready:prepare --
  --candidate 2.1.4` и отдельный release check прошли. После release commit нужен
  идемпотентный повтор preflight на точном HEAD.
- Последовательность выпуска: commit/push → Ready PR → обязательные `frontend`,
  `pytest`, `full-verification` → squash merge без bypass → штатный `deploy-test` →
  read-only проверка версии и доступного SHA/asset-состава на TEST. Pilot/Prod и
  публикация methodology/configuration/prompt artifacts не включены.

### Описание будущего PR

Участник без назначения оставался с кнопкой, способной открыть legacy chat, а знакомство могло переключиться на последнюю анкету организации. Теперь ожидание проверяет server journey с защитой owner/epoch, briefing читает подтверждённую revision своего активного binding, а admin readiness сохраняет latest для новых назначений. Отсутствие должности/email не блокирует UserContext; исторические профили и организационные источники неизменны. Подписи кнопок ожидания переносятся при text200.

Проверено: backend1092, HTTP153, frontend275; controlled PostgreSQL/HTTP, VM и browser до профиля; отрицательные owner/source/checksum состояния и snapshot/replay/rollback. Старый component seed получил явно ограниченную upstream fixture без ослабления runtime guards; первичный full integration FAIL и адресные исправления сохранены. CI на PR head и человеческая приёмка обязательны; merge/deploy этой задачей не выполнялись.
