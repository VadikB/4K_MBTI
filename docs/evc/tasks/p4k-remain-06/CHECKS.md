# REMAIN_06 — проверки и передача

## Результат

Локальный проверяемый кандидат `17291144c6d96a56db4cac30292427f327da69a9`, ветка `codex/p4k-remain-06`, base `07166475b478c843243102c748d51f8564b7cec0` (включает REMAIN05 PR219). Продуктовая версия не менялась. Код UI представляет только подтверждённые серверные progress/time: initial placeholder заменён неизвестностью; текущая позиция и завершённые позиции подписаны раздельно; progress fill использует completed/total. Missing/null/invalid Cycle time не берёт legacy deadline; 0 остаётся00:00. Current network failure снимает неподтверждённый остаток/пометку паузы; late foreign failure не меняет новый scope. Chat/draft/Continue/clipboard product handlers сохранены.

Первичные источники/хеши/решения — [TASK](TASK.md), текущая передача — [STATE](STATE.md). M1.6/9 → C24/34/45/46 → server read_runtime frozen route/status + UI renderProductRuntime/renderReturnCard/renderInterviewMeta/getRemainingCaseTimeMs → renderer/loader/native Chromium/HTTP/ownedPG ниже. Подключение источника не выдано за методологический PASS, CURRENT не присвоен.

## Идентичность

Все browser/PG факты получены локально, не на TEST. Во время запусков GitHEAD был base07166475 + рабочий diff. `receipts/{r1,layout}/source-identity.json` содержит startup fingerprints; `receipts/tested-source.json` связывает их с byte-identical code SHA17291144. API/backend и published artifacts относительно base неизменны. Позднее дополнялись только тесты/evidence. Это не CI exact remote head и не deploy proof. Переиспользованы существующие actual tests, выполненные заново в выбранной области, а не исторические статусы PASS без primary evidence.

## Команды и результаты

Все команды выполнялись из worktree; внешний runner `python3 docs/evc/tasks/p4k-remain-06/receipts/bounded-runner.py --seconds N --idle 60 --log receipt -- COMMAND` задавал deadline, log limit и TERM/KILL своей PGID. Тестовый профиль1200с/test90с/HTTP15с описан до run в STATE. Runner byte-identical ранее проверенному REMAIN05, положительный/deadline/no-progress контроль переиспользован из `../p4k-remain-05/receipts/runner-controls.json`, без правки validator.

| Команда | Факт | Primary receipt |
| --- | --- | --- |
| `node --test tests/frontend/remain06-projection.test.mjs` до исправления | exit1,3PASS/9FAIL | receipts/before.txt.gz |
| адресные projection/p3-a/p3-b/e01 после исправления | exit0,53PASS | receipts/after-targeted.txt.gz |
| `node --test tests/frontend/*.test.mjs` итог | exit0,321PASS | receipts/frontend-final2.txt.gz |
| `npm run lint:js` | exit0 PASS | receipts/lint.txt.gz |
| `npm run build:web` | exit0 PASS; build tracked в code commit | receipts/build.txt.gz |
| `pytest -q --run-integration tests/integration/test_m7_cycle_planner_db.py -k 'remain06 or controlled_return_179 or sales_r1 or presence_lease_119 or started_cycle_uses_saved_return_policy or return_policy_snapshot_fails_closed'` | exit0,10PASS/23deselected, PostgreSQL15 own localhost55446 | receipts/pg-after.txt.gz |
| `pytest -q tests/unit/test_m7_return_integration.py tests/e2e/test_m5_runtime_http.py -k 'return or presence'` | exit0,5PASS/9deselected | receipts/http-unit.txt.gz |
| `playwright test tests/browser/remain06-chat.spec.mjs --workers=1 --retries=0 --timeout=90000` | exit0,3PASS | receipts/browser-final.txt.gz |
| `playwright test --config tests/frontend/p3-a-browser.config.mjs tests/frontend/p3-a-r1-return.spec.mjs --grep 'R1 v2\|REMAIN06' --workers=1 --retries=0 --timeout=90000` | exit0,2PASS; real HTTP/ownedPG, one assessee Turn | receipts/browser-r1.txt.gz + receipts/r1/ |
| `playwright test --config tests/frontend/p3-a-browser.config.mjs tests/frontend/p3-a-chat-mobile.spec.mjs --grep 'short and long\|multiline draft\|computed text scale' --workers=1 --retries=0 --timeout=90000` | exit0,3PASS; 5 viewport/short+long; draft/reload; computed text200 | receipts/browser-layout.txt.gz + receipts/layout/ |
| `git diff --check` и staged check | exit0 PASS | рабочий diff/code commit |

