# Задача 10.5 — профиль участника → M4 → Cycle

Основание: постановка 10.5 ред.1, 05.10.2026. Зависимость 10.4 — commit
6764131570791b21508bbf7986773c54cef12f33, Draft PR #33. После fetch main:
8654b97ed6605d560111c37cd291f98f82c41457. Ветка codex/task10-5-user-profile-m4,
отдельный результат поверх 10.4; merge/deploy не поручены.

## Разведка, источники и план

Повторно используется неизменный прочитанный контекст README, CONTRIBUTING, EVC
workflow/matrix/recipe/review, architecture context/Registry, M1 v1.4 FROZEN CURRENT=NO,
Change01 README/manifest и ADR002. Адресно прочитаны M4.1–6 в
assessment_definitions/contexts/competencies_4k/1.1/m4_context_source.md, context_contract.json,
M3 RoleProfile (назначение, источники, версии), его repository и файловый manifest;
assessment_contexts, participant_profile, agent confirm/persist, m10_product_flow,
m7_cycle_planner, auth/dashboard/start routes, текущая форма, 10.2 seed и тесты REV-02.
M4.Context v1.0 требует только ФИО в UserContext; профессиональные поля необязательны.
Новые нормы достаточности/конфликтов не вводятся. Подробные hashes сохраняются в sources.json.

REV-02 уже подключил canonical builder к форме и имеет fresh-M4 browser test.
Не переделывается. Дополнительные разрывы: частичный commit legacy перед M4;
выбор последнего M4 по user_id без org/config scope; отсутствие отдельной ошибки
NO_ROUTE; форма ещё требует legacy role/профессиональные поля сверх M4.

План: воспроизвести частичную запись; атомарное canonical подтверждение без legacy
генерации; scoped выбор/проверка refs, checksum и статусов; явный profile_id при старте;
неоднозначность требует выбора, NO_ROUTE возвращает исправимое состояние без пустого
Cycle; owned PostgreSQL + browser + общие регрессии; commit/PR и CI его head.

Технические решения в пределах постановки: сохранять текущий контракт, добавляя
необязательные поля; пользоваться существующими таблицами/builder, без миграций;
старый numeric role_id не является M3 version_id. Новые подтверждения не изменяют
исторические snapshots. No-route не публикует WORKING кейсы.

Стоп-условия: отсутствуют для технической задачи. Admission 8.1, рабочий каталог
и экспертные GC остаются отдельными решениями владельцев. Синтетический маршрут —
только в принадлежащем тесту стенде. Новый UX, legacy cleanup и реальные LLM вне задачи.

Откат: отключить создание новых оценок/подтверждение с понятным сообщением,
сохранить чтение истории, owner/email guards 10.4 и все новые snapshots; не возвращать
частичную запись или выбор чужого scope. Версии/исходники не удалять и не пересчитывать.

Реализация: commit `2e03c308ccbe94e1136adbe60e9e3a74291e9eb7`. Последующий коммит
этой же ветки добавляет только отчёт/доказательства. Финальный head и CI указываются
в описании PR; CI родительского 6764131 этому изменению не приписывается.

## Реализация и связь с источниками

В основной форме больше не используется numeric `role_id` как вход M3. Выбор M3
содержит явный `role_profile_version_id`; при нескольких контекстах/конфигурациях
нет выбора первого элемента. Единственное опубликованное значение может быть
выбрано автоматически, неоднозначность требует действия участника.

Цепочка вызовов:

```text
chat.js → GET /users/assessment/profile/options
  → активная организация → опубликованные M3/OrganizationContext/configuration
chat.js → POST /users/agent/profile/confirm
  → authenticated owner/email → lock users → восстановление диалога из БД
  → participant_profile.confirm → confirmed UserContext
  → assessment_contexts.create_personalized_profile / build_from_confirmed_sources
  → контактная карточка + согласие + диалог + dashboard в одной транзакции
interview.js → POST /users/assessment/cycles/start(personalized_profile_id)
  → owner/org/config scope → текущий Cycle либо проверка актуального M4
  → M7 plan → допустимая первая AS → PM-04 runtime
```

