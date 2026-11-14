# STATE P4K-REMAIN-06-v1.6

Base07166475b478c843243102c748d51f8564b7cec0, codex/p4k-remain-06. Исполнитель Codex пользователя/REDMI-Note-15-Pro. Активно: before-регрессия и адресное исправление. Прочитанные источники/стоп-условия/допуски — TASK.md.

## Профиль до запуска

RUN_ID remain06-controlled-20261114, SHA base + exact diff/source fingerprints. Общий deadline1200с с начала первого теста; preflight120с; test90с; HTTP15с; no-progress60с (новый тест/этап/Turn/receipt, одинаковый heartbeat не прогресс). Один worker, retries0, SDK retries0, LLM/mail0. Browser≤100действий/сценарий, HTTP≤40, readback≤12/operation, deliveries≤4 для идемпотентности. Teardown60с/grace15с; логи≤10MiB/процесс, evidence≤100MiB. При лимите stop, PARTIAL/NOT_RUN сохраняются, без автоматического повышения.

Конечные варианты: renderer plan8/catalog9/materialized1 и plan3; time positive/0/null/missing/invalid; actual loader late owner/Cycle/AS/view; clipboard actual handler matrix; native browser long/short desktop1440/mobile320/390/430/768 + text200/scroll/focus/draft/IME, pendingGET/network/reload/Continue lost-response; owned PG selected m7_cycle_planner return179/R1/presence119-120/saved-policy/fail-closed + read_runtime frozen8. По необходимости один Turn на R1 browser fixture. Не запускать полный p3-a suite/Report.

Команды: python3 receipts/bounded-runner.py --seconds <remaining<=1200> --idle60 --log <receipt> -- node --test <target>; npm run lint:js/build:web; playwright test --workers1 --retries0 --timeout90000; PYTHON_DOTENV_DISABLED=1 pytest --run-integration выбранные m7 tests. Runner reuse: предыдущий immutable runner-controls.json читается отдельно перед run, без изменения validator.

Ресурсы до старта: своих workers/servers/browser/DB/container нет; symlink node_modules/.venv к существующим зависимостям, .env не читать. Docker не используется. Owned PostgreSQL15: /private/tmp/p4k-remain06-pg, port55446, role remain06, DB agent4k_pytest, UTF8, shared_buffers128MB/max_connections20; restart=no, supervisor нет. Старт initdb/pg_ctl, status pg_ctl -D ... status; stop pg_ctl -D /private/tmp/p4k-remain06-pg -m fast -w stop. Browser server p3-a-preview owned port18936 или встроенный server port0; PIDs записать при старте. Остановка workers: TERM только зарегистрированный PGID, grace15с/KILL; browser/server teardown в finally. При failure сначала inspect/readback, unknown сохраняет owned volume при остановленном вычислении. Удалять только подтверждённую owned DB после readback; чужие ресурсы не трогать. Фактический cleanup требует PID/port/DB проверки.

Owned PG started: PID1140, port55446; initdb первый sandboxFAIL shmget, эскалация разрешена, UTF8/initdb/start/create agent4k_pytest PASS. БД01/TEST/production не читаются.
Before renderer12:9FAIL/3PASS; after targeted53PASS; frontend317PASS, lint/buildPASS. Таймер run-clock.json остаётся исходный, deadline не продлевается.

PG first10:2FAIL (новая fixture missing recognized_at),8PASS; corrected10PASS,8.5с. Product SQL/API не менялись. RUN browser-component PID/PGID1328, ephemeral localhost port,180с/test90/idle60. Далее owned p3-a R1 port18935 + long/short viewport reuse18933; STATE исходные18936/port0 уточнены до старта. Browser selection R1 existing one Turn + new lost-response no Turn, без первого startup test с дополнительным ответом.

## Финал реализации и controlled run

Code candidate17291144c6d96a56db4cac30292427f327da69a9 сохранён локальным commit. PASS:frontend321, PG10, HTTP/unit5, browsercomponent3 + R1realPG2 + layout3, lint/build/diff. Исторические beforeFAIL/fixtureFAIL сохранены. Все15AC и PARTIAL native границы — CHECKS.md. Startup fingerprints base+dirty проверены против byte-identical code candidate. Api/policies unchanged. Локальный минимум выполнен; release version/remote CI/human review NOT_RUN.

Controlled run закончен до1200с. PG1140 stopped/no server, .teststand owned DB gone, agent4k_pytest dropped(0schemas/0connections), /private/tmp/p4k-remain06-pg removed; registered process groups exited, ports55446/18935/18933 free, restart=no, no containers. Preview для будущего просмотра не оставлен. Bundle готовится без push/PR; исходная пользовательская dirty ветка не менялась. Следующий шаг принадлежит архитектору/reviewer, не запуск другой карточки.
