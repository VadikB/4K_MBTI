# Браузерная приёмка 10.3

Требуются Python-зависимости штатного тестового окружения, Node и PostgreSQL.
`STAND_ADMIN_URL` должен указывать на **локальный выделенный кластер**, где разрешено
создание/удаление БД. Рабочие `.env`, production/test сервера с реальными данными
не используются. Каждый тест через bootstrap 10.2 создаёт собственную
`product4k_pytest_*`, synthetic участников/входы, запускает сервер/worker и удаляет
только принадлежащую ему БД. Порт 18830 должен быть свободен.

```sh
npm ci
npx playwright install chromium
npm run build:web
STAND_ADMIN_URL=postgresql://pytest:pytest@127.0.0.1:5432/postgres npm run test:browser
```

Локально используется `.venv/bin/python`; `BROWSER_PYTHON=python` — для CI.
На Linux для установки системных зависимостей: `npx playwright install --with-deps chromium`.
Нет implicit skip при отсутствии БД/браузера. Retries выключены, workers=1.

Основные A/B/C и positive T11 идут через реальный UI, cookie auth, HTTP, PostgreSQL,
workers и экспорт PDF. Подменяется только AI-граница явным техническим gateway;
Evidence ссылается на настоящие сохранённые Turns. `fixtures/v1.json` содержит
заранее заданные synthetic ответы и ожидаемые проявления, это не GC. Ответы
персонажа проверяются отдельно на отдельном CASE-BROWSER-CHARACTER-01 synthetic-v1; его технический допуск
и профиль team_lead задаются до старта. Пакеты в Git не получают FROZEN/CURRENT.
C1/C2 получают короткий план до первой AS; даты в существующем Cycle не переписываются.

N3/N4 — явно отделённые редкие fixtures **после** завершения основной положительной
трассы: историческая Report revision и ошибка генератора. Они не создают IA/Results,
не подменяют основной T11 и проверяют неизменность Results. N5 — реальный owner API
регенерации, затем проверка idempotency и revision. Дополнительные гонки/четыре
исхода/версии проверяются существующим backend/HTTP/integration набором.

Артефакты: `.test-stand/browser-output/` и `.test-stand/browser-results.json`;
CI прикладывает их как `browser-acceptance`. Вложения содержат только synthetic
Report/PDF/screenshots, серверный лог и assessment HTTP-ответы. Auth trace/cookies/
пароли не записываются. Не публиковать каталоги со `state.json` или `prepare.log`.
Успех browser suite подтверждает техническую интеграцию указанного gateway,
не качество реального provider, admission 8.1, экспертное заключение или Reliability.

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
HTTP/auth/worker/admission/Results/PDF не подменяются. Шесть прежних сценариев
10.3 остаются в полном наборе. Платных real-provider вызовов нет.
