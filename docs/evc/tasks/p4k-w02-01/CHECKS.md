# Проверки P4K-W02-01

Initial base `07166475b478c843243102c748d51f8564b7cec0` /2.1.5.
Final base `b0bf7a4e8e4f0fe70c400525a373b9822229dfdc` /2.1.6; candidate2.1.7.
Первоначальный source/tested SHA `a52e8909c0a1ce850d08c2d83c3e35dbe7a59919`;
хеши runtime совпадают с checked-content.json. Handoff после него — только docs.

| AC | Результат | Первичное доказательство / граница |
| --- | --- | --- |
| AC01 | PASS TECH, human visual PENDING | W02 browser1440×1024/390×844/320×844; computed styles, keyboard focus007D89, Onest, цвета, отсутствие полосы/подписи, длинный ответ и форма. 6 характерных PNG в evidence. HTML прототипа недоступен: без sandbox DNS denied, с доступом HTTP401; сверка по достаточному текстовому эталону. |
| AC02 | PASS TECH | Реальный bundled frontend, controlled contract responses с реальной schema object из definition.json; server consent text/version7, три question text/order и answer1–3, сводка и3 действия. Динамические ФИО/организация/назначенная роль, пустая должность «Не указано». |
| AC03 | PASS TECH | Общая форма3textarea, изменение второго ответа, отмена,503save failure сохраняет draft, повтор сохраняет, reload читает обновлённую сводку; confirmation единственный, история read-only. PATH29 fixture адаптирован к общей форме, его HTTP/PG граница — mandatory CI. |
| AC04 | PASS TECH (UI contract) | POST существующего issues с обоих шагов,201receipt обязателен; controlled network failure + безопасный повтор, сообщение сохраняется, роль/шаг/consent/answers не меняются. Backend handler не менялся. Tenant/authorization регрессии сохраняются в test_w02_acquaintance_db.py и mandatory CI; не выдаётся за локальный новый DB run. |
| AC05 | PASS TECH | Browser reload подтверждения/ответов и возврат dashboard→history; scoped-draft/late-readback frontend регрессии PASS. REMAIN04 late waiting response после logout PASS. Подготовка/старт не переработаны;11адресных browser включают существующие REMAIN05 normal/unknown first start. |

Команды/результаты (logs в evidence):

- `npm run ready:prepare -- --candidate 2.1.7` — exit0; fresh mainb0bf7a4.
- `npm run lint:js` — exit0.
- `npm run build:web` — exit0; dist пересобран штатно.
- `node --test tests/frontend/*.test.mjs` —324 PASS,0FAIL, включая scopes/late-readback.
- `python3.12 scripts/check_release_version.py --base-ref origin/main` —2.1.7 PASS.
- `git diff --check` —exit0.
- Browser final run06:11 PASS,0FAIL/retries0,13.1s. Команда и PID группы в runner.json,
  итог runner-result.json; полный stdout browser.log. Run01 environment EPERM сохранён
  отдельно, не product FAIL; run02–05 — исправления после осмотра/нового diff.
- Финальное self-review: API, schema, rights, published definitions, PM contracts и
  управляющие документы неизменны. Shared CSS disabled opacity и mobile rules
  проверены; scoped CSS не затрагивает соседние экраны.

Воспроизведение снимков: из корня worktree
`W02_RUN_ID=w02-review-replay python3 docs/evc/tasks/p4k-w02-01/run-browser.py`.
Используются существующие Node/Playwright/Chromium, реальные LLM/письма=0,
локальные временные static servers, no database. Wrapper ограничен600s/90s без
прогресса, one worker/retries0, завершает свою process group. Новые server PID/ports
фиксируются в resources.jsonl, штатный afterAll подтверждает stop. `ports-stopped.json`
и runner-result подтверждают остановку своего, исходный PostgreSQL55432 не использован.

PR221: https://github.com/VadikB/4K_MBTI/pull/221; обязательный CI нового head PENDING после синхронизацииmain. Human review/merge/deploy/фактический TEST: NOT_RUN,
этим этапом не разрешены. Откат — revert собственного PR, данные не меняются.
