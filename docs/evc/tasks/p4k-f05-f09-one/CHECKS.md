# Проверки P4K-F05-F09-ONE

`PARTIAL` означает, что проверенная часть не закрывает весь AC. Данные только
синтетические; PostgreSQL 15 на `127.0.0.1:55432` принадлежит этой задаче.

Доказательства: E1 — `node --test tests/frontend/*.test.mjs` (271 PASS);
E2 — `npm run test:backend` (1089 PASS, 551 deselected);
E3 — `npm run test:backend:http` (153 PASS, 13 deselected); E4 — 31 PASS в
`test_questionnaire_sources_db.py`, `test_exec03_answer_status_db.py`,
`test_exec03_turn_replay_db.py`, `test_m5_runtime_db.py`,
`test_m10_product_path_db.py` на `p4k_f05_pytest`; E5 —
`questionnaire-it-inputs.spec.mjs` (1 PASS, реальный UI→HTTP→owned PG,
[сводка](evidence/f05-owned-summary.json), screenshots 1440/390/320/200%
в `evidence/f05-confirmed-with-draft-*.png`); E6 — 12 PASS в
`exec-fix02-preparation.spec.mjs`, `f05-f09-next-layout.spec.mjs`,
`questionnaire-draft-guards.spec.mjs` (Chromium, синтетический HTTP/компонент,
[скриншоты](evidence/)); E7 — `path29-participant.spec.mjs` (1 PASS:
confirmed N + draft N+1 → назначение → первый Case/Turn, owned PG,
controlled gateway, `P4K_FULL_PATH=0`;
[сводка](evidence/f05-f07-path29-summary.json));
E8 — `npm run lint:js`, `npm run build:web`, `git diff --check` (PASS).
E4 использует `TEST_DATABASE_URL` только
с `test/pytest` в имени; E5/E7 создают и удаляют собственные marker-owned БД.
E9 — `runtime.spec.mjs` (3 PASS: технический Cycle с двумя AS через
Turn→Finish→ASK→явный Next→Report, второй tab завершает сценарий один раз,
потерянный/непринятый Turn и owner boundary; owned PG и controlled gateway).
E10 — `path29-participant.spec.mjs` после добавления новой сессии (1 PASS:
confirmed #1 + draft #2, fresh admin login показывает действующую #1 и
редактируемый #2, затем назначение и первый Turn; owned PG).
E11 — новые `runtime.spec.mjs` (2 PASS по отдельности: commit `scenario_end`
и commit Next с потерей ответа, reload, завершение двух AS и Report без
повторной первой команды; owned PG). Безопасная [сводка](evidence/continuation-summary.json).
E12 — `P4K_F05_CONFIRM_LOST=1` + `questionnaire-it-inputs.spec.mjs` (1 PASS:
Confirm #2 сохранён при потерянном ответе, GET/reload показывает #2 действующей,
#1 остаётся в истории, в PG ровно две редакции и один Confirm POST).
E13 — `P4K_F06_STALE_ASSIGNMENT=1` + `path29-participant.spec.mjs`
при поздних 200/409/500 (3 PASS по отдельности): HTTP POST уже завершён сервером,
logout/login в том же browser, старый ответ не меняет новый статус; owned PG
показывает один профиль, один Cycle и один start.
E14 — E11 Next после CSS исправления (1 PASS): полный экран runtime в Chromium,
1440/390/320 px и 320 px с 200% текста, длинный статус, keyboard focus,
скрытое старое поле, без horizontal overflow; screenshots
`evidence/f09-runtime-*.png`. Первый прогон выявил позднее правило `width: 200px`,
следующий — нечитаемую форму при 200%; исправлено и повторено PASS.
E15 — `runtime.spec.mjs` F07 known 409 (1 PASS): настоящий Turn handler возвращает
`M7_BLOCKING_SYSTEM_WAIT` после `scenario_end` отдельным HTTP-клиентом, UI объясняет
ожидание предыдущего действия, отклонённый текст отсутствует в PostgreSQL;
явная проверка исходной команды разрешает ответ на ASK, Cycle дошёл до Report.
Первый E15 выявил общее сообщение, исправлено. Второй прогон показал, что
тестовый драйвер должен нажать «Проверить состояние» перед новым ответом;
исправлен тест, третий прогон PASS.
E16 — `P4K_F05_DRAFT_ONLY=1` + `questionnaire-it-inputs.spec.mjs` (1 PASS):
только `ready_for_confirmation` #1, после reload UI блокирует назначение,
в owned PG одна черновая редакция и ноль назначений; E4 отдельно проверяет
другую оценку, E3 — чужую организацию.
E17 — `P4K_F05_INCOMPLETE_LATE_SAVE=1` + `questionnaire-it-inputs.spec.mjs`
(1 PASS): неполный draft #2 сохранён в owned PG; ответ preview задержан до
logout/login, новый UI показывает confirmed #1 действующей, #2 отдельно,
назначений нет. E6 отдельно проверяет поздний GET при смене org/assessment.
E18 — `P4K_F06_A_B_A=1` + `path29-participant.spec.mjs` при поздних
200/409 (2 PASS): две синтетические организации в owned PG, суперадминистратор
выбирает A→B→A до ответа первого назначения; статус нового поколения не меняется,
в PG один профиль/Cycle/start. Первая фикстура попыталась добавить обычного
администратора в две организации и закономерно нарушила уникальность; вариант
переведён на штатный доступ суперадминистратора, повтор PASS.
E19 — `P4K_F06_CURRENT_ERROR=1` + `path29-participant.spec.mjs` (1 PASS,
повтор после усиления): в owned PG тест сначала фиксирует idempotency key
для уже назначенного первого участника, затем UI тем же ключом пытается
назначить второго. Реальный handler возвращает 409
`ASSIGNMENT_OPERATION_IDEMPOTENCY_CONFLICT`; текущая сессия показывает
понятную причину. Один исходный профиль/Cycle/start, назначение второму
не создано. Предыдущая версия E19 проверяла только контролируемый 409;
новый прогон подтвердил серверный отказ.
E20 — `runtime.spec.mjs` F08 stalled headers/body (2 PASS по отдельности):
после commit `scenario_end` удержаны сначала HTTP-заголовки, затем чтение тела;
в обоих случаях клиент завершил ожидание за пределом 30 секунд с неизвестным
исходом и отключённым вводом. После reload тот же Cycle дошёл через ASK и
явный Next до Report; terminal export owned PG: две закрытые AS,
`collection_status=calculated`, `pipeline.status=ready`, `report.status=ready`.
E21 — `runtime.spec.mjs` F09 stalled headers (1 PASS): сервер зафиксировал
явный Next, его HTTP-заголовки удержаны более клиентского предела 30 секунд;
UI показал проверку той же операции без нового POST. Reload открыл вторую AS;
terminal export owned PG: две закрытые AS, `collection_status=calculated`,
Report ready. Долгую `queued/running` этим прогоном не заявляем.
E22 — `runtime.spec.mjs` F07 fresh 403 (1 PASS): контролируемый HTTP 403 на
первый Turn показан рядом с ответом, в owned PG отклонённого Turn нет; после
явного readback дальнейший ответ разрешён, terminal export — две закрытые AS
и Report ready. Код 403 сформирован тестовым HTTP-перехватчиком.
E23 — `runtime.spec.mjs` F08 known refusal (1 PASS): контролируемый HTTP 409
на первый Finish показан как определённый отказ, в owned PG AS оставалась
`active`; после reload штатный Finish и остальной Cycle дошли до Report.
Первый отказ не выдан за неизвестный исход и не создал переход.
E24 — `runtime.spec.mjs` F07 stalled body (1 PASS после уточнения ожидания):
сервер зафиксировал первый Turn, чтение тела ответа удержано; UI рядом с
репликой показал неизвестный либо уже подтверждённый сохранённый исход,
автоматический exact readback мог разрешить его до 30 секунд. После reload
в owned PG ровно один Turn с этим текстом, терминальный Cycle дошёл до Report.
Первое ожидание только общего `#interview-error` было неверным: фоновой
readback успевал показать статус рядом с репликой; проверка перенесена туда.
E25 — `runtime.spec.mjs` F08 без ASK (1 PASS): изолированный gateway
выдаёт отсутствие необходимости уточнения после сохранённого Turn; первый
Finish ведёт через `NO_QUESTION` прямо к закрытию AS. До явного Next UI
остаётся между ситуациями с отключённым прежним полем. После Next в owned PG
вторая AS, terminal export — две закрытые AS и готовый Report. Ветвь ASK
отдельно проверена E9/E11.
E26 — `runtime.spec.mjs` F07 без реплики (1 PASS): контролируемый
синтетический исход M5 не активирует `mandatory_update` и `character_response`;
UI показывает один сохранённый Turn участника без придуманного ответа.
Ветка с обязательным обновлением Case проверена E7/E9; оба пути в owned PG
дошли до терминального Report.
E27 — `runtime.spec.mjs` F07 late poll (1 PASS после исправления): GET runtime
захватил снимок до Turn и вернулся после POST/readback. Первый прогон проявил
откат экрана к состоянию без ответа и остановку на ASK при серверных
`scenario_ended`/`ASK`; добавлены поколение команды при отправке и проверка
монотонности append-only Turn/event trace. Повтор: старая GET-проекция не
снимает сохранённую реплику, reload и терминальный Cycle с двумя AS/Report
PASS; в owned PG нет дубликата исходного Turn.
E28 — `runtime.spec.mjs` F09 two tabs (1 PASS): обе вкладки одного участника
видят `between_situations`; первый Next уже committed, его HTTP-ответ удержан,
вторая вкладка отправляет свой Next. Оба POST получили 201, после reload
вкладки сходятся на одной новой AS. Усиленный повтор: до выдачи первого
ответа участник ушёл на главный экран; поздний ответ не открыл интервью,
после явного возврата доступна та же новая AS. Терминальный экспорт owned PG содержит
ровно две AS и один Cycle; Report готов. E4/E6 отдельно покрывают
`failed/retry_allowed` и admission.
E29 — `runtime.spec.mjs` F07 late Turn receipt after AS advance (1 PASS):
первый POST зафиксирован сервером, его ответ удержан; вторая вкладка завершила
первую AS и явным Next открыла вторую. Первая вкладка уже показывала новую AS
до прихода старого ответа и после него сохранила её; исходный Turn отправлен
один раз. Терминальный экспорт owned PG: две закрытые AS и готовый Report.
Первый тестовый прогон был прерван при неучтённом подтверждении Finish во
второй вкладке; после обработки диалога повтор PASS.
E30 — `runtime.spec.mjs` F08 late Finish receipt after AS advance (1 PASS):
первый `scenario_end` сохранён, его ответ удержан; вторая вкладка прошла ASK,
закрыла первую AS и явным Next открыла вторую. Первая вкладка уже имела новый
AS ID и после позднего ответа сохранила его; отображаемое оставшееся время
не увеличилось, повторного `scenario_end` нет. После reload терминальный
экспорт owned PG подтвердил две закрытые AS и готовый Report. Первый прогон
не дошёл до проверяемого действия из-за таймаута подготовительного onboarding;
повтор PASS.
Повтор полного frontend-набора на текущем diff: 271 PASS. Первый прогон выявил
7 сбоев изолированных VM-harness после нового `productRuntimeMutationGeneration`;
обновлены три harness, адресный и полный повтор PASS. Backend-набор на текущем
diff: 1089 PASS, 551 deselected; `lint:js` и `git diff --check` PASS.
Первый E11 Next выявил неверное общее сообщение об ошибке сохранения ответа;
исправлено в `interview.js`, повтор PASS. Первый E10 ожидал preview в новой
сессии, хотя сохранённый черновик открывается в форме; проверка уточнена по
значению поля, повтор PASS. Все результаты относятся к синтетическим данным.

Первый E2 выявил отсутствующие `id`/`assignment_ref` у старой unit-фикстуры
confirmed; исправлено, повтор PASS. Новая проверка draft-only сначала ожидала
`data_missing`, фактический штатный статус — `draft_unconfirmed`; ожидание
исправлено и повторено PASS.

Проверка составного технического PATH29 с `P4K_COMPLETION_PROFILE=1` и
`P4K_FULL_PATH=0` не закрыла MERGE-AC01. Сначала преждевременное включение
QA orchestration сделало каталог недоступным до назначения; после переноса
включения за старт штатная component fixture дошла до первого Case, но
`verifyPreparation` законно остановилась на `GENERATION_MISSING` до Turn:
она не содержит сохранённого функционально сгенерированного AS. Экспериментальные
изменения теста отменены. Реальный provider и платные вызовы не запускались;
проверенные ранее отдельные owned browser/PG контуры остаются доказательством
только своих частей. Тестовые БД этих попыток удалены по marker.

E31 — `tests/integration/test_m10_product_path_db.py` на отдельной owned
`p4k_f05_pytest` (19 PASS, 1 warning, 68.43 с): функциональный Cycle и Next
через реальные HTTP handlers; один ID проходит queued→running→completed;
повтор того же POST возвращает этот ID, другой owner получает 404 на status
и 403 на Next, в PG нет второго выбранного Next. Прогоны выполнялись
последовательно: два одновременно запущенных процесса конфликтовали с
изоляционной проверкой тестового gateway, после остановки обоих один чистый
повтор дал 19 PASS. Это дефект процедуры запуска, не продукта.

E32 — `P4K_FULL_PATH=1 P4K_PROGRAM_SOURCE=published-pilot
P4K_CONTROLLED_PROVIDER=1 P4K_COMPLETION_PROFILE=1` и
`tests/browser/path29-participant.spec.mjs` (1 PASS, Chromium, ~1.1 мин):
один owned browser/HTTP/PG путь F05 confirmed #1 + draft #2 → назначение
по действующей #1 → подготовка и продуктовый admission функциональной AS →
первый Turn → Finish/ASK/закрытие → явный Next → новая AS. Тестовый provider
помечен `controlled_fixture` и возвращает синтетический кандидат на основе
опубликованного v1.2 источника с SHA-256
`09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b`;
продуктовые validators, сохранение и admission действуют штатно. Безопасная
[сводка](evidence/functional-owned-summary.json) содержит ID редакций/AS,
checksum receipts и подтверждённый marker cleanup. После проверенного первого
Next тест отдельно закрывает fixture для удаления БД: `pipeline.status=failed`
от незавершённой второй AS относится только к cleanup, не к проверяемому
переходу и не является доказательством Report.

E33 — тот же путь с `P4K_F09_LONG_NEXT=1` (1 PASS, Chromium, ~2.1 мин):
Next worker удержан в running за пределом клиентского ожидания; UI предлагает
«Проверить состояние», один Next POST и один operation ID. После logout
участника/login администратора worker завершил операцию, readback прежнего
owner нашёл новую AS, новый owner получил 404 на старый operation status,
старое интервью не появилось. Owned DB удалена по marker. Дополнительный
компонентный F06 stale response и отдельные F07/F08/F09 fault branches остаются
E9–E30, а E32/E33 закрепляют их совместимость в одном кандидате.

Воспроизведение E31: `TEST_DATABASE_URL=<owned-test-url> .venv/bin/pytest -q
tests/integration/test_m10_product_path_db.py` в единственном процессе.
Воспроизведение E32/E33: `STAND_ADMIN_URL=<isolated-admin-url>
P4K_FULL_PATH=1 P4K_PROGRAM_SOURCE=published-pilot P4K_CONTROLLED_PROVIDER=1
P4K_COMPLETION_PROFILE=1 BROWSER_PYTHON=.venv/bin/python
node_modules/.bin/playwright test tests/browser/path29-participant.spec.mjs`;
для E33 добавить `P4K_F09_LONG_NEXT=1`. Адреса должны указывать только на
выделенный owned test кластер; browser fixtures сами проверяют marker и удаляют
свои БД. Финальная [проверка очистки](evidence/final-cleanup.json): marker
`p4k_f05_pytest` совпал, БД удалена, других owned test БД нет, кластер остановлен.
`node --check` трёх изменённых `.mjs`, `npm run lint:js`, `git diff --check`
и `py_compile` четырёх изменённых Python файлов с кэшем в `/private/tmp` — PASS.
Первый `py_compile` системным Python не смог создать кэш в защищённом
`~/Library/Caches`; повтор с `PYTHONPYCACHEPREFIX` прошёл, исходники не менялись.

E34 — полный локальный pre-PR набор после `9c946718` и адресного исправления
тестового VM-адаптера: первый frontend-прогон дал 267 PASS / 4 FAIL, потому что
адаптер не реализовал новый `page.on('dialog')`; добавлен no-op listener для
VM fixture, адресный повтор 4 PASS и весь frontend-набор 271 PASS. Остальные
проверки: `npm run test:backend` 1089 PASS / 551 deselected;
`npm run test:backend:http` 153 PASS / 13 deselected; `npm run lint:js` PASS;
`npm run build:web` PASS без изменения `web/dist`; `git diff --check` PASS.
Первый полный `TEST_DATABASE_URL=<owned-test-url> npm run
test:backend:integration` на PostgreSQL 15: 353 PASS, 7 FAIL, 25 setup ERROR,
9 SKIP. Причина 31 неуспеха на первом запуске — test stand требует
`agent4k_pytest` либо `task11_pytest` и явного DB user, а owned-stand тесты
также требуют `STAND_ADMIN_URL`; первоначальный URL этим условиям не отвечал.
Ещё один FAIL R03 сохраняется при корректном URL.
Адресный `--lf` с allowlisted именем, явным DB user и maintenance URL:
31 PASS, 1 FAIL. Оставшийся `test_r03_auth_full_flow_db.py` дважды получил
значение вне диапазона 1–7. Прежняя интерпретация вывода pytest как
`Retry-After: 0` была неверной: точный HTTP readback на неизменённом
`origin/main` показал 10807 секунд при cooldown 7 в зоне Europe/Moscow.
Одиночный тест на `origin/main@c06e94d5` в отдельном чистом worktree дал
идентичный FAIL. Авторизация R03 и этот тест не менялись кандидатом; gate
исходного F05–F09 SHA в этом прогоне был FAIL и не выдаётся за PASS. Безопасная
[сводка](evidence/full-local-verification.json) и итоговая
[очистка](evidence/final-cleanup.json) сохранены; обе marker-owned БД удалены,
выделенный кластер остановлен, временный baseline worktree удалён.

| ID | Статус | Проверенный синтетический путь / остаток |
| --- | --- | --- |
| F05-AC01 | PASS | E5/E7/E10: confirmed #1 + draft #2, GET/reload/новая сессия; UI показывает #1 действующей и #2 в редактируемой форме. Назначение и первый Turn на #1, в PG две редакции и один Cycle. |
| F05-AC02 | PASS | E16: только draft #1, GET/reload, UI показывает «Назначение пока недоступно», в PG одна черновая редакция и ноль назначений. E4: другая оценка → `data_missing`; E3: чужая организация → 403, чужая редакция не используется. |
| F05-AC03 | PASS | E4: confirm идемпотентен; E12: после #1 создаётся #2, UI отправляет один Confirm, ответ теряется после commit; GET/reload показывает #2 действующей, #1 сохраняется в истории, в PG ровно две редакции. |
| F05-AC04 | PASS | E17: неполный draft #2 и задержанный ответ сохранения после logout/login, confirmed #1 остаётся действующей, в PG один draft и ноль назначений. E6: поздний GET не переносит черновик между org/assessment/login; E4: readiness N не меняется. |
| F06-AC01 | PASS | E1: смена owner/epoch; E13: поздние 200/409/500 после logout/login не меняют сообщение новой сессии. На owned PG повтор назначения имеет один серверный эффект, один профиль/Cycle/start. |
| F06-AC02 | PASS | E18: A→B→A на двух реальных синтетических org в одном UI, поздние 200/409 отклонены поколением экрана; в owned PG один серверный эффект назначения, один профиль/Cycle/start. E1: тот же guard при открытии экрана. |
| F06-AC03 | PASS | E7: обычный успех и replay назначения → `already_assigned`, точный readback без второго Cycle; E19: реальный серверный 409 при конфликте сохранённого operation ID в той же сессии, понятный feedback, один UI POST и без назначения второму участнику. В PG по-прежнему один профиль/Cycle/start. |
| F07-AC01 | PASS | E7/E9: обычный Turn, HTTP 200, один ответ участника и предусмотренный Case `mandatory_update`; E26: отдельная разрешённая ветвь без реплики, ровно один сохранённый Turn и ноль `mandatory_update`/`character_response` в owned PG. Оба маршрута достигли Report без фиктивного ответа. |
| F07-AC02 | PASS | E9: сбой до/после commit и тот же Turn через readback; E15: реальный 409 после `scenario_end`, предметная причина, отклонённого Turn нет в PG. E22: контролируемый 403, понятный отказ, нет Turn, явный readback. E24: зависшее тело после commit, статус рядом с репликой, после reload один Turn в PG. |
| F07-AC03 | PASS | E1 и P3: pending/context/repeat, включая смену Cycle; E4: PG replay; E9: потеря ответа до/после commit, тот же Turn, reload/две вкладки и граница owner на owned PG. E29: поздний ответ Turn после перехода другой вкладки к следующей AS не изменил её и не создал второй Turn. |
| F07-AC04 | PASS | E1: pending закрывает ввод до exact readback, поздний ответ проверяет scope. E27: реальный browser/owned PG poll со старой проекцией возвращён после Turn/readback; UI сохранил подтверждённый ответ и дошёл до ASK/Report. Первый FAIL воспроизвёл откат, после защиты поколения и append-only trace повтор PASS. |
| F08-AC01 | PASS | E9/E11: owned UI→HTTP→PG Finish→ASK→закрытие AS→between, новая AS только после Next. E25: отдельный допустимый маршрут `NO_QUESTION` закрывает AS без ASK, прежний ввод недоступен, после явного Next открыта вторая AS; обе ветви дошли до Report без дополнительного Cycle. |
| F08-AC02 | PASS | E11: потерянный ответ после commit, неизвестный исход, блокировка ввода, reload, один `scenario_end` в PG. E20: отдельные зависания заголовков и тела после commit, ограниченное ожидание и terminal export. E23: контролируемый 409 показан как определённый отказ, AS остаётся active, затем штатное завершение и Report. |
| F08-AC03 | PASS | E1: owner/AS scope; E4: закрытие AS и запрет нового Turn; E9: второй tab не создаёт второй `scenario_end`. E30: поздний Finish после перехода второй вкладки к новой AS не перерисовал старую ситуацию и не перезапустил таймер; один `scenario_end` и терминальный Report на owned PG. |
| F09-AC01 | PASS | E1/E11/E21: timeout заголовков, неизвестный исход и readback той же команды. E31: реальные HTTP/PG queued→running→completed одного ID. E33: browser на owned PG удержал worker в running за клиентским пределом, увидел статус и «Проверить состояние», сохранил один Next POST без ложного failed. |
| F09-AC02 | PASS | E6: `failed/retry_allowed` true/false и reload; E4: owned PG retry/admission; E9/E11: ready и явный Next без дубликата при потере ответа; E28: две вкладки отправили Next, обе сошлись на одной второй AS после reload, терминальный экспорт — две AS и один Cycle. |
| F09-AC03 | PASS | E1: scope owner/Cycle/AS и очистка старого ID; E28: поздний ответ после ухода на главный экран не открыл интервью. E31: другой owner получает 404/403 на operation/Next. E33: worker завершил Next после смены owner в браузере; старая AS не появилась в новой сессии, прежний owner readback нашёл одну новую AS. |
| F09-AC04 | PASS | E6/E14: реальный полный runtime UI на owned PG и отдельная CSS геометрия, 1440/390/320/200%, длинный статус, keyboard focus, широкая кнопка и отсутствие горизонтального overflow. Между AS старое поле скрыто; степень готовности и ETA не выдумываются. |
| MERGE-AC01 | PASS | E32/E33: один candidate и один owned browser/HTTP/PG маршрут F05 confirmed #1 + draft #2 → назначение → функциональная AS через продуктовый admission → Turn → Finish/ASK → явный Next → одна новая AS. E13/E18/E19: поздний/отклонённый F06; E9/E11/E20/E21/E24/E28–E30: потери, зависшее тело, reload, поздние ответы и отсутствие дубликатов в допустимом техническом runtime; E33: длинный Next и смена owner. Контролируемый provider не доказывает реальный LLM, terminal cleanup не доказывает Report этого маршрута. |

E35 — временный detached checkout `b6996a54260037c919340024a443ca00ef16a30c`
содержит F05–F09 `5091e13e` и отдельно исправленный R03 `4e6bffa4`.
`STAND_ADMIN_URL=<owned-maintenance-url>
TEST_DATABASE_URL=<owned-agent4k_pytest-url> npm run test:backend:integration`:
393 PASS, 2 SKIP явного real-provider LLM, 1246 deselected, 0 FAIL,
1 warning за 730.47 с. Оба R03 timezone варианта PASS. Перед удалением
`agent4k_pytest` проверен точный owner marker, после удаления owned test БД
не осталось, выделенный PostgreSQL остановлен. [Сводка](evidence/combined-r03-gate.json).

Итого по AC: 19 PASS из 19 локально. Полный integration-набор на исходной
ветке F05–F09 имеет базовый R03 FAIL; на временном сочетании с отдельным
R03 fix локальный gate зелёный. Это не CI и не изменение исходного кандидата.
Полный PATH/F22 и качество реального LLM не заявлены. F03/F04 — отдельные
зависимости. CI `frontend`, `pytest`, `full-verification` на точном head и
human review до слияния не выполнены; до TEST и визуальной приёмки владельца
кандидат не дошёл.

E36 — после разрешённого squash merge R03 PR #213 `origin/main` стал
`e7cd26dc35d919976c202904dd40ca09d3bad790` (приложение `2.0.101`).
`deploy-test` job [#973](https://github.com/VadikB/4K_MBTI/actions/runs/43275471959/job/131382576960)
и шаг `Deploy main to test` — PASS. Draft PR #214 на `6b23f69e` до
обновления базы: `frontend` и `pytest` PASS, полный workflow SKIP для draft.
После `git fetch origin main` исходный код объединился без конфликтов;
конфликты только в `web/dist` устранены `npm run build:web` с штатной очисткой.
На объединённом дереве `node --test tests/frontend/*.test.mjs`: 271 PASS;
`npm run lint:js`: PASS; `npm run test:backend`: 1089 PASS / 552 deselected;
`npm run test:backend:http`: 153 PASS / 13 deselected; build и staged
`git diff --check`: PASS. Полный local integration точного merge SHA не
повторялся: E35 уже проверил тот же F05–F09 product code с R03 fix, а принятая
база дополнительно содержит номер версии и release-сборку. Полный CI точного
SHA остаётся обязательным после согласования версии и Ready.

E37 — draft PR #214 обновлён до `a5fe39ee`: [быстрый CI
#974](https://github.com/VadikB/4K_MBTI/actions/runs/43276619804) —
`frontend` PASS, `pytest` PASS, `deploy-test` SKIP для PR;
`full-verification` SKIP для draft. Владелец утвердил `2.1.0` (`minor`)
и Ready. На актуальной `origin/main@e7cd26dc` команда
`npm run ready:prepare -- --release-type minor --candidate 2.1.0` — PASS:
согласованные файлы версии, `npm run build:web` и release gate.
`git diff --check` — PASS. Полный CI точного нового SHA требуется после
commit, push и перевода PR в Ready.
