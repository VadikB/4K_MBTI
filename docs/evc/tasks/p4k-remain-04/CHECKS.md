# CHECKS REMAIN_04 v1.6

Base: ae25fd5a, ветка codex/p4k-remain-04. Точный кодовый tested SHA будет записан после рабочего commit. Исторический 5a47e105/TEST2.1.0 не использован как текущий PASS. Никаких платных LLM, реальных писем, общего TEST/Prod, merge/deploy.

## Первичные локальные результаты

- `npm run test:backend -- --quiet`: 1091 PASS, 563 deselected, exit0, 85.60 с; product diff до fixture-адаптации. Повтор после нового helper выполняется.
- `npm run test:backend:http -- --quiet`: 153 PASS, 15 deselected, exit0, 45.73 с. HTTP handlers настоящие; отдельные downstream источники заменены техническими fixtures.
- `npm run lint:js`, `npm run build:web`: PASS. `node --test tests/frontend/*.test.mjs`: 275 PASS, включая настоящий waiting click/отказ/late owner/переход через server journey. `git diff --check`: PASS.
- Новый SQL/HTTP: tests/integration/test_remain04_acquaintance_db.py — первый вариант 2 PASS; после расширения источников/ACL/late negative повторяется на code SHA.
- Существующие review_m4_confirmation/w02_acquaintance/path29_scope_states: 4 PASS на первом адресном run (без LLM).
- Browser remain04-waiting.spec.mjs: 2 PASS, 5.5 с; login/directURL/reload/check, отказ GET, waiting→assignment→briefing→три ответа/edit/confirm, late logout. До 100 действий и 40 HTTP/сценарий. На 1440/1366/768/390/320, длинный текст, text200 и Tab. `auth-r03.spec.mjs --grep 'ADM28 superadmin still restores|ADM19-02 routes org-admin own assessment|W02 blocks direct entry'`: 3 PASS, 5.6 с.
- Browser первичные FAIL сохранены: fixture без session-bootstrap (2 попытки, вторая без изменения из-за shell encoding failure); text200 обнаружил nowrap кнопки — CSS исправлен; locator button для существующего summary — поправлена только fixture. Ни один FAIL не переписан в PASS.
- Полный `TEST_DATABASE_URL=<owned agent4k_pytest:55444> STAND_ADMIN_URL=<owned postgres:55444> npm run test:backend:integration -- --quiet` (эквивалент pytest --run-integration -m integration -q): **399 PASS, 2 skipped, 5 FAIL**, 674.50 с. Пять FAIL локализованы в старом component seed: clean_bootstrap, f02_tokens, path29_participant, path_admin_contract, profile_access. Новое ожидание без назначения отклоняло прежний fixture consent. Тестовый boundary адаптирован отдельно; выполняется адресный повтор упавших и зависимых сценариев, полный run автоматически не повторяется.

## Связь AC и проверок

| AC | Источник → контракт/код → проверка | Итог |
| --- | --- | --- |
| F24-AC01 | M1.4/M4.3–4, Change01 И-2/3 → participant_binding + exact assignment_readiness; admin default latest → remain04 SQL/HTTP revisions41/42 внутри orgA, orgB43, browser briefing41 | PASS (итог ниже) |
| F24-AC02 | REMAIN02 v1.4 модель доступа → REQUIRED_BRIEFING_FIELDS + recipient_access_projection; реальные membership gates → HTTP owner403/org confirm403; browser readonly | PASS (итог ниже) |
| F24-AC03 | M4.1 подтверждённый источник → missing/unconfirmed/ambiguous binding не fallback; owner epoch/requestNo → SQL negative/VM late + browser waiting/error/logout | PASS (итог ниже) |
| F25-AC01 | M4.2–4 → optional position/email не readiness gate, W02 raw/normalized + explicit resolve + transactional M4 → HTTP/PG rollback/replay/один профиль; browser minimal ФИО/W02/edit/confirm | PASS (итог ниже) |
| F25-AC02 | M1.4/M4.4 → новая assignment scope, новый UserContext/profile, старый snapshot неизменен → SQL exact byte-equivalent row + existing M4 lifecycle; browser edit/issues | PASS (итог ниже) |
| F25-AC03 | C-23/24/M4.5–6 → profile_for_start/validate_snapshot + late exact binding refs; content без identity → SQL owner/org/source/config/checksum negatives и M4 projection | PASS (итог ниже) |
| F26-AC01 | REMAIN04 no assignment → managed early_readiness waiting + participant check action → login/direct/reload, network без assign/prepare/start, SQL GET без профиля | PASS |
| F26-AC02 | F26 UI → focus heading + wrapping scoped buttons → 5 viewport, long text, text200/Tab | PASS; native zoom/физический телефон NOT_RUN |
| F26-AC03 | PM-02 не start → actual waiting click server journey/epoch → VM + waiting→briefing browser; ADM19 org-admin/ADM28 superadmin regression | PASS |

