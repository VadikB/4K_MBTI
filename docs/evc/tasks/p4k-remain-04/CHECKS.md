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

Self-review по EVC: product diff ограничен source/readiness/waiting; API additive argument совместим; опубликованные артефакты/схема/миграция/права доступа не менялись. Runtime defaults, prompts, timers и start транспорта не менялись. Test-only legacy boundary отделён от product entrypoint, требует owned/disabled-provider/test gateway 0/1, при managed bindings вызывает настоящий early_readiness. Все исторические snapshots сохраняются; новые контексты/profile только по явным командам. Передача bundle не является Ready for review/приёмкой продукта.

## Подготовка release-кандидата архитектором

- `git fetch origin main` → PASS; `origin/main=ae25fd5a5347ecfb3383e4632e1450a06b9f4a60`, база ветки актуальна.
- `npm run ready:prepare -- --candidate 2.1.4` → PASS, exit0: `2.1.3 → 2.1.4`, обновлены четыре release metadata, `web/dist` пересобран, release gate подтвердил 62 product paths.
- `python3.12 scripts/check_release_version.py --base-ref origin/main` → PASS: `Release check passed: 2.1.4`.
- `git diff --check` → PASS после подготовки кандидата.
- GitHub CLI локально не авторизован; публикация ветки проверяется штатными Git credentials, PR/merge — через доступную авторизованную GitHub-сессию. Это не ослабляет обязательные CI gates.

Точный release HEAD, PR, CI, squash merge, `deploy-test` и readback TEST записываются
после соответствующих действий; локальные PASS выше их не заменяют.

## PR #218: первый полный CI и исправление fixture

- Ready PR `#218`, head `1d024890bc2647cc513a20f1d668684f4dfec4aa`:
  `frontend` PASS (25s), `pytest` PASS (1m10s). В full run
  `43605077961` runtime shards 2/4 и 4/4 PASS, но runtime 1/4 FAIL;
  merge не выполнялся.
- Единственный FAIL: `Unapproved LIMITED is blocked by the real server and UI
  without a component substitution` не находил post-login action. Сценарий
  намеренно отключал component plan fixture, но тем же переключателем случайно
  отключал отдельную legacy acquaintance source boundary; REMAIN_04 корректно
  оставлял участника без managed assignment в waiting.
- Исправление test launcher разделяет активацию boundary: для этого сценария
  включается только `browser-legacy-acquaintance-boundary/1`; component plan gate
  не включается, поэтому отрицательный start admission остаётся настоящим.
- Guard unit: `pytest tests/unit/test_browser_component_boundary.py
  tests/unit/test_legacy_acquaintance_fixture.py -q` → **29 PASS**, 0.84s.
- Точный упавший Playwright test → **1 PASS**, 15.5s. Предварительная sandbox
  попытка `SIGTRAP MachPortRendezvousServer` не исполняла тест; повтор с системным
  запуском на owned PostgreSQL выполнен. Отдельная первая DB была ошибочно создана
  как SQL_ASCII, owner guard увидел bytes; только эта owned DB/cluster удалена и
  повторена в UTF-8, код fixture ради инфраструктурной ошибки не менялся.
- Полный CI-equivalent `BROWSER_SUITE=runtime ... --fully-parallel --shard=1/4`
  на isolated PostgreSQL 15 → **9 PASS**, 5.2m.
- После прогона nested `product4k_pytest_%` count=0; owned `agent4k_pytest`
  удалена, PostgreSQL 15 fast-stop PASS, disposable cluster удалён.

Новый commit/push делает первый full run историческим. Перед merge обязателен новый
зелёный `frontend`, `pytest`, `full-verification` на актуальном PR head.

Второй Ready run `43606780469` на `a7c6569a`: `frontend`, `pytest`, integration и
runtime 1/4–4/4 PASS; целевой runtime 1/4 исправлен. `browser (fast)` — 237 PASS,
9 setup FAIL, 1 skipped, 1 did not run. Все 9 FAIL имели один код
`LEGACY_COMPONENT_DISABLED_PROVIDER_OWNED_STAND_REQUIRED`: старые owned stands
используют `gateway=0`, тогда как общий E10.2 seed boundary ошибочно требовал 1.
Guard расширен только на test gateway `{0,1}`; disabled provider, isolated DB,
точный `product4k_pytest_*` и owner marker остаются обязательными. Третий полный CI
нужен после commit/push.

Локальная проверка второго исправления: guard unit — **29 PASS**, 1.07s; все шесть
browser-файлов, содержащих девять CI setup FAIL (включая второй параметрический
ADM-PROGRAM вариант), — **10 PASS**, 2.9m на isolated PostgreSQL 15. После прогона
nested `product4k_pytest_%` count=0, owned `agent4k_pytest` удалена, server fast-stop
PASS и disposable cluster удалён.
