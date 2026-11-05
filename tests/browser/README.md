# Браузерная приёмка 10.3

Требуются Python-зависимости штатного тестового окружения, Node и PostgreSQL.
`STAND_ADMIN_URL` должен указывать на **локальный выделенный кластер**, где разрешено
создание/удаление БД. Рабочие `.env`, production/test сервера с реальными данными
не используются. Каждый runtime-тест через bootstrap 10.2 создаёт собственную
`product4k_pytest_*`, synthetic участников/входы, запускает сервер/worker и удаляет
только принадлежащую ему БД. При локальном последовательном прогоне порт 18830
должен быть свободен.

```sh
npm ci
npx playwright install chromium
npm run build:web
STAND_ADMIN_URL=postgresql://pytest:pytest@127.0.0.1:5432/postgres npm run test:browser
```

Локально используется `.venv/bin/python`; `BROWSER_PYTHON=python` — для CI.
На Linux для установки системных зависимостей: `npx playwright install --with-deps chromium`.
Нет implicit skip при отсутствии БД/браузера. Retries выключены, workers=1.
Локальный полный прогон остаётся последовательным. В CI runtime-набор делится
Playwright на четыре shard; каждый shard работает на отдельном runner со своим
PostgreSQL, поэтому фиксированные порты и временные БД между ними не пересекаются.
Остальные browser-spec выполняются отдельным fast lane параллельно с runtime и
backend integration. Новый `tests/browser/*.spec.mjs` автоматически включается в
fast lane. Для тяжёлого набора, которому требуется шардирование, нужно явное
решение о включении в runtime-контур; молчаливого исключения нового spec нет.

Основные A/B/C и positive T11 идут через реальный UI, cookie auth, HTTP, PostgreSQL,
workers и экспорт PDF. AI-граница подменяется явным техническим gateway;
Evidence ссылается на настоящие сохранённые Turns. `fixtures/v1.json` содержит
заранее заданные synthetic ответы и ожидаемые проявления, это не GC. Ответы
персонажа проверяются отдельно на отдельном CASE-BROWSER-CHARACTER-01 synthetic-v1; его технический допуск
и профиль team_lead задаются до старта. Пакеты в Git не получают FROZEN/CURRENT.
C1/C2 получают короткий план до первой AS; даты в существующем Cycle не переписываются.
Короткие значения передаются в `create_plan` до `prepare`, не новой ревизией после
подготовки AS; fixture проверяет совпадение Cycle/revision. Проверка связи AS с
текущей ревизией не ослабляется ради временных сценариев.

N3/N4 — явно отделённые редкие fixtures **после** завершения основной положительной
трассы: историческая Report revision и ошибка генератора. Они не создают IA/Results,
не подменяют основной T11 и проверяют неизменность Results. N5 — реальный owner API
регенерации, затем проверка idempotency и revision. Дополнительные гонки/четыре
исхода/версии проверяются существующим backend/HTTP/integration набором.

Артефакты: `.test-stand/browser-output/` и `.test-stand/browser-results.json`;
CI прикладывает их отдельно для fast lane и каждого runtime shard как
`full-verification-browser-*`. Вложения содержат только synthetic
Report/PDF/screenshots, серверный лог и assessment HTTP-ответы. Auth trace/cookies/
пароли не записываются. Не публиковать каталоги со `state.json` или `prepare.log`.
Успех browser suite подтверждает техническую интеграцию указанного gateway,
не качество реального provider, admission 8.1, экспертное заключение или Reliability.

### Граница старых component-сценариев после PATH-PILOT-02

Старый каталог `e102-controlled@1.0` не покрывает полный M2 и не имеет принятого
пилотного плана. Его прежний автоматический старт не считается продуктовым допуском.
Для сохранения независимых S10/M4/history/Report component-проверок явно подключается
`tests/browser/fixtures/component-plan-boundary-v1.json`: **SYNTHETIC upstream
plan-policy substitution**, не human review и не допуск программы. Аннотация
`synthetic_upstream` сохраняется в Playwright JSON; сервер пишет явный marker.

Только тестовый entrypoint `tests/browser_component_server.py` запускает тот же
`main.app` с узкой подстановкой чистого `plan_gate`; production entrypoint не меняется.
Обязательны проверка ownership, `product4k_pytest_*`, совпадение marker/DB,
`provider_mode=disabled` и gateway=1. Разрешены только pinned исходники старых
Case fixtures, точные ID/version/targets и каталог. Stored full M2/план/checksums не
переписываются; остальные проверки AS/профиля/назначения/времени не подменяются.
`tests/path29_browser_app.py` подключает ту же границу только в legacy-static
component-режиме. Для real provider, full PATH и published-pilot активация запрещена.

Отдельный browser-тест `Unapproved LIMITED ...` запускает **обычный main.app без
подстановки**, с assessment scope: UI не предлагает старт, HTTP start возвращает409,
Cycle остаётся prepared, calendar_deadline=null, AS не предъявлена. Реальный
положительный pilot gate/start проверяется SQL/HTTP suite
`tests/integration/test_pilot_start_admission_db.py`, с явно обозначенными
синтетическими записями upstream-согласования/LLM, не платным PATH. Таким образом
успех старого component-набора не выдаётся за допуск нового пилота.

Владелец 05.10 разрешил отдельный synthetic-кейс для персонажа. Он использует
структуру CASE-TDISC-04 и только материалы mandatory_update/character_reaction;
ветви условного раскрытия (включая спорную Асю) отсутствуют. Исходный CASE-TDISC-04
и CASE04_ASYA_BRANCH_CONDITION_REQUIRES_METHOD_OWNER_DECISION не изменены и
по-прежнему блокируют его обычный допуск. Fixture не является принятием CASE-TDISC-04.

C1 запускает отдельный обычный Chromium через CDP `noDefaults`, без флагов,
отключающих фоновое поведение. Проверяется реальное `document.visibilityState=hidden`
после открытия другой вкладки. Это не подмена DOM-свойства. Порт 18831 также свободен.
В Linux нужен Xvfb: `xvfb-run -a npm run test:browser` (как в CI).
Для сравнения текста PDF требуется тестовая зависимость `pypdf>=6.0.0`.

`AGENT4K_BROWSER_SCENARIO=acceptance-v1` устанавливает только helper из owned state.
Это технический профиль fixture; в production .env он не добавляется, без guard
изолированного стенда gateway не активируется.

## Интегрированная приёмка 10.7

`G10.7` создаёт тот же owned stand с `browser_profile=unprepared`. До UI read-only
SQL проверяет отсутствие UserContext/M4 у участника и всех AS/Turns/IA/Results/Report.
Новый сценарий проходит подтверждение роли/контекста, Cycle, уточнение, завершение,
Report/PDF; затем реальный logout, очистку cookies/storage, login, историю,
второй Cycle и идемпотентную регенерацию только представления первого.
HTTP/auth/worker/AS admission/Results/PDF не подменяются; upstream plan policy —
явная component-подстановка, описанная выше. Шесть прежних сценариев
10.3 остаются в полном наборе. Платных real-provider вызовов нет.
