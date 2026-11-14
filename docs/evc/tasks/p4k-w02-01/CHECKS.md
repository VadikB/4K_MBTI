# Проверки P4K-W02-01

Initial base `07166475b478c843243102c748d51f8564b7cec0` /2.1.5.
Final base `b0bf7a4e8e4f0fe70c400525a373b9822229dfdc` /2.1.6; candidate2.1.7.
Первоначальный source/tested SHA `a52e8909c0a1ce850d08c2d83c3e35dbe7a59919`;
хеши runtime совпадают с checked-content.json. Handoff после него — только docs.

| AC | Результат | Первичное доказательство / граница |
| --- | --- | --- |
| AC01 | PASS TECH, human visual PENDING | W02 browser1440×1024/390×844/320×844; computed styles, keyboard focus007D89, Onest, цвета, отсутствие полосы/подписи, длинный ответ и форма. 6 характерных PNG в evidence. HTML прототипа недоступен: без sandbox DNS denied, с доступом HTTP401; сверка по достаточному текстовому эталону. |
| AC02 | PASS TECH | Реальный bundled frontend, controlled contract responses с реальной schema object из definition.json; server consent text/version7, три question text/order и answer1–3, сводка и3 действия. Динамические ФИО/организация/назначенная роль, пустая должность «Не указано». |
| AC03 | PASS TECH | Общая форма3textarea, изменение второго ответа, отмена,503save failure сохраняет draft, повтор сохраняет, reload читает обновлённую сводку; confirmation единственный, история read-only. PATH29 fixture адаптирован к общей форме; адресный actual backend/HTTP/ownedPG run PASS24.3s. |
| AC04 | PASS TECH (UI contract) | POST существующего issues с обоих шагов,201receipt обязателен; controlled network failure + безопасный повтор, сообщение сохраняется, роль/шаг/consent/answers не меняются. Backend handler не менялся. Tenant/authorization регрессии сохраняются в test_w02_acquaintance_db.py и mandatory CI; не выдаётся за локальный новый DB run. |
| AC05 | PASS TECH | Browser reload подтверждения/ответов и возврат dashboard→history; scoped-draft/late-readback frontend регрессии PASS. REMAIN04 late waiting response после logout PASS. Подготовка/старт не переработаны;11адресных browser включают существующие REMAIN05 normal/unknown first start. |

Команды/результаты (logs в evidence):

- `npm run ready:prepare -- --candidate 2.1.7` — exit0; fresh mainb0bf7a4.
- `npm run lint:js` — exit0.
- `npm run build:web` — exit0; dist пересобран штатно.
- `node --test tests/frontend/*.test.mjs` —324 PASS,0FAIL, включая scopes/late-readback.
- `python3.12 scripts/check_release_version.py --base-ref origin/main` —2.1.7 PASS.
- `git diff --check` —exit0.
- Browser final run07:11 PASS,0FAIL/retries0,12.6s. Команда и PID группы в runner.json,
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

Финальный source/candidate/tested SHA: `ea78b533b031faabd560d33709e793fb9efc4687`.
После baseline — только mobile CSS padding16px для48px-кнопки на320px;
run07 проверяет финальныйCSS, frontend324 переиспользован по совпадению JS-хешей.
Актуальные checks и CI receipt привязаны к PR head.

CI head4131fea: frontend/pytest/integration и4runtime groupsPASS; fast256PASS,1SKIP,
1FAIL — PATH29 ещё ожидал старыйцветF6F9F9 и прежнюю вертикальную геометрию.
Oracle приведён к W02F7F7F7 и composer; продуктовые файлы не менялись.
Адресный PATH29 на ownedPG55493:1PASS24.3s, role/consent/answers/редактирование/
reload/readonlyhistory/возвраткactiveAS прошли через actual backend/HTTP/БД.
Первый localattempt остановился доapp из-за brokenvenv, причина устранена своим
минимальным CIvenv. ОбаownedPGcluster остановлены, ports55493/18859свободны.
ПервичныйCIлог сохранёнgzip, path-run/result подтверждают finite-profile+stop.
Новый обязательныйCI текущегоhead ожидается; прежнийFAILне заменён старымPASS.


## ADD01 — актуальная проверка визуальной дельты

Исходный SHA `47d11f72a9c54c9a8a302fb96ba474a7a632f708` (прежний CI PASS).
Base/main `b0bf7a4e8e4f0fe70c400525a373b9822229dfdc`, кандидат **2.1.7** сохранён.
Новый source SHA фиксируется в STATE после commit; точный PR/CI head — в локальном
RELEASE_STATUS.json после CI. История проверок выше не является CI нового head.

| Пункт | Результат сверки по ADD01 / W02_REFERENCE |
| --- | --- |
| 1 | Текстовое действие на identity/summary:400,14/20,#007D89,underline,transparent,border0; прежний handler/button keyboard/focus сохранены. |
| 2 | Composer: белый отдельный block1120px, border-box,padding16,radius8,gap16; вокруг#F7F7F7, полноширинная линия/белая полоса отсутствуют. |
| 3 | «Отправить»200×48px на desktop, поле/отправкаdisabled при действиях, точный placeholder. Вопросы отправляют через прежний handler/API. Mobile — колонка/полная ширина; точный HTML недоступен. |
| 4 | Labels400,14/20,#464554,margin-bottom6; answers400,16/24,#222C30; иерархия заголовка сохранена. |
| 5 | Один question-hint400,14/21,#464554 для трёх вопросов и их истории. |
| 6 | Примечание400,14/21,#464554; border-left3#CBD5E1,padding-left14,margin-top20. |
| 7 | Стрелка скрыта (display:none, вне keyboard path); бирюзовая точка после названия. Desktop section center720px; мобильное размещение справа сохранено. |
| 8 | Основная600/вторичная500,16/24; действия под сообщением; фокус сохранён. Обе кнопки48px после поправки padding вторичной11px. |

