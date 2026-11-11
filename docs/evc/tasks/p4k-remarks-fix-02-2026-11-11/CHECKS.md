# CHECKS — P4K-REMARKS-FIX-02

База `8442ae1975bc7debcc44eb1dcc7289d48c6f964d`. Поведенческий commit
`0fb071b48b46d5fa8ac52b1888924b2d6a764b79`; обновление только VM test harness
`62f1304b0280a95ff6c92f305e416c873b5d7c72`; финальные CSS/test constraints
`485919f6e03674935cfdd111b9551d6f2aea0164`. Следующий release commit добавляет
только подготовку версии2.0.97, сборку и этот отчёт; результаты не приписываются
ещё не запущенному CI. Machine evidence: [verification-summary](evidence/verification-summary.json).

## Локальные проверки

| Команда / область | Фактический результат |
|---|---|
| `shasum -a 256 -c SHA256SUMS.txt` внешнего пакета | PASS13/13; архив в Git не добавлен |
| `npm run lint:js`; `git diff --check` | PASS |
| `node --test tests/frontend/*.test.mjs` | PASS250/250 на62f1304; первоначальные4 failures старого VM harness устранены |
| `npm run build:web`; `git diff --exit-code -- web/dist` | PASS на62f1304, production JS тот же на485919f |
| `npm run test:backend` | PASS1065,518 deselected на0fb071b |
| `npm run test:backend:http` | PASS144,12 deselected на0fb071b |
| `npm run test:backend:integration` | Первый полный прогон:342 PASS,1 FAIL,25 ERROR,2 SKIP. Все26 отказов локализованы и повторены ниже |
| Target integration eight files (EXEC02/managed/participation/actor/questionnaire/purge/membership) | PASS47 на62f1304 после выбора штатного имени собственной reference-БД agent4k_pytest |
| `pytest --run-integration test_r03_auth_full_flow_db.py test_remarks_questionnaire_actor_owned_stand.py` | PASS2 на485919f после UTC настройки только owned PostgreSQL |
| Admin browser four spec files | PASS5 на0fb071b: real auth/HTTP/PG, manual/CSV, exclusion, purge и lost response |
| `playwright test --config=tests/frontend/remarks02-browser.config.mjs` | PASS3 на0fb071b: actual modules/DOM/handlers, synthetic transport faults |
| `playwright test tests/browser/remarks-admin-render.spec.mjs` | PASS1 на485919f,12 layout состояний1440/390/320×text100/200×empty/long tags |
| `npm audit --audit-level=high` | PASS gate;3 moderate dev-dependency advisories, high/critical нет; зависимости не менялись |
| `npm run ready:prepare -- --candidate 2.0.97` | PASS: fresh origin/main,2.0.96→2.0.97, source/dist, releasegate |

Общие backend/HTTP результаты применимы к финальному runtime: последующие изменения
касались только VM harness и CSS. SHA/хеши и границы сохранены в summary.25 ERROR
были fail-closed allowlist reference database name (не дефект продукта); единственный
auth FAIL — timezone disposable cluster Europe/Moscow, тогда как timestamp-контракт
ожидает UTC. Исправлена тестовая среда, guards/тесты не ослаблялись. Это повтор
затронутых отказов, а не объявление первого полного прогона зелёным. Два SKIP —
отдельно разрешаемые real-provider тесты; LLM не вызывался.

Для воспроизведения: собственный localhost PostgreSQL16, timezone UTC,
`TEST_DATABASE_URL=postgresql://<owned-user>@127.0.0.1:<owned-port>/agent4k_pytest`,
`STAND_ADMIN_URL=postgresql://<owned-user>@127.0.0.1:<owned-port>/postgres`,
`PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0`; команды npm из корня checkout.
Reference DB и cluster должны принадлежать исполнителю, рабочая .env не читается.

## Acceptance

| AC | Статус и доказательство |
|---|---|
| AC01 | PASS —10 real PG lifecycle cases + actual HTTP guards before/after exclusion, deny new assign; snapshots неизменны. [participation](evidence/participation-checks.json) |
| AC02 | PASS — существующий PR207,47 HTTP requests, admin/scoped/foreign/relogin/reinclude; root UI адресно открывает существующую форму повторного включения |
| AC03 | PASS — actual clicks preview faults/real403/self409 и локальная ошибка; pageErrors0. [purge](evidence/purge-browser-final.json) |
| AC04 | PASS — loss before/after real commit, reload, same command/operation/receipt, zero recovery preview, foreign actor/fingerprint guards; storage failures не обещают rollback |
| AC05 | PASS в browser matrix; email без44px колонки, focus/actions, long/empty tags, success/error, программа над2 groups. Native zoom и physical devices NOT_RUN; text200 и chat CSS zoom200 проверены |
| AC06 | PASS —manual/CSV, A uploaded/B confirmed и обратно, смена revision, fresh login, foreign403/404,4 immutable history snapshots,54 actual HTTP. [actor](evidence/questionnaire-actor-checks.json) |
| AC07 | PASS —actual Pause/Finish/Additional и channels; safe technical errors, точные business refusals. [handlers](evidence/chat-handler-errors.json) |
| AC08 | PASS в actual functions/browser synthetic faults; pending/unknown recovery priority, Send/Finish locked, exact draft revision и storage failure. PostgreSQL replay guards проверены отдельным integration, browser здесь не объявляется real commit |
| AC09 | PASS —deferred rejects owner/epoch/Cycle/AS/screen/load/view generation, включая leave→return той же оценки. [stale](evidence/chat-stale-rejections.json) |
| AC10 | PASS —actual formatter matrix detail/code, без предложения выключенного переноса; endpoint410 и server guards сохранены |
| AC11 | PASS —250 frontend,1065 backend,144 HTTP,47 target integration, browser manual/CSV/contact/C04/recipients и молчаливые ограничения/IME |
| AC12 | Локальная передача PASS; одна ветка, автор bvv.fructus@gmail.com, GitHub bvvfructus-jpg push=true. PR/full CI/main/deploy записываются readback при выполнении |

## Review и остаток

Независимое code review blockers не выявило после исправления найденных postcommit
purge ambiguity, recovery storage error и same-scope rejected callback. Авторство
выводится из escaped server revision; ручной автор не возвращён. Scheme/migrations,
Cycle/AS snapshots/history, methodology/admission/time/results не менялись.
Кандидат передаётся на обязательный полный CI; его статус читается для exact PR head.
Owner visual acceptance PENDING до просмотра TEST, исторический hang UNKNOWN.
Файлы state.json/пароли/cookies/tokens в evidence не экспортируются. Все созданные
stand DB удалены с ownership marker и independent absence readback.
