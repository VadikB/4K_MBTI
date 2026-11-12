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

Первый E2 выявил отсутствующие `id`/`assignment_ref` у старой unit-фикстуры
confirmed; исправлено, повтор PASS. Новая проверка draft-only сначала ожидала
`data_missing`, фактический штатный статус — `draft_unconfirmed`; ожидание
исправлено и повторено PASS.

| ID | Статус | Проверенный синтетический путь / остаток |
| --- | --- | --- |
| F05-AC01 | PARTIAL | E5/E7: confirmed N + draft N+1, GET/reload, UI показывает N действующей; назначение и первый Turn используют её, в PG две редакции и один Cycle. Новый login администратора на той же БД не проверен. |
| F05-AC02 | PARTIAL | E4: только draft → `draft_unconfirmed`, чужой assessment → `data_missing`; E3: чужая org → 403. Общий browser/PG сценарий не выполнен. |
| F05-AC03 | PARTIAL | E4: confirm idempotent и один published context; E5: confirm/reload. Потерянный ответ при N→N+1 в browser/PG не проверен. |
| F05-AC04 | PARTIAL | E4: неполный draft сохраняет readiness N; E6: поздний GET не переносит черновик между org/assessment/login. Поздний save на PG не проверен. |
| F06-AC01 | PARTIAL | E1: поздний 200/409 после смены user/epoch не меняют UI. 500 и logout/login через браузер/HTTP не проверены. |
| F06-AC02 | PARTIAL | E1: A→B→A с новым поколением отбрасывает 200/409; открытие экрана также меняет поколение. Нет browser/PG назначения. |
| F06-AC03 | PARTIAL | E1: текущий 200/409 сохраняет feedback; E7: replay назначения → `already_assigned`, без второго Cycle. Нет общего browser receipt/readback. |
| F07-AC01 | PARTIAL | E7: обычный Turn из UI, HTTP 200; E4: PG M5 runtime/replay. Обе ветви с/без реплики сценария в browser/PG не проверены. |
| F07-AC02 | PARTIAL | E1: первый 409 показывает отказ и не посылает второй POST; E4: answer-status/replay. 403, потеря до/после commit и зависшее тело на browser/PG не проверены. |
| F07-AC03 | PARTIAL | E1 и P3: pending/context/repeat; E4: PG replay. Две вкладки и reload во время Turn на PG не проверены. |
| F07-AC04 | PARTIAL | E1: pending закрывает ввод до exact readback, поздний ответ проверяет scope. Browser poll race с PG не проверен. |
| F08-AC01 | PARTIAL | E1: потерянный `scenario_end` сохраняет команду и блокирует ввод; E4: PG clarification/finish. Единого browser Finish→ASK/between нет. |
| F08-AC02 | PARTIAL | E1: lost response/reload без повторного Finish; deadline POST/GET и 45 s уточнение. Header/body stall, отказ и PG readback не проверены вместе. |
| F08-AC03 | PARTIAL | E1: owner/AS scope; E4: закрытие AS и запрет нового Turn. Поздний ответ и таймер в настоящем UI не проверены. |
| F09-AC01 | PARTIAL | E1: потерянный Next проверяет тот же ID без нового POST; локальный лимит не делает failed. Долгий queued/running на PG/browser не проверен. |
| F09-AC02 | PARTIAL | E6: failed/retry_allowed true/false, reload; E4: PG retry/admission. Ready и две вкладки на одном UI→HTTP→PG пути не проверены. |
| F09-AC03 | PARTIAL | E1: scope owner/Cycle/AS, новая AS очищает старый Next ID. Поздний worker/poll при смене контекста в браузере не проверен. |
| F09-AC04 | PARTIAL | E6: Chromium+CSS продукта, длинный статус, 1440/390/320, 200%, keyboard focus, старое поле disabled, без overflow. Полный runtime экран не проверен. |
| MERGE-AC01 | PARTIAL | Один diff: E7 реальный owned UI→HTTP→PG F05→assignment→первый Turn; E1 F06/неопределённые команды, E4 Finish/Next PG. Нет продолжения того же browser runtime через Finish→Next и fault branches. |

Полный PATH/F22 и качество реального LLM не заявлены. F03/F04 — отдельные
зависимости. До PR нужны оставшиеся AC, CI `frontend`, `pytest`,
`full-verification` на точном head и human review; до TEST и визуальной
приёмки владельца кандидат не дошёл.