Контрольный снимок: `evidence/add01/1440-summary-1440.png`,1440×1024.
Сверка Codex по8пунктам и computed styles: `1440-add01-computed.json`.
Это техническая сверка по текстовым источникам; пиксельное совпадение с недоступным
HTML и приёмка человеком не объявлены. Сайт вновь недоступен черезweb.open.

Команды и первичные результаты (каталог evidence/add01):

- `npm run lint:js` —exit0/lint.log.
- `node --test tests/frontend/*.test.mjs` —324PASS/0FAIL/frontend.log.
- `npm run build:web` —exit0/build.log, затем штатный ready:prepare idempotent build.
- `npm run ready:prepare -- --candidate 2.1.7` —exit0/ready-prepare.log, freshmainb0bf7a4.
- `git diff --check` —exit0; финальная запись в diff-check.log.
- Existing W02 only1440px +REMAIN05:4PASS/4.7s; initial-browser.log.
- После установленного50px→48px visualfix повтор onlyW02:1PASS/2.9s;
  browser.log/runner-result.json, own groupabsent=true. JS и frontend324 прежние.
- Existing PATH29 actual frontend/HTTP/ownedPG:1PASS/21.5s; path-browser.log,
  wrapper23.01s/path-run-result.json. Это проверка адаптированных существующих
  fixtures, новых тестов только дляCSS и полной новой матрицы не вводилось.
- Все собственные fixture ports60075/60111 закрыты; PG55493/backend18859 закрыты,
  pg_stopped=true; ports-stopped.json и path-run-result.json. ЧужойPG55432 сохранён.
- RuntimeSHA256 — checked-content.json; backend/API/БД definitions не менялись.

Профиль:1worker/retries0,total600s/no-progress90s, штатные deadline/teardown,
реальныеLLM=0/письма=0. Повторы только после выявленной причины; продуктивныйCSSfix1.
Команда воспроизведения односнимочного preview-сценария — текущий ADD01 блок STATE.

Следующий шаг: push того же PR221 и mandatory frontend/pytest/full-verification
точного нового head. Human reviewPENDING. Ручные длинные ответы/форма/телефон по
принятому ADD01 отложены послеmain/TEST; merge/deploy по-прежнему требуют допуска.

ADD01 новый source/candidate/tested SHA: `2c620afe506d28e69cd59087c74c27169313434e`.
Runtime bytes соответствуют evidence/add01/checked-content.json; следующий
handoff commit меняет только STATE/CHECKS. Обязательный CI проверяет точный
финальный PR head; итоговые SHA/links/status в RELEASE_STATUS.json после CI.


### Уточнение после доступа к HTML W02 v5

Владелец прямо разрешил повторный вход в ChatGPT и затем Google sign-in.
IAB открыл эталон; прежний пробел доступа закрыт. Sitesread подтверждаетversion5,
DOM/computed styles сводки просмотрены адресно1440/390 (не новая матрица).
Первичное чтение — evidence/add01/reference-dom-styles.json. Встроенные шрифты,
секреты и учётные данные не копировались. СкачиваниеHTML превысилоtimeout;
дальше использован уже доступный DOM, повтор скачивания не выполнялся.
Дельта относительно43d16e2:mobilecomposer padding/gap12, label14/21,
textarea padding11/12, textaction44px/padding10, dot7desktop/5mobile,
mobile section12/16/actionsgap12. Это уточнение тех же8пунктов, без API/JSfix.
Кнопки48px сохранены по явному текстовому REFERENCE; HTML secondary50px включает
border, его механическое копирование нарушило бы явную высоту48px.
Перед controlledrun `w02-add01-html-final` — своих PID/containers/DB нет;
исходные foreignlisteners прежние. Тот же finiteprofile600s/90s/1worker/0retries,
noLLM/noletters и прежний runner/commands; W02only1440px +REMAIN05.
Перед адреснымPATH29 — новыйcluster `.test-stand/w02-pg-add01-html`,
PG55493/backend18859, рольstand_owner, синтетическая product4k_pytest DB.
Старт python3 /tmp/p4k-w02-add01-html-path.py; status/stop с новымclusterpath
штатные, ownedgroups иPID до использования фиксируются в evidence/add01/path-run.json.
Повтор обусловлен полученным новым исходным HTML и конкретной CSSдельтой.
Текущий CI43d16e2 относится к прежнемуCSS; послеpush новыйhead проходит весьCI.

Уточнение поHTML проверено: W02+REMAIN05 4PASS/4.6s, ownGroupabsent=true;
PATH29 actualHTTP/ownedPG 1PASS/20.6s, PG55493/backend18859free/pg_stopped=true.
Один контрольный summaryPNG обновлён; frontend324/lint/build переиспользованы
по неизменнымJS/bundleхешам, CSS проверен снимком/computedstyles/PATH29.
Все8пунктов ADD01 закрыты технически, доступHTML теперьPASS, humanreviewPENDING.
CI43d16e2 завершился9PASS; он исторический, после CSSуточнений нуженCI новогоhead.
