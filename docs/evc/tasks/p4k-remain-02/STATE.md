# REMAIN_02 — состояние

- Исполнитель: Codex пользователя, машина пользователя, 2026-11-14.
- Сессия: P4K-REMAIN-02-v1.6. Ветка: `codex/p4k-remain-02-org-recipients`; worktree: `worktrees/p4k-remain-02`.
- Base: `20add5cb1806afde0f5dd052973802b079811f63` (`origin/main` на старте). Исторический срез карточки `5a47e105`/TEST 2.1.0 не приравнен к текущему base.
- Активная карточка: REMAIN_02 v1.6, правила исполнения 1.0 (SHA-256 соответственно `8f4c9755300a8ad79663298b96deb8e5aa3b1f008d1429383013adcd2017a0da`, `ece5f67dde34f7771e0084789f40617131e99d767ad5d8a57cac320320796c31`).
- Владелец общих функций `Api/questionnaire_sources.py` confirm/assignment_readiness и `Api/m8_report_access.py` customer_can_read_report/list_customer_reports: эта ветка REMAIN_02. Контракт: текущая анкета без C04/contact/picker; старые CSV/черновики читаются; готовность без удалённых полей; ACL по текущему admin membership и связи Report→Results→Cycle→organization. `Api/acquaintance.py`, `web/js/screens/admin/organizations.js`, `web/js/wiring.js` — совместные участки, править только относящиеся к 02 функции.
- Завершено: разведка; отдельный worktree без посторонних изменений.
- Активный шаг: серверная совместимость анкеты и ACL; затем UI и затронутые тесты.
- Стоп: нет новых предметных норм, миграции, публикации или изменения TEST. При конфликте с REMAIN_01 в общей функции нужна сверка перед интеграцией.

## Конечный профиль проверки до запуска

- RUN_ID: `remain02-local-20261114-20add5cb`; candidate/tested SHA: пока `20add5cb`, после изменений указать фактический SHA/diff.
- План: unit `tests/unit/test_questionnaire_sources.py`; frontend `tests/frontend/rel01-report-access.test.mjs`; HTTP `tests/e2e/test_adm28_confirmation_http.py` и `test_m8_report_access_http.py`; isolated PostgreSQL `tests/integration/test_questionnaire_sources_db.py` и `test_m8_report_access_db.py`; затем матрица: `git diff --check`, `npm run lint:js`, `npm run build:web`, `npm run test:backend`, адресный browser, `npm run test:backend:integration` при изолированном TEST_DATABASE_URL.
- Варианты: manual/new CSV/old CSV/draft/lost response; author/confirm/scope; effective N при N+1; P/админы A,B,новый C,отозванный A/чужие; list/open/PDF; 320/390/1440/200% в одной fixture. Реальные LLM/mail: 0.
- Лимиты controlled run: общий 20 мин, preflight 120 с, тест 90 с, HTTP 15 с, без прогресса 60 с; 1 worker, retries full-run 0, SDK 0; browser ≤100, HTTP ≤40, readback ≤12/operation, доставка ≤4 только для идемпотентности. Docker при необходимости: 1 собственный комплект, 2 CPU/2 GiB, логи ≤10 MiB/процесс, артефакты ≤100 MiB/run, teardown 60 с/grace 15 с.
- Ресурсы на старте: собственных контейнеров, серверов, портов, PID/PGID, БД и volume нет. Старт/статус/остановка будут записаны до их создания. Неизвестные ресурсы не трогать. Для локального pytest без сервера: запуск конкретной команды, статус по exit code, остановка Ctrl-C только её PTY/session. При unknown сохранить данные и остановить вычисление (`DATA_RETAINED_COMPUTE_STOPPED`).

## Изолированная PostgreSQL — профиль перед запуском

