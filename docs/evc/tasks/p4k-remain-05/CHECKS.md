# CHECKS REMAIN_05 v1.6

RUN_ID `remain05-controlled-20261114`; base `a1cdfedfb8b71d150b078eb0380ea013f0b08965`. Точный tested code SHA фиксируется в STATE после commit; все результаты относятся к одним исходникам кандидата. Первичные квитанции — `receipts/`, без secrets/PII. Повторно использованы существующие тесты, исполненные заново; исторические 91unit/6queue не объявлены свежим PASS.

## Команды и результаты

| Команда | Фактический результат |
| --- | --- |
| `node --test tests/frontend/product-cycle-start.test.mjs tests/frontend/http-deadline.test.mjs tests/frontend/remain05-errors.test.mjs` | Первичный адресный run 31 PASS; последующие регрессии известного refusal/opaque проверены полным frontend |
| `node --test tests/frontend/*.test.mjs` | 303 PASS, exit0; `receipts/frontend.txt.gz` |
| `npm run lint:js` | PASS, exit0; `receipts/lint.txt.gz` |
| `npm run build:web` | PASS, exit0; `receipts/build.txt.gz`, dist включён |
| `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 .venv/bin/python -m pytest -q tests/unit/test_m5_functional_generation_service.py tests/unit/test_functional_personalization_matrix.py tests/unit/test_product_cycle_preparation_fencing.py tests/unit/test_product_cycle_preparation_projection.py` | 65 PASS, exit0; `receipts/protocol.txt.gz` |
| PG/HTTP exact selection ниже | 16 PASS, exit0, 21 deselected; `receipts/pg-http.txt.gz` |
| `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 TEST_DATABASE_URL=<owned localhost:55445/agent4k_pytest> .venv/bin/python -m pytest -q --run-integration tests/integration/test_remain05_first_preparation_db.py` | 7 PASS, exit0; `receipts/functional-pg.txt.gz` |
| `npx playwright test tests/browser/remain05-first-start.spec.mjs tests/browser/exec-fix02-preparation.spec.mjs tests/browser/auth-r03.spec.mjs --grep 'REMAIN05\|first preparation\|committed first start\|reload resolves unknown first start\|reload reads a preparation' --workers=1 --retries=0 --timeout=90000` | 8 PASS, exit0 за12.9с; `receipts/browser-regression.txt.gz`; новые3 отдельно также PASS |
| `git diff --check` | PASS, exit0 |

PG16 command: тот же `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 TEST_DATABASE_URL=<owned localhost:55445/agent4k_pytest> .venv/bin/python -m pytest -q --run-integration` с файлами `tests/integration/test_pilot_start_admission_db.py tests/integration/test_path_start_assignment_lineage_db.py tests/integration/test_m10_product_path_db.py` и точным `-k`:

```text
reassignment_http_start_presents_new_as_once_with_zero_answers or exact_limited_plan_reaches_explicit_start_same_as_and_zero_answers or two_concurrent_explicit_starts_present_once_without_resetting_time or real_sql_revocation_scope_and_publication_fail_closed_before_start or http_start_uses_same_sql_decision_and_does_not_expose_review_material or http_lost_start_receipt_is_recovered_by_read_only_runtime or reassignment_supersedes_stale_queued_preparation_without_new_index or legacy_completed_operation_keeps_exact_cycle_readback_until_reassignment or test_path_start_assignment_lineage or product_cycle_preparation_operation_returns_only_committed_admitted_cycle or http_preparation_retry_requires_server_classified_technical_failure or product_cycle_preparation_reclaim_fences_late_worker
```

## Матрица AC и прослеживаемость

