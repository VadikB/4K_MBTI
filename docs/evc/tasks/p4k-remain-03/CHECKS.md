# REMAIN_03 — проверки

Проверяемый код: `785ed19c1af0125c1ace5a4514f9e5537fc866ba` на base `7871a0c6952ca13047355fd17d1b3b8a7c1e9c96`. Следующий commit `46c0087d` добавил только browser-регрессию; финальный commit добавит только документы, runtime после `785ed19c` не менялся. Проверки Python/HTTP/адресной PostgreSQL выполнены после первого кодового commit `6f7ee3dd`, который отличается от `785ed19c` только JS, browser-тестами и `web/dist`. JS/frontend/browser/build/lint повторены после второго кодового commit. Полный integration повторён на неизменённом backend-коде. Локальный синтетический контур; внешних писем и LLM-вызовов не было.

| AC | Итог | Вход и первичное доказательство |
| --- | --- | --- |
| F15-AC01 | PASS локально | Owned batch, разные статусы и два адресата; partial/extra/duplicate и чужой адрес не дают ложного общего успеха. HTTP `153 PASS`; PostgreSQL адресно `18 PASS`; browser batch в `35 PASS`. Синтетический mail sink подтверждает вызов, но не внешнюю доставку. |
| F15-AC02 | PASS локально | Потеря до/после фиксации, повтор того же `operation_id`, reload, readback, поздний ответ при смене экрана/пользователя, отказ, refresh error и сохранение старых неизвестных операций. PostgreSQL адресно `18 PASS`, browser `35 PASS` (12 REMAIN_03); повтор не создаёт вторую запись/отправку. |
| F15-AC03 | PASS локально | UTC `expires_at` API/mail, UI-срок, границы UTC/Moscow, used/revoked/expired, старое/новое поколение и guard отзыва использованного приглашения. Python unit+HTTP, PostgreSQL адресно `18 PASS`, browser `35 PASS`. TTL-политика не менялась. |

## Команды и результат

| Команда | Результат |
| --- | --- |
| `git diff --check` | PASS, exit 0 |
| `npm run lint:js` | PASS, exit 0 |
| `npm run build:web` | PASS, exit 0; повторная сборка не дала diff `web/dist` |
| `node --test tests/frontend/*.test.mjs` | PASS, exit 0: 272 passed |
| `npm run test:backend -- --quiet` | PASS, exit 0: 1093 passed, 561 deselected, 1 известное deprecation warning |
| `npm run test:backend:http -- --quiet` | PASS, exit 0: 153 passed, 15 deselected, 1 известное deprecation warning |
| `npx playwright test tests/browser/adm-program-guards.spec.mjs --workers=1 --retries=0` | PASS, exit 0: 35 passed (12 REMAIN_03) |
| `TEST_DATABASE_URL=<owned isolated agent4k_pytest DB> STAND_ADMIN_URL=<owned isolated admin DB> .venv/bin/python -m pytest --run-integration -q tests/integration/test_r03_auth_invitation_db.py tests/integration/test_program01_invitation_revoke_db.py` | PASS, exit 0: 18 passed |
| `TEST_DATABASE_URL=<owned isolated agent4k_pytest DB> STAND_ADMIN_URL=<owned isolated admin DB> npm run test:backend:integration -- --quiet` | PASS, exit 0: 402 passed, 2 skipped (real-provider), 1250 deselected, 1 известное deprecation warning; 724.42 с. Повтор после переноса UTC-сериализатора, backend-код соответствует `785ed19c`. |

Первый полный integration на DB `remain03_pytest`: FAIL (362 passed, 9 skipped, 8 failed, 25 errors) из-за штатного ограничения имени БД и отсутствия `STAND_ADMIN_URL`. После переименования собственной DB в `agent4k_pytest` полный набор на предшествующем коде: PASS (402 passed, 2 skipped — real provider, 1250 deselected); повтор на точном коде указан выше. Пробный адресный запуск из обычной песочницы: 18 ERROR из-за запрещённого локального TCP; тот же тест с разрешённым доступом к собственному порту: 18 PASS. Эти неуспешные запуски не засчитаны как проверка продукта. Собственный PostgreSQL после повторного полного прогона остановлен: `pg_ctl status` exit 3 (`no server running`), `pg_isready` exit 2 (`no response`).

Draft [PR #217](https://github.com/VadikB/4K_MBTI/pull/217) открыт после прямого уточнения пользователя-архитектора. На документальном head `8006089b` быстрые CI [`frontend`](https://github.com/VadikB/4K_MBTI/actions/runs/43596327443/job/132451501906?pr=217) и [`pytest`](https://github.com/VadikB/4K_MBTI/actions/runs/43596327443/job/132451501721?pr=217) — PASS, `full-verification` — SKIPPED по условию draft. Пользователь явно согласовал patch `2.1.3`; `npm run ready:prepare -- --candidate 2.1.3` и `python3.12 scripts/check_release_version.py --base-ref origin/main` — PASS. После commit версии быстрый CI предыдущего head перестанет быть актуальным. Общий TEST/Prod/реальная доставка: NOT_RUN.

## Проверка кандидата версии 2.1.3 до commit

Содержимое runtime invitation после `785ed19c` не менялось; кандидат повышает только номер приложения и пересобирает `web/dist`. Согласование patch — прямой ответ пользователя-архитектора 14.11.2026. На рабочем дереве с `2.1.3`:

| Команда | Результат |
| --- | --- |
| `npm run ready:prepare -- --candidate 2.1.3` | PASS, exit 0; свежий `origin/main=7871a0c6`, preflight, bump и build |
| `python3.12 scripts/check_release_version.py --base-ref origin/main` | PASS, exit 0: `Release check passed: 2.1.3` |
| `git diff --check` | PASS, exit 0 |
| `npm run lint:js` | PASS, exit 0 |
| `node --test tests/frontend/*.test.mjs` | PASS, exit 0: 272 passed |
| `npm run test:backend -- --quiet` | PASS, exit 0: 1093 passed, 561 deselected |
| `npm run test:backend:http -- --quiet` | PASS, exit 0: 153 passed, 15 deselected |
| `npx playwright test tests/browser/adm-program-guards.spec.mjs --workers=1 --retries=0` | PASS, exit 0: 35 passed |

Полный локальный integration 402 PASS на неизменённом backend-коде `785ed19c` переиспользован по области; на новом head после Ready обязательный CI выполнит integration и browser заново. Повтор `ready:prepare` на committed head и CI записать после commit/push. Ни один локальный тест не отправлял реальную почту или LLM-вызов.