- Docker daemon недоступен. Проверен установленный PostgreSQL 15.16; запускается один owned временный кластер с каталогом `/private/tmp/p4k-remain02-pg`, журналом `/private/tmp/p4k-remain02-postgres.log`, PID в `postmaster.pid`, портом `55432`, сокетом `/private/tmp`; restart supervisor отсутствует (`restart=no`). БД `remain02_pytest` создаётся только в этом кластере, volume Docker нет. Содержимое синтетическое.
- Старт: `/usr/local/opt/postgresql@15/bin/initdb -D /private/tmp/p4k-remain02-pg -A trust -U remain02`; `/usr/local/opt/postgresql@15/bin/pg_ctl -D /private/tmp/p4k-remain02-pg -o '-h 127.0.0.1 -p 55432 -c unix_socket_directories=/private/tmp' -l /private/tmp/p4k-remain02-postgres.log start`; `/usr/local/opt/postgresql@15/bin/createdb -h /private/tmp -p 55432 -U remain02 remain02_pytest`.
- Статус: `/usr/local/opt/postgresql@15/bin/pg_ctl -D /private/tmp/p4k-remain02-pg status`; `/usr/local/opt/postgresql@15/bin/pg_isready -h /private/tmp -p 55432`.
- Остановка при успехе/FAIL/таймауте: `/usr/local/opt/postgresql@15/bin/pg_ctl -D /private/tmp/p4k-remain02-pg -m fast stop`; затем status и порт. Данные не удаляются до проверки итога; при unknown оставить каталог и отметить `DATA_RETAINED_COMPUTE_STOPPED`. Никаких чужих процессов не останавливать.

- После полного integration: `remain02_pytest` переименована в `agent4k_pytest` в том же кластере для штатного `test_stand` (`127.0.0.1:55432`). Полный набор 393 PASS, 9 SKIP; относящийся к F13 actor HTTP использует отдельный marker-owned DB, поэтому перед его запуском `agent4k_pytest` удаляется командой `/usr/local/opt/postgresql@15/bin/dropdb -h 127.0.0.1 -p 55432 -U remain02 agent4k_pytest`. Затем тест сам создаёт и уничтожает свою marker-owned DB через `scripts/test_stand.py`; `STAND_ADMIN_URL` указывает только на maintenance `postgres` этого же временного кластера. При сбое сохранить state/evidence marker DB, вычисление остановить.

## Checkpoint перед кандидатом

- Завершено: backend questionnaire/готовность/ACL, UI и потребители, новый пример CSV 0.2 при неизменном 0.1, адресная регрессия, TASK/CHECKS. Изменения только REMAIN_02; общий TEST и другие карточки не менялись.
- Проверки на рабочем diff: `git diff --check` PASS; backend unit 1090 PASS; HTTP 153 PASS; frontend 272 PASS; lint/build PASS; полный integration на owned PostgreSQL 393 PASS/9 SKIP; адресный DB/HTTP 3 PASS; actor owned HTTP/PG PASS; browser guards 30 PASS, auth 17 PASS, visual 1 PASS, keyboard/widths 1 PASS. Данные о точном candidate SHA и bundle занести в передачу после коммита.
- Ресурсы: PostgreSQL PID 28939, порт 55432, `restart=no`; owned `agent4k_pytest` существует для финального запуска, marker-owned actor DB удалена тестом. Browser/HTTP preview servers остановлены Playwright teardown; постоянных worker/poller нет. После финальной проверки остановить PostgreSQL по указанной выше команде и проверить `running=false`/порт свободен.
- Текущий шаг: commit кандидата и проверки на его точном SHA; следующий шаг: cleanup ресурсов, передача bundle и ограничений архитектору. CI/PR/merge/deploy/Prod и человеческая приёмка остаются за внешним процессом.

## Финальный preflight после коммита кода

- Кодовый commit: `95edcfa8` (`git rev-parse HEAD` перед документальным checkpoint). RUN_ID `remain02-final-20261114-95edcfa8`, исходный код и `web/dist` соответствуют этому SHA. Следующий commit меняет только STATE/CHECKS; финальные тесты запускаются после него на его точном HEAD.
- Финальные команды: `npm run test:backend -- --quiet`, `npm run test:backend:http -- --quiet`, `TEST_DATABASE_URL=<owned agent4k_pytest 127.0.0.1:55432> npm run test:backend:integration -- --quiet`, `npm run lint:js`, `node --test tests/frontend/*.test.mjs`, `npm run build:web` с проверкой отсутствия diff. Профиль 20 мин/90 с/test/1 worker/0 retry и teardown указан выше; реальные LLM/mail 0.
- Свой ресурс перед стартом: PostgreSQL PID 28939, порт 55432, БД `agent4k_pytest`, restart supervisor отсутствует; marker DB actor-test удалена. Команды статуса/остановки выше. Внешние и неизвестные ресурсы не трогать.
