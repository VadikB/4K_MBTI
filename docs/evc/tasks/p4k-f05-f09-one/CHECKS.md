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
| F05-AC02 | PARTIAL | E4: только draft → `draft_unconfirmed`, чужой assessment → `data_missing`; E3: чужая org → 403. Общий browser/PG сценарий не выполнен. |
| F05-AC03 | PASS | E4: confirm идемпотентен; E12: после #1 создаётся #2, UI отправляет один Confirm, ответ теряется после commit; GET/reload показывает #2 действующей, #1 сохраняется в истории, в PG ровно две редакции. |
| F05-AC04 | PARTIAL | E4: неполный draft сохраняет readiness N; E6: поздний GET не переносит черновик между org/assessment/login. Поздний save на PG не проверен. |
| F06-AC01 | PASS | E1: смена owner/epoch; E13: поздние 200/409/500 после logout/login не меняют сообщение новой сессии. На owned PG повтор назначения имеет один серверный эффект, один профиль/Cycle/start. |
| F06-AC02 | PARTIAL | E1: A→B→A с новым поколением отбрасывает 200/409; открытие экрана также меняет поколение. Нет browser/PG назначения. |
| F06-AC03 | PARTIAL | E1: текущий 200/409 сохраняет feedback; E7: replay назначения → `already_assigned`, без второго Cycle. Нет общего browser receipt/readback. |
| F07-AC01 | PARTIAL | E7: обычный Turn из UI, HTTP 200; E4: PG M5 runtime/replay. Обе ветви с/без реплики сценария в browser/PG не проверены. |
| F07-AC02 | PARTIAL | E1: первый 409 показывает отказ без второго POST; E9: потеря до/после commit, один Turn; E15: реальный 409 после `scenario_end`, предметное сообщение, нет отклонённого Turn в PG, явный readback. 403 и зависшее тело в browser/PG не проверены. |
| F07-AC03 | PARTIAL | E1 и P3: pending/context/repeat; E4: PG replay; E9: потеря ответа до/после commit, тот же Turn, reload/две вкладки и граница owner на owned PG. Смена Cycle/AS во время позднего ответа в одном browser прогоне не проверена. |
| F07-AC04 | PARTIAL | E1: pending закрывает ввод до exact readback, поздний ответ проверяет scope. Browser poll race с PG не проверен. |
| F08-AC01 | PARTIAL | E9/E11: owned UI→HTTP→PG Finish→ASK→закрытие AS→between; новая AS после явного Next, две закрытые AS и отчёт. Прямая closure без ASK в этом browser контуре не проверена. |
| F08-AC02 | PARTIAL | E1: deadline POST/GET и 45 s уточнение; E11: потерянный ответ после commit, UI показывает неизвестный исход и блокирует ввод, reload восстанавливает состояние, один `scenario_end` в PG. Header/body stall и известный отказ в одном browser/PG прогоне не проверены. |
| F08-AC03 | PARTIAL | E1: owner/AS scope; E4: закрытие AS и запрет нового Turn; E9: второй tab не создаёт второй `scenario_end`. Поздний ответ и таймер в настоящем UI не проверены. |
| F09-AC01 | PARTIAL | E1: клиентский предел и тот же ID без нового POST; E11: потерянный ответ после commit показывает проверку той же операции, reload открывает новую AS, один первый Next POST. Долгий queued/running на PG/browser не проверен. |
| F09-AC02 | PARTIAL | E6: failed/retry_allowed true/false, reload; E4: PG retry/admission; E9/E11: ready и явный Next открывают следующую AS, две AS и один Cycle, без дубликата при потере ответа. Две вкладки для Next на PG не проверены. |
| F09-AC03 | PARTIAL | E1: scope owner/Cycle/AS, новая AS очищает старый Next ID. Поздний worker/poll при смене контекста в браузере не проверен. |
| F09-AC04 | PASS | E6/E14: реальный полный runtime UI на owned PG и отдельная CSS геометрия, 1440/390/320/200%, длинный статус, keyboard focus, широкая кнопка и отсутствие горизонтального overflow. Между AS старое поле скрыто; степень готовности и ETA не выдумываются. |
| MERGE-AC01 | PARTIAL | Один diff: E10/E13 owned F05→assignment→первый Turn с поздними ответами F06; E9/E11 отдельный допустимый технический runtime через Turn→Finish→ASK→явный Next→Report и потерю ответов Finish/Next. Объединённый browser/PG прогон со всеми fault branches не выполнен. |

Полный PATH/F22 и качество реального LLM не заявлены. F03/F04 — отдельные
зависимости. До PR нужны оставшиеся AC, CI `frontend`, `pytest`,
`full-verification` на точном head и human review; до TEST и визуальной
приёмки владельца кандидат не дошёл.
