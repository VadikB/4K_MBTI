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
вкладки сходятся на одной новой AS. Терминальный экспорт owned PG содержит
ровно две AS и один Cycle; Report готов. E4/E6 отдельно покрывают
`failed/retry_allowed` и admission.
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
| F07-AC03 | PARTIAL | E1 и P3: pending/context/repeat; E4: PG replay; E9: потеря ответа до/после commit, тот же Turn, reload/две вкладки и граница owner на owned PG. Смена Cycle/AS во время позднего ответа в одном browser прогоне не проверена. |
| F07-AC04 | PASS | E1: pending закрывает ввод до exact readback, поздний ответ проверяет scope. E27: реальный browser/owned PG poll со старой проекцией возвращён после Turn/readback; UI сохранил подтверждённый ответ и дошёл до ASK/Report. Первый FAIL воспроизвёл откат, после защиты поколения и append-only trace повтор PASS. |
| F08-AC01 | PASS | E9/E11: owned UI→HTTP→PG Finish→ASK→закрытие AS→between, новая AS только после Next. E25: отдельный допустимый маршрут `NO_QUESTION` закрывает AS без ASK, прежний ввод недоступен, после явного Next открыта вторая AS; обе ветви дошли до Report без дополнительного Cycle. |
| F08-AC02 | PASS | E11: потерянный ответ после commit, неизвестный исход, блокировка ввода, reload, один `scenario_end` в PG. E20: отдельные зависания заголовков и тела после commit, ограниченное ожидание и terminal export. E23: контролируемый 409 показан как определённый отказ, AS остаётся active, затем штатное завершение и Report. |
| F08-AC03 | PARTIAL | E1: owner/AS scope; E4: закрытие AS и запрет нового Turn; E9: второй tab не создаёт второй `scenario_end`. Поздний ответ и таймер в настоящем UI не проверены. |
| F09-AC01 | PARTIAL | E1: клиентский предел и тот же ID без нового POST; E11: потерянный ответ после commit показывает проверку той же операции, reload открывает новую AS, один первый Next POST. E21: зависшие заголовки после commit ограничены 30 секундами, одна команда и terminal export. Долгий queued/running на PG/browser не проверен. |
| F09-AC02 | PASS | E6: `failed/retry_allowed` true/false и reload; E4: owned PG retry/admission; E9/E11: ready и явный Next без дубликата при потере ответа; E28: две вкладки отправили Next, обе сошлись на одной второй AS после reload, терминальный экспорт — две AS и один Cycle. |
| F09-AC03 | PARTIAL | E1: scope owner/Cycle/AS, новая AS очищает старый Next ID. Поздний worker/poll при смене контекста в браузере не проверен. |
| F09-AC04 | PASS | E6/E14: реальный полный runtime UI на owned PG и отдельная CSS геометрия, 1440/390/320/200%, длинный статус, keyboard focus, широкая кнопка и отсутствие горизонтального overflow. Между AS старое поле скрыто; степень готовности и ETA не выдумываются. |
| MERGE-AC01 | PARTIAL | Один diff: E10/E13 owned F05→assignment→первый Turn с поздними ответами F06; E9/E11 отдельный допустимый технический runtime через Turn→Finish→ASK→явный Next→Report и потерю ответов Finish/Next. Объединённый browser/PG прогон со всеми fault branches не выполнен. |

Полный PATH/F22 и качество реального LLM не заявлены. F03/F04 — отдельные
зависимости. До PR нужны оставшиеся AC, CI `frontend`, `pytest`,
`full-verification` на точном head и human review; до TEST и визуальной
приёмки владельца кандидат не дошёл.