STOP нового сценария: profile readback, 0 AS/Cycle/Report, real LLM/mail0. Старый E10.2 component upstream fixture явно не доказывает REMAIN04/current assignment. Опубликованные пакеты, immutable профили и история не менялись. Обязательный CI и человеческое review — NOT_RUN до PR архитектора.

## Финальный результат на code SHA 57f56f863ad9535045b758ae6f2b1d451d9ff177

| Команда / область | Факт | Первичное evidence |
| --- | --- | --- |
| `npm run test:backend -- --quiet` | **PASS 1092**, 563 deselected; exit0; 74.50 с | receipts/backend.txt.gz |
| `npm run test:backend:http -- --quiet` | **PASS 153**, 15 deselected; exit0; 34.05 с | receipts/http.txt.gz |
| `npm run lint:js` | PASS, exit0 | tool output; frontend command chain exit0 |
| `node --test tests/frontend/*.test.mjs` | **PASS 275**, exit0 | receipts/frontend.txt.gz |
| `npm run build:web` + `git diff --exit-code -- web/dist` | PASS, exit0; сборка воспроизводится | receipts/build.txt.gz |
| `pytest --run-integration test_remain04_acquaintance_db.py test_path_admin_contract_owned_stand.py -q` | **PASS 3**, exit0; 12.04 с, exact code SHA | receipts/integration-exact-sha.txt.gz |
| Предыдущий адресный follow-up (14 tests) | 12 PASS, 2 FAIL; оба FAIL затем адресно исправлены и подтверждены в строке выше | receipts/integration-followup.txt.gz |
| `playwright ... remain04-waiting.spec.mjs --timeout=90000` | **PASS 2**, exit0; 5.8 с; product UI тот же что code SHA, два последующих изменения только HTTP fixtures | receipts/browser.txt.gz; waiting-320.png, waiting-text200.png, profile-confirmed.png |
| `playwright auth-r03.spec.mjs --grep ...` | **PASS 3**, exit0; org-admin/superadmin/W02 | receipts/browser-admin-regression.txt.gz |
| `git diff --check` | PASS, exit0 | финальная локальная команда |

Все 9 AC имеют технический PASS в заданной комбинации SQL/HTTP/VM/browser. Native zoom/физический телефон NOT_RUN (не блокирует автоматические проверки). Контролируемый browser не доказывает живой HTTP/PG — эти свойства проверены отдельно настоящими handlers/SQL. M4 component suite использует явно отмеченную legacy upstream fixture; это не новый допуск ожидания/назначения, LLM или GC.

Первый полный integration остаётся **FAIL**, не переименован в зелёный полный прогон. Его 399 PASS переиспользованы только для неизменённых областей; все 5 упавших тестов после fixture-исправлений получили PASS в адресных повторах. Дополнительно повторён изменённый M4 owned stand. Новый полный CI на PR head, человеческое review и визуальная приёмка TEST — NOT_RUN. 2 skipped полного run не считаются PASS; controlled scope не требует real-provider.

Self-review по EVC: product diff ограничен source/readiness/waiting; API additive argument совместим; опубликованные артефакты/схема/миграция/права доступа не менялись. Runtime defaults, prompts, timers и start транспорта не менялись. Test-only legacy boundary отделён от product entrypoint, требует owned/disabled-provider/gateway1, при managed bindings вызывает настоящий early_readiness. Все исторические snapshots сохраняются; новые контексты/profile только по явным командам. Передача bundle не является Ready for review/приёмкой продукта.