| Данные формы | Канонический вход / использование |
| --- | --- |
| `full_name` | UserContext.identity; обязательное поле M4.2, не runtime-content |
| `position` | UserContext.professional.position_or_status; необязательное |
| `duties` | UserContext.professional.regular_tasks; необязательное |
| `role_profile_version_id` | опубликованная M3 version, доступная участнику |
| `organization_context_version_id` | опубликованный контекст активной организации |
| `assessment_configuration_id` | опубликованная конфигурация с M2 methodology 1.1 |
| `email` | неизменяемая identity по 10.4; не входит в M4 runtime |
| `telegram`, `company_industry` | контактная карточка; не подменяют подтверждённый OrganizationContext |
| старый `role_id` | только совместимость прежнего API без M4-selection; новая форма его не отправляет |

M4.2/3/4/5 → существующие validated sources, checksum, provenance и conflicts →
`assessment_contexts`, `participant_profile` → owned PostgreSQL acceptance и REV-02.
ADR002 / immutable Cycle → явный профиль и сохранённый `profile_ref_json` →
`m10_product_flow` → старый открытый/рассчитанный Cycle и Report не изменяются,
следующий независимый Cycle использует новый snapshot. PM-05/06/07 и их предметные
правила не изменены. Версионированные methodology/case/prompt definitions не изменены.

Точное повторение ввода возвращает тот же M4, блокировка участника сериализует
одновременные запросы. Неудача после INSERT M4 откатывает также карточку и согласие.
Новый ввод создаёт новую confirmed UserContext version и immutable M4. GET проверяет
источники без пересоздания профиля. Несоответствие checksum/источников блокирует новый
старт; старый Cycle использует собственный frozen reference.

`journey-state` теперь использует M4 и Cycle, а не полноту legacy user_role_profiles.
Восстановление сессии загружает сохранённое согласие и Telegram. Explicit M4 selection
передаётся также в restore/bootstrap/journey и повторно проверяется сервером: при
нескольких конфигурациях reload сохраняет выбор без доверия к browser storage.
Изменение повторяет уже существующий переход подтверждения к dashboard, без нового UX.

`NO_ROUTE` откатывает создание плана/Cycle/session в savepoint и возвращает отдельную
ошибку `M7_NO_ADMISSIBLE_CASE` с действием ответственного специалиста. Готовность M4
при этом сохраняется. Никакой автоматической публикации WORKING-кейсов нет.

## Регрессии и доказательства

Первый воспроизводимый FAIL атомарности — `artifacts/task10-5/before.log`.
Первый полный browser run: 9 PASS / 1 FAIL — reload вернул в legacy-профиль;
лог сохранён в `browser-before-reload-fix.log`. После исправления два новых
браузерных сценария прошли. Ошибки промежуточных тестовых ожиданий (терминальное
состояние Cycle и попытка второго membership при UNIQUE(user_id)) исправлены в
fixture; реальные ограничения и pipeline не ослаблялись.

Новый `test_profile_to_m4_owned_stand.py` создаёт и уничтожает свою БД через 10.2.
Перед подтверждением у участника нет UserContext/M4. Положительный путь проходит
через реальный TestClient/SQL, без подстановки repository. Adversarial draft для
проверки unconfirmed/checksum создаётся в отдельной откатываемой транзакции;
не становится входом реального прохождения. Все данные синтетические, gateway
детерминированный, внешние LLM не вызываются.

Browser `P10.5` использует `browser_profile=unprepared`; первый M4 создаёт форма.
`inspect_profile_browser.py` проверяет принадлежность стенда и работает в READ ONLY:
сохраняет нулевые counts до UI, M3/M4/config refs, checksum и Cycle/AS после старта.
Case fixture E10.2 и character-case-v1 остаются исключительно техническими, не GC.

Для P10.5-04 также используются прежние интеграции M3/M4 и REV-02: чужая организация,
недоступная роль, immutable версии, блокирующий конфликт. Новая owned приёмка
проверяет неподтверждённый UserContext, неверный checksum, отсутствующие refs,
чужой M4 и смену организации. Норма обязательности полей не расширена.

## Ограничения и передача

Репозиторий содержит пять CASE-TDISC-01…05 со статусом WORKING — см. `catalog.json`.
Нормативная готовность рабочего каталога не подтверждена. Состояние реальных БД не
читалось; синтетический допуск не закрывает admission 8.1, решения методолога и GC.
Техническая приёмка этого изменения не является приёмкой всей методологии/продукта.