PG environment: `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 TEST_DATABASE_URL=postgresql://remain06@127.0.0.1:55446/agent4k_pytest`; browser realPG `STAND_ADMIN_URL=postgresql://remain06@127.0.0.1:55446/postgres`; provider disabled, controlled gateway, real LLM/mail0. Только новая owned БД с test/pytest в имени, .env не читался. Backend full suite не требуется для product JS/HTML/CSS-only изменения; CI/frontend/pytest/full-verification будущего PR обязателен отдельно.

## Все15 AC

PASS в таблице относится к обозначенному техническому уровню; PARTIAL не повышается до полной приёмки. Code SHA17291144/tested byte proof выше.

| AC | Статус и фактическая граница | Первичное доказательство |
| --- | --- | --- |
| F17-AC01 | PASS Chromium1440/390, short/long, одна AS, авторы/public materials/без JSON/колонки | browser-layout.txt.gz, layout/*.json/png |
| F17-AC02 | PARTIAL:320/390/430/768, scroll/focus/draft/reduced viewport и synthetic text200 PASS; physical/software keyboard/native textzoom NOT_RUN | layout/*-scope.json, draft-reduced-viewport.json |
| F17-AC03 | PASS bounded: один saved Turn, reload возвращает его и scoped draft, Send оставляет active; request IDs/no duplicatePG; owner/AS late guards actual VM + native draft scope | r1/pg-readback.json, return-http-readback.json, frontend-final2.txt.gz |
| F18-AC01 | PASS plan8/catalog9/materialized1: обе server/UI проекции8, current1/completed0; fill по completed | pg-after.txt.gz, remain06-projection tests |
| F18-AC02 | PASS второй plan3, pendingGET/reload: нет placeholder1/5, unknown до GET, затем server facts | browser-final.txt.gz, component/ |
| F18-AC03 | PASS actual loader late owner/Cycle/AS/view guards, newer scope не перезаписывается; PG facts независимы от local state | frontend-final2.txt.gz p3-b-loader-scope, pg-after.txt.gz |
| F19-AC01 | PASS formatter+actual renderer positive/0/null/missing/invalid + browser unknown/0. Legacy fallback выполняется в synthetic mixed-state до fix; штатная browser-достижимость этого mixed-state UNKNOWN, fresh restore инициализирует legacy fields null. Узкий guard теперь не допускает legacy time для Cycle | before.txt.gz, frontend-final2.txt.gz, browser-final.txt.gz |
| F19-AC02 | PASS server-confirmed pause→Continue→sameAS/reload, прежний бюджет/deadline; календарные72ч не ожидались | r1/return-http-readback.json, explicit-return-card.png, pg-after.txt.gz |
| F19-AC03 | PASS current network→unknown без ложной паузы; late owner/Cycle response/failure отброшен; recovery constraints сохранены | browser-final.txt.gz, frontend-final2.txt.gz, pg-after.txt.gz |
| F20-AC01 | PASS ownedPG Continue+immediate heartbeat/old lease, тот же AS, нет обратного интервала/повторногоabsence/500 | pg-after.txt.gz existing presence_lease119_120 |
| F20-AC02 | PASS accepted/lost-response, один UI POST, replay same idempotency receipt, two tabs sameAS, foreign403; readback без новой команды | r1/remain06-lost-continue.json, browser-r1.txt.gz, pg-after.txt.gz |
| F20-AC03 | PASS R1v2 sameAS/no policy fail-closed/oldQA snapshot pinned; OPS01 отдельно NOT_RUN без допуска | pg-after.txt.gz snapshot parameterized, r1/source-identity.json |
| F21-AC01 | PARTIAL: native Ctrl/Cmd+V/Shift+Insert + synthetic paste/beforeinput/drop PASS, no clipboard read/clear, draft/cursor сохранены; OS context paste NOT_RUN | browser-final.txt.gz, component/*protected-selection.json, frontend-final2.txt.gz |
| F21-AC02 | PASS Chromium CSS исключает protected selection (selectionText empty), fallback actual handlerscopy/cut блокируют; contextmenu/drag synthetic blocked; owncopyallowed, realerror не стирается. Физические OS clipboard операции отдельно не заявлены | component/*protected-selection.json, browser-final.txt.gz, remain06-clipboard VM |
| F21-AC03 | PARTIAL: обычный ввод/native Chromium CDP IME/navigation и owner/AS guards PASS; actual handler matrix outside assessment auth/admin/onboarding PASS. Browser scope auth/admin/manual анкета дополнительно проверен в продолжении ниже; физические устройства NOT_RUN | frontend-final2.txt.gz, browser-final.txt.gz |

## Сохранённые неуспешные попытки

`pg.txt.gz`:8PASS/2FAIL — в новой test fixture был пропущен обязательный recognized_at; исправлен только тест, затем10PASS. `browser-component.txt.gz` и `browser-clipboard-after.txt.gz`: неверное ожидание preventDefault при CSS user-select:none, реального selection нет. После двух попыток выполнена диагностика вместо расширения: protected selectionText пуст; это штатная CSS защита. Handler matrix отдельно исполняет fallback. `browser-clipboard-diagnosed.txt.gz` PASS и итоговый browser-final PASS. Эти FAIL не стёрты. Первые initdb/pg_ctl sandbox не запустились (shmget/неткаталога); собственный запуск через разрешённую эскалацию прошёл, не ошибка продукта.

## Саморевью и риски

По review-checklist: scope одинPM04/UI; Api/SQL/schema/API/auth/published definitions не менялись, defaults предметной нормы не вводились. Отдельные current/completed отражают существующий server контракт. No-methodology/refactor/bump/PR/merge/deploy. Native/эмуляция/synthetic/PG различены. Все product source bytes после lint/build/browser неизменны; fingerprints проверены. Риски config/schema/privacy нет новых; build даёт штатный cascade chunk renames. Откат: revert code17291144 + штатный build при следующем согласованном выпуске; данные/история сохраняются. Управляющие документы не менялись.

## Ресурсы и следующий шаг

Owned preview БД удалены после PG readback; agent4k_pytest имела0schemas/0connections, удалена; PostgreSQLPID1140 остановлен, cluster directory удалён, restart=no. Зарегистрированные workers/browser/server PIDs завершены, ports55446/18933/18935 свободны. Containers0. `receipts/cleanup.json`, r1/layout cleanup — первичные подтверждения. STOP соблюдён:1Turn/currentASactive, Continue сохраняетAS, noFinish/Report/GC/paid/общийTEST.

Передача локальным bundle/веткой архитектору. Следующий этап: человеческое review, закрытие оговорённых native границ приёмки и подготовка release-кандидата/обязательный CI на exact PR head после отдельного допуска. Все внешние флаги остаются false, PR пользователем не создавался. PARTIAL пункты не выданы за полный product PASS.

## Продолжение14.11 — native scope и release-preflight

По прямой команде «продолжаем» fresh origin/main повторно прочитан через git fetch:07166475 прежний. Product code17291144, API/policies/build/version неизменны. Дополнен только tests/browser/remain06-chat.spec.mjs: actual assessment→logout→auth в том же browser page; actual admin/manual questionnaire typing и CDP IME, synthetic transfer-events не блокируются; CSV control native focus доступен. Системный clipboard не читался/не вставлялся, product writes0, DB/Turn/Cycle не создавались. Native browser boundary F21-AC03 теперь доказана; PARTIAL сохраняется только для физических устройств. F17-AC02/F21-AC01 physical/OS/native-zoom ограничения прежние.

Новый конечный профиль/ресурсы до run — STATE; actual run window и limits — receipts/native-scope/run.json. Первая попытка FAIL из-за выбора CSV-tab перед textarea manual формы; исправлен только тест. Адресный test1PASS, затем все4consumers общей authenticated/logout fixture PASS. Это регрессия изменённого test harness, не повтор PG/R1/Report. receipts/native-scope/{before,targeted,consumers}.txt.gz и scope-input.json сохраняют факты. Старые frontend321/PG10/HTTP5/layout3/R1browser2 применимы к прежним byte-identical product files.

Саморевью: scope теста ограничен F21, реальный ввод отличён от synthetic transfer events, без clipboard read/PII/реальных внешних сообщений. Новых product-дефектов при ревью diff не выявлено; это саморевью агента, не человеческая приёмка. Зарегистрированные PGID завершены, localhost18937 свободен, DB/container0.

Штатный python3.12 release-preflight exit2: нужен согласованный PATCH2.1.6; версия2.1.5 не изменялась. Вывод — receipts/native-scope/release-preflight.txt. Допуск version_bump/branch_push/pr/merge/deploy в TASK остаётся false. Следующий конкретный шаг: утвердить подготовку2.1.6 и независимые push/PR флаги; merge/deploy требуют последующей приёмки exact head/CI.

## Кандидат2.1.6 и разрешение PR

Прямое сообщение владельца14.11 разрешило режим архитектора, PATCH2.1.6, push своейветки и PR. merge/deploy/artifact_publish=false. Штатный ready:prepare2.1.6 PASS на fresh main07166475; номер назначен один раз. На release bytes frontend321,4component browser, lint/build/release gate/diff PASS. Первичные логи receipts/release216/*.txt.gz, source-binding.json подтверждает прежние Api/interview/wiring/CSS, поэтому PG10/HTTP5/R1browser2/layout3 переиспользованы без нового Turn/Cycle. Physical/OS/nativezoom PARTIAL остаётся явным ограничением приёмки. CI точного PRhead и humanreview следуют отдельно.
