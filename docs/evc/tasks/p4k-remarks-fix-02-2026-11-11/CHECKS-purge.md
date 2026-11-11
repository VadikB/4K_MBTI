# F03/F05 — адресная проверка purge и сообщений

База `8442ae1975bc7debcc44eb1dcc7289d48c6f964d`; проверки ниже выполнены на рабочем дереве до общего candidate commit. Фиксация exact code SHA кандидата — в общих CHECKS/STATE. Хеши проверенных файлов: [purge-checks.json](evidence/purge-checks.json).

- FIX02-AC03: **PASS** — actual production click/handlers + API controller; browser network/403/409/503 preview, real HTTP execute403/409 и self409. Нет unhandled/pageerror, raw technical strings, молчания. Определённый отказ снимает pending operation и разрешает новое preview/confirmation.
- FIX02-AC04: **PASS** — real localhost HTTP + owned PostgreSQL: abort до отправки; `route.fetch()` с реальным commit и последующим abort ответа; reload в обоих случаях; receipt-first повтор без нового preview. Команда `operation_id/email/fingerprint/target` одинакова до/после reload, один receipt и один delete-effect на target; другой actor/target/fingerprint не получает прежнее подтверждение.
- FIX02-AC10: **PASS** адресных formatter/handler tests и проверенного existing server scoped contract: строковый и object `code/detail`, legacy подсказка переноса, точная текущая организация, actual add-member error handler → production membership formatter → status. Отключённый server endpoint не менялся; actual server guards отдельно покрывает existing HTTP suite.

## Команды и evidence

`node --test tests/frontend/account-purge-recovery.test.mjs tests/frontend/api-safe-errors.test.mjs` → **32/32 PASS**. Это actual functions/handlers и transport fault tests в Node, не живой browser/PG.

`STAND_ADMIN_URL=<owned localhost maintenance PG55492> BROWSER_PYTHON=/tmp/p4k-adm-program-ui-fix-01-20261109/.venv/bin/python REMARKS_PURGE_EVIDENCE=/tmp/p4k-remarks-fix-02-purge-evidence npx playwright test tests/browser/remarks-purge-recovery.spec.mjs --workers=1` → **1/1 PASS**, 22.6s, 11 scenarios. [HTTP/PG/browser evidence](evidence/purge-browser.json), [independent owned DB cleanup](evidence/purge-cleanup.json). Session values не экспортированы; `.env`, external LLM/email и рабочие данные не использовались.

`npm run lint:js`, `npm run build:web`, `git diff --check` → PASS на текущем рабочем дереве. Общий финальный набор/CI и exact commit сохраняются главным агентом.

Browser screenshot: `/tmp/p4k-remarks-fix-02-purge-evidence/5c20b79e-188f-41d1-935c-c995d6645a30/purge-recovered.png`. Это Chromium на Mac, не physical device/owner visual acceptance. Первоначальный sandbox запуск Chromium не стартовал (MachPort permission); успешный прогон выполнен с разрешённым local sandbox escalation. Промежуточные fixture/entry-export FAIL устранены в этой задаче, все созданные test DB независимо удалены с ownership guard.

## Реализация и ограничения

Подтверждённая команда хранится до POST под actor, target, fingerprint и email; reload сохраняет ту же operation. При недоступном persistent storage delete не отправляется. Unknown имеет отдельную recovery карточку вне списка аккаунтов, включая уже удалённую цель. POST использует существующий серверный receipt-first readback до target lookup. Новый preview для recovery не нужен.

`PURGE_EXECUTION_FAILED` трактуется как unknown: серверный post-commit `invalidate_user` может завершиться ошибкой уже после commit. Клиент не заявляет rollback и сохраняет operation для receipt retry. Серверные preview/fingerprint/ledger, superadmin/self-delete guards, explicit irreversible confirmation не ослаблялись; backend purge API/схема не менялись.

После browser PASS добавлена адресная защита storage read/write failure при recovery ранее unknown команды: ошибка не утверждает, что прежнее удаление не отправлялось. Actual controller test покрывает оба отказа; source hashes обновлены, общий финальный build/регрессия фиксируются в общих CHECKS.
