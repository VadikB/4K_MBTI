# REMAIN_03 — проверки

Исходный проверенный код: `785ed19c1af0125c1ace5a4514f9e5537fc866ba` на base `7871a0c6952ca13047355fd17d1b3b8a7c1e9c96`; текущая версия в PR — `bca3fc79` плюс адресная коррекция browser CI ниже. Проверки Python/HTTP/адресной PostgreSQL выполнены после первого кодового commit `6f7ee3dd`; backend-код после `785ed19c` не менялся. JS/frontend/browser/build/lint повторены после каждого изменения JS. Полный integration повторён на неизменённом backend-коде и прошёл в Ready CI на `bca3fc79`. Локальный синтетический контур; внешних писем и LLM-вызовов не было.

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

## Ready CI на `bca3fc79` и коррекция

- Повтор `npm run ready:prepare -- --candidate 2.1.3` на committed head — PASS, `Ready preflight passed: release 2.1.3; product paths: 65`; tracked diff пуст.
- Быстрый draft CI на `bca3fc79`: [`frontend`](https://github.com/VadikB/4K_MBTI/actions/runs/43597099597/job/132453835148?pr=217) PASS, [`pytest`](https://github.com/VadikB/4K_MBTI/actions/runs/43597099597/job/132453834903?pr=217) PASS. PR переведён в Ready по прямому согласию архитектора.
- Ready [Full verification run](https://github.com/VadikB/4K_MBTI/actions/runs/43597260416): integration, четыре runtime browser shards, `frontend`, `pytest` — PASS; [`browser (fast)`](https://github.com/VadikB/4K_MBTI/actions/runs/43597260416/job/132454322226?pr=217) FAIL: 241 PASS, 1 SKIP, 3 FAIL. Required `full-verification` FAIL вследствие этого job. Этот CI не принят.
- Три сбоя `browser (fast)`: `ADM28 real isolated backend` ожидал известный `EMAIL_PROVIDER_NOT_CONFIGURED`, получил unknown; `AC18-ADM-1B` ожидал точное сообщение о неполном batch, получил unknown; `R03 network retry` повторно нажал скрытую после рендера старую кнопку и превысил timeout. Первые два — дефект новой обработки, третий — устаревший сценарий теста после появления явного readback. Исправлено без второго эффекта: известный код завершает операцию, неполный ответ сохраняет точный диагноз и pending identity, повтор использует «Проверить исход», GET 404 и тот же idempotency key.
- После исправления: `npm run lint:js` PASS, `npm run build:web` PASS, `node --test tests/frontend/*.test.mjs` — 272 PASS, адресный `npx playwright test tests/browser/auth-r03.spec.mjs --grep 'AC18-ADM-1B|unconfigured invitation provider|network retry reuses invitation' --workers=1 --retries=0` — 3 PASS. Первый расширенный browser запуск из ограниченной песочницы завершился `listen EPERM 127.0.0.1:18764` до тестов продукта; повтор с разрешённым доступом к собственному тестовому серверу — 158 PASS, 1 штатный SKIP за 3.1 мин. Инфраструктурный запрет не засчитан как продуктовый FAIL.
- Провалившийся CI сценарий `adm28-real.spec.mjs` повторён на собственном изолированном PostgreSQL (`STAND_ADMIN_URL=<owned isolated admin DB> BROWSER_PYTHON=.venv/bin/python npx playwright test tests/browser/adm28-real.spec.mjs --workers=1 --retries=0`) — 1 PASS за 18.9 с. Кластер `/private/tmp/p4k-remain03-pg` после этого остановлен `pg_ctl -m fast stop`; `pg_ctl status` → exit 3, `no server running`. Снимки, автоматически перезаписанные browser-тестом в `docs/evc/evidence/adm-status-01/`, восстановлены из исходного commit; unrelated diff нет.
- Дополнительный полный `adm-program-guards.spec.mjs` после первой коррекции выявил три FAIL при 32 PASS: старые REMAIN_03 проверки требовали явный текст «Исход отправки пока неизвестен» вместе с диагнозом неполного batch. Сообщение уточнено без изменения состояния/повтора; повтор этого набора — **35 PASS** за 34.7 с. Повтор адресных трёх `auth-r03` сценариев — **3 PASS**. Финальные `npm run lint:js`, `npm run build:web`, `npm run ready:prepare -- --candidate 2.1.3`, release guard и `git diff --check` — PASS. Промежуточный FAIL исправлен и не засчитан за финальный результат.