Схема БД и исторические данные не мигрируются. Обратная совместимость: optional
поля запросов/ответов, прежнее подтверждение без M4-selection сохраняет свой API;
новая форма вызывает атомарный canonical путь. Массовая очистка legacy вне задачи.

Self-review по EVC: owner/email guards 10.4 сохранены; source/version/checksum chain
проверяется; defaults предметной нормы не введены; нет published edits; все DB
проверки на принадлежащих запускам стендах; результаты и ограничения разделены.
Ни merge, ни deploy не выполнялись. Для следующей задачи — отдельный приёмочный
review этого PR и зависимых 10.4/REV-01–04; рабочий каталог ведётся отдельно.

## Итог локальной приёмки

| Критерий | Статус и доказательство |
| --- | --- |
| P10.5-01 | PASS: browser receipts `before`: 0 UserContext, 0 M4, 0 Cycle; форма создаёт ready M4 |
| P10.5-02 | PASS: owner=1, org=1, M3 version=4, org-context=1, configuration=2, UserContext=2, M4=2; одна первая AS |
| P10.5-03 | PASS технической границы: owned synthetic fixture; repository WORKING не менялся |
| P10.5-04 | PASS: owned HTTP/repository негативные случаи + M3/M4/REV-02 регрессии |
| P10.5-05 | PASS: concurrent submit, rollback после INSERT, потеря ответа, повтор, reload; остаётся один M4 |
| P10.5-06 | PASS: новый M4, неизменный старый open/calculated Cycle и Report; новый независимый Cycle использует новый M4 |
| P10.5-07 | PASS: чужой M4 и прежняя организация отклонены; история и owner-boundaries в полном browser suite |
| P10.5-08 | PASS: ready M4, отдельная ошибка каталога, ноль новых Cycle/AS/результатов |
| P10.5-09 | Локально PASS; CI нового финального head выполняется после push и фиксируется в PR |

Синтетический M4 browser checksum:
`48ace0364e932f10bf93bed36ee0018b018db3dd87f3ce410809278cf1d05b3c`.
Полные ссылки/refs — [profile-cycle-receipts.json](artifacts/task10-5/profile-cycle-receipts.json).
Это значения одноразового стенда, не рабочие идентификаторы.

| Команда | Фактический результат |
| --- | --- |
| `npm run test:backend` | 343 PASS, `unit.log` |
| `npm run test:backend:http` | 37 PASS, `http.log` |
| `STAND_ADMIN_URL=<local maintenance> TEST_DATABASE_URL=<local maintenance test> .venv/bin/python docs/evc/tasks/artifacts/task10-5/integration-run.py` | 79 + 3 = 82 PASS, `integration.log`; первый набор на новой owned DB, bootstrap на своих disposable DB |
| `STAND_ADMIN_URL=<local maintenance> .venv/bin/python -m pytest --run-integration tests/integration/test_profile_to_m4_owned_stand.py -q` | PASS; полный вариант также входит в integration выше |
| `node --test tests/frontend/*.test.mjs` | 4 PASS, `frontend.log` |
| `npm run lint:js` | PASS, `lint.log` |
| `npm run build:web` | PASS, `build.log`; результат включён в commit |
| `STAND_ADMIN_URL=<local maintenance> npm run test:browser` | 10 PASS / 0 FAIL / 0 retries, `browser.log`, `browser-summary.json`; Chromium 153.0.8010.12 |
| `git diff --check` | PASS |
| M3/M4 manifest checksums | 7 PASS, `artifact-checks.json` |
| Визуальная проверка | Прочитаны PNG формы при потере ответа и ready/no-catalog; поля и сообщение читаемы |

Доказательства в [artifacts/task10-5](artifacts/task10-5): request, sources/hashes,
implementation hashes, воспроизведение ошибки, owned acceptance, полные локальные
логи, browser-summary, receipts и три PNG. `.test-stand/state.json`, credentials и
дампы БД в Git не включены. Реальные LLM: NOT_RUN, не нужны для технического контракта.
CI родительского PR не используется как PASS задачи 10.5. Окончательный CI/head/base
публикуется в описании нового PR, human review остаётся отдельным шагом.