| AC | Статус и проверяемый факт | Первичный результат / границы |
| --- | --- | --- |
| F04-AC01 | PASS TECH. Actual advance handler: answer PUT, consent POST, progress PUT × TypeError/AbortError/deadline/opaque409; текст/шаг остаются. Actual GET/PUT browser smoke. Safe renderer сохраняет известные W02/M4/admission/cancellation причины, код отдельно. | frontend303 + browser8; safe-error-answer.png. Первичный raw Failed to fetch удалён из отображения; подтверждение сохранения на сервере не выдумывается. |
| F04-AC02 | PASS TECH. Abort/deadline/empty/invalid/incomplete/foreign201/body-abort → same-cycle readback; pending записан до POST. Stall headers/body ограничен actual default transport. Reload не меняет key; один persisted старт/AS/бюджет. | product-cycle-start tests + invalid201 browser + actual HTTP/PG lost receipt, concurrent starts. |
| F04-AC03 | PASS TECH. Отмена/admission409 остаются отказами, readback AS не открывается; foreign/missing runtime/GET503 остаются unknown. Точный assignment/owner проверяет сервер. | frontend safe reasons/refusal/foreign; SQL revocation/scope/publication, HTTP foreign readback; lineage5. |
| F04-AC04 | PASS TECH. Явный normal201→runtime→reload, та же первая AS. Actual SQL first start/readback сохраняет AS, время и0assessee turns. | browser normal-start + pilot HTTP/PG. Browser использует синтетические HTTP-проекции, SQL/HTTP — настоящую owned PostgreSQL. Это сочетание границ, не единая живая auth→организация→AS сессия и не новый paid PATH. |
| F27-AC01 | PASS TECH. v1 exact envelope совместим; v2 missing/foreign candidate/check batch, invalid JSON, missing/incomplete protected review, FAIL/NOT_RUN закрывают admission. Actual controlled tester/challenger→queue сохраняет accepted trace/checksum/ref/AS; FAIL/INCOMPLETE сохраняют диагностику, AS/time/Turns0. | protocol65 + functional PG7 + PG16. Echo checksum не считается содержательной экспертизой. |
| F27-AC02 | PASS TECH. Durable queued/running/completed/failed, lost prepare→reload→GET той же operation; failure_result и checks не теряются при GET. Late worker fenced, assignment superseded, foreign no-read/no-write. | functional PG crash before/after provider/after attach/closed; PG16 fencing/scope; browser lost prepare + failure reload. UI unknown — отсутствие подтверждения, не выдуманный server status. |
| F27-AC03 | PASS TECH. Сначала чтение; same key old operation, server-only retry_allowed, new UUID не обходит admission refusal, два клиента получают ту же active operation; unknown/old failed fail-closed. | PG HTTP retry matrix, protocol projection; browser first preparation retry=true/false + lost response. Start и Next автоматически не повторяются. |

M1.4–5 / M4.4/6 / M5 AS admission / Change01 И-2/3 → C23/24/34 fixed profile/candidate/required IDs → неизменённые `m5_functional_generation_service`, `product_cycle_preparation_queue`, `m10_product_flow.start_prepared`, `assessment_start_readiness` → protocol/functional PG/pilot HTTP. M1.6/Change01 И-6 / M7.5 first session → один явный start/сохранённое время → изменённый frontend `product-cycle-start`, errors и onboarding handlers → actual deadline/handler/browser + SQL readback. M6/M8 не менялись, GC не применим.

## Сохранённые неуспехи и ограничения

- Sandbox localhost browser `listen EPERM` и initdb shared memory EPERM: NOT_RUN_ENV; разрешённый запуск выполнен. Это не product FAIL.
- Первый PG run:1 PASS/4 FAIL/11 setup ERROR, SQL_ASCII вернул bytes вместо str; `receipts/pg-http-initial-encoding-fail.txt.gz`. После штатного пересоздания только owned test DB template0/UTF8 тот же набор16 PASS; продукт не исправлялся ради fixture.
- Первый browser:1 PASS/1 FAIL после90с, пропущен consent_text в synthetic fixture, guard disabled корректен. `receipts/browser05-initial-fixture-fail.txt.gz`; после дополнения fixture новые3 и итоговые8 PASS. Лимит не повышен, full retries0.
- Полный backend/HTTP/integration и общий browser suite NOT_RUN: продуктовый Python/API/схема не менялись, matrix JS minimum выполнен; F27 адресные реальные PG/HTTP и protocol исполнены. Изменён только reuse test harness с default false; полный дальнейший сценарий до второй AS/Report не запускался из-за STOP05.
- CI, human review, TEST deploy/визуальная приёмка, physical device, real LLM/mail — NOT_RUN. Никакого нового release/CURRENT/methodology PASS. Исторические fd…/64344f28/PREP-DIAG остаются UNKNOWN.
- Недоступность sessionStorage остаётся существующим ограничением восстановления после reload; серверные guards/идемпотентность сохраняются. Нет утверждения о сохранении текста/результата без server подтверждения.

Визуально просмотрен safe-error-answer.png: ответ/кнопка/причина видимы, текст не теряется. Новая первая AS — same-first-as.png. Cleanup и точные SHA — STATE.


## Итог exact-code и review

На code SHA `d1326a3e7ee4cee8a1741d1580f6f83b5ce8caef` повторены под проверенным bounded wrapper: protocol65 PASS/3.36с; PG23 PASS/49.87с; frontend299 PASS и browser8 PASS. Receipts exact-protocol/exact-pg, все child_exited=true. После code review изменились только product-cycle-start.js, его frontend tests и пересобранный dist: readback refusal cause сохраняется при unknown, пустой/scalar/array participant_payload не считается подтверждённой AS. Итоговые frontend303, browser8, lint/build PASS; серверные65/23 reused с d1326a3e, byte-identical `Api/` и `tests/integration/` подтверждены `git diff --name-only d1326a3e -- Api tests/integration` (пусто). Новый код не меняет gateway/queue/admission/frozen refs.

Первый browser fixture90с превысил профиль no-progress60с, внешний ограничитель тогда отсутствовал: это отдельный harness-limit FAIL, не PASS профиля. Перед последним run wrapper в receipts/bounded-runner.py проверен positive/deadline/no-progress одноошибочными controls (runner-controls.json). Финальные тесты выполнялись с hard180с/no-progress60с/log10MiB и адресным TERM/grace15/KILL собственного PGID; все завершены раньше лимитов, без автоматических full retries. Никакого постоянно работающего monitor/service в продукт не добавлено.

Cleanup: test schemas0/connections0; dropdb exit0, pg_ctl fast stop exit0, status exit3/no server running; postmaster.pid отсутствует, owned cluster directory удалён. Primary cleanup.json; финальная проверка портов/процессов и symlinks — STATE.


## Кандидат архитектора2.1.5

14.11.2026 fresh origin/main=a1cdfedf, без новых коммитов/конфликтов. `npm run ready:prepare -- --candidate 2.1.5` exit0: version sync/build/release gate PASS. `npm run lint:js`, `python3.12 scripts/check_release_version.py --base-ref origin/main`, `git diff --check` PASS. После смены release/assets frontend303 PASS/3.01с; browser8 PASS/13.0с, bounded processes child_exited=true (PGID96270/96346). Primary receipts architect-ready/architect-frontend/architect-browser. Product handlers, Api и tests/integration byte-identical369ad32f: прежние protocol65/PG23 сохраняют применимость; новая БД/LLM/mail не запускались. Смена версии не меняет frozen snapshots/definitions. Remote CI ещё NOT_RUN до создания PR; GitHub CLI требует авторизацию, CUA Yandex не получил допуска.


## Сопровождение первого CI219

Head5bf7aca5: frontend/pytest и все5 browser lanes PASS; integration1FAIL/410PASS/2SKIP за500.09с, full-verification FAIL. Primary CI link и summary — receipts/ci219-snapshot.json. Единственный FAIL test_http_resume_reports_and_persists_first_deadline[None-60-None] получил409 M7_TIME_LIMIT_REACHED вместо200. Product Api и исходный test byte-identical basea1cdfedf, REMAIN05 frontend при этой проверке не исполняется.

Детерминированный before: старая positive fixture оставляет7200-(3599.8+3600.1)=0.1с; controlled .2с delay после resume воспроизводит тот же409 (1FAIL/3.36с), `receipts/ci-positive-before.txt.gz`. Test-only after: budget_offset=None оставляет60.1с, задержка.2с остаётся регрессией; exact expired fractional cases и guard не меняются. `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 TEST_DATABASE_URL=<owned agent4k_pytest:55445> .venv/bin/python -m pytest -q --run-integration tests/integration/test_exec_fix05_first_deadline_db.py -k 'first_deadline_persisted_once or test_http_resume_reports_and_persists_first_deadline'` —18PASS/16.72с; unit test_exec_fix05_first_deadline.py —10PASS/.55с. Bounded runner180с/no-progress60с, child_exited=true. Не случайный rerun доPASS: контролируемое воспроизведение предположения fixture, затем адресная правка.

Это регрессия обязательного CI, не изменение M7/product timers/оценивания и не новый путь Блок2/3/Report. Новый head требует обязательного CI. Проверенные frontend303/browser8/65protocol/23PG сохраняют применимость по прежним product/затронутым тестовым байтам; integration suite на прошломhead не объявляется PASS.
