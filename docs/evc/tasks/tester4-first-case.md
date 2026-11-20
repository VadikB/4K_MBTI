# TGBOT-08: первый Case для участника 4

## Поручение и границы

Владелец 20.11.2026 поручил назначить оценку ID=4 проекта PRJ-C100657129C7,
связать с 4К только на test и проверить первый Case в Telegram.
Спецификации/методология 4К не изменяются. Не подставлять согласие/ответы реального
человека, не создавать локальный предметный fallback. Чужие рабочие деревья сохранены.

## Разведка

4К base main 052a9be5 после параллельного PR; версия пока не проверена.
Новый собственный worktree /private/tmp/4k-tester4-first-case, ветка codex/tester4-first-case.
Бот main/deployed 49a47d8d; PR #7 отдельно открыт и его изменения не входят в этот выпуск.

Read-only preflight бота: ID4 active, Telegram linked; agent4k_user_id отсутствует;
role business_analyst v1 published, M3 binding отсутствует; spec v1 published,
configuration agent4k:configuration:11 (specialist_pilot_v1), methodology competencies_4k v2,
локальное число кейсов 5. Назначений/контекстов 0. Идентификатор курса есть.
На test OpenAPI содержит только /integration/v1/assessment-configurations.
Published M3 specialist_expert v1 ID2 найден; сопоставление требует решения владельца.

## Прочитанные источники

Повторно использован неизменённый контекст README/CONTRIBUTING, EVC workflow,
verification matrix, artifact recipe, architecture context/Registry, Change01/manifest,
ADR-002 из предыдущей части задачи. Дополнительно прочитаны:
- docs/architecture/product-4k/telegram-student-channel-v1.md (DRAFT/development_only);
- docs/evc/decisions/tg-student-channel-risk-acceptance.md (pending);
- docs/evc/integration/tg-student-channel-v1.json;
- docs/evc/tasks/tg-student-channel-api-implementation.md;
- TGBOT01/03 и фактические Api/integration_routes.py, educational_contexts.py,
  integration_identity_service.py в изолированной незавершённой исходной ветке;
- бот app/application/assessments.py, app/integrations/agent4k.py, app/bot.py.
Старый identity resolve передаёт email: не использовать для реального участника.

## План и ожидаемые решения

1. Preflight и контрактные пробелы — выполнено.
2. Ожидаются ответы владельца: synthetic/real ID4; mapping business_analyst→specialist_expert;
   допуск test-only API/expand двух технических таблиц с backup и отключением при сбое.
3. Подготовить additive интерфейсы на свежем main, сохранить исходные незакоммиченные
   файлы. Реальный person/subject и согласие не изобретать. Поведение программ не обходить.
4. Unit/HTTP + isolated PostgreSQL integration и основной web regression, точные
   совместимые SHA и полный CI до merge. Не использовать общий test для автотестов.
5. Backup, выпуск, mapping/assignment/context штатными сервисами; admission и первый
   Case через штатный runtime, ответы участника самим участником.
6. Подтверждение Telegram и отчёт фактических PASS/FAIL/NOT_RUN.

## Откат

Отключить Channel API/ботовый канал; revert release кода. Не удалять созданные
Cycle/Turn и published snapshots; технические expand таблицы остаются для readback.
Точная миграция/backup и target scope утверждаются до записи. Пока только read-only
серверная диагностика и локальная подготовка; DB writes и LLM NOT_RUN.

## Решения владельца после preflight

20.11.2026 подтверждено: ID4 — реальный участник, отвечает сам; business_analyst
сопоставляется со specialist_expert v1 (ID2); test-only выпуск API и двух
служебных таблиц после CI с backup разрешён.
Владелец отклонил предположение, что нужен отдельный пользователь/аккаунт 4К:
пользователи и контактная identity принадлежат исключительно БД бота.
Запрос agent4k_user_id был ошибочной зависимостью текущего adapter, не новым
требованием владельца. Персональные данные/аккаунты в 4К не создавать.

Найденный архитектурный пробел: current runtime привязан FK к users в M2 profiles,
organization assignments, Cycle owner, queue и ответах acquaintance. В main нет
непрозрачного external subject API. Старый email resolve не использовать и не
выдавать его за реализацию принятого решения. Это блокирует запись связи/первый
Case до совместимого решения технического subject; согласие на Channel API
не трактуется как согласие на копирование пользователей или переписывание норм.
Все серверные действия пока только read-only. Новые таблицы не создавались.


## Актуализация TGBOT-08: непрозрачный ключ (20.11.2026)

Прямое поручение владельца: «Исправь интеграцию через непрозрачный ключ без
создания учётных записей в 4К … до получения первого кейса … через стенд test».
Оно уточняет прежний допуск Channel API. Ранние пункты ожидания выше — история
preflight, не актуальные запросы повторного разрешения.

Контракт: бот один раз сохраняет случайный UUID4 до HTTP. Только UUID и
organization_ref поступают в `/integration/v1/subjects/resolve`; timeout повторяет
тот же ключ. 4К возвращает UUID/status, не ID пользователя. FK текущего runtime
сохраняется через анонимную техническую строку `users`: email, phone, job_description,
role_id отсутствуют; `full_name=subject:<UUID>` — технический alias, не ФИО человека.
Не создаются `user_identities`, password credentials, auth roles, login sessions,
email verification или приглашение на регистрацию. Контактная identity остаётся в
боте. Машинный actor организации также не имеет способа входа и не является
участником; используется только для аудита канонических операций.

Расширение схемы additive: `telegram_assessment_subjects`,
`external_educational_contexts`, `educational_channel_operations`; immutable subject
и snapshot; уникальность org/owner/canonical assignment запрещает повторную оценку
через другой внешний ref. Бот: nullable unique external_subject_ref; nullable
external_assignment_id до фактического канонического назначения. Старые записи и
snapshots сохраняются. Новая связь с legacy ID не смешивается.

Новый интерфейс не переписывает acquaintance, M2/M3, M5, M7, M10 или опубликованные
программы. External bot assignment_ref хранится отдельно от опубликованного
canonical assignment_ref. Список программ берётся из опубликованного каталога;
выбор версии — владельцем. Questionnaire readiness, source binding, consent,
подтверждение трёх ответов, профиль и очередь подготовки исполняются штатными
сервисами текущего main. GET не вызывает LLM. Действия имеют durable replay и
scope lock; конфликт ключа/ревизии отклоняется. Чтение /get_case не выражает согласие.
Прогресс — проекция participant_dashboard, а не число сгенерированных кандидатов.

Граница допуска: только test, закрытый по умолчанию flag, один UUID, один project
PRJ-C100657129C7, отдельная test organization. Production/pilot не включаются.
Синтетические тесты и их ответы не переносятся к реальному участнику.
PM-04 и подготовка по действующим контрактам используются повторно;
PM-05/06/07 и предметные нормы не меняются, соответствие всей методологии не заявлено.

### Проверки и выпуск

Backend unit: 1306 PASS; HTTP и полный isolated integration выполняются.
Адресный DB/HTTP opaque/admission/replay: 7 PASS.
Бот: 23 isolated integration PASS, 20 adapter/Telegram tests PASS.
Ошибка первого integration-прогона: не был задан STAND_ADMIN_URL для owned
stand tests; прогон остановлен (3 FAIL, 25 ERROR), повтор запущен с localhost
maintenance URL. Это не PASS и не основание отключать тесты.

Перед merge: локальный минимум, актуальный main/patch version, обязательные
frontend/pytest/full-verification CI. Затем backup test DB, сверка pg_restore list,
установка кода с flag=false, additive schema, отдельный org и scope allowlist.
Бот: backup и проверка restore list; применить точную expand migration после CI,
до merge доставить её серверному release gate (не обходить проверку AST миграций).
Миграция не удаляет и не преобразует существующие поля. Rollback — прежний код,
flag=false, расширение остаётся; downgrade запрещён при существующих subject или
pending preparation. Восстановление backup — только в отдельную БД для сверки,
не перетирать чужие данные/оценки.

Фактическое получение Case остаётся NOT_RUN: выпуск и реальные подтверждения
ещё не выполнены. Необходимые сведения организатора нельзя выдумывать;
участник сам принимает согласие, отвечает и подтверждает ответы в своём Telegram.

### Уточнение: источником является проект

Владелец отверг использование tz2/test16 и заполнение сведений компании:
«мы хотели подменить контекст организации контекстом проекта». Затем подтвердил
конкретную привязку карточки и формулировки цели/использования/реальности кейсов.
Organization остаётся техническим контейнером; содержательный источник —
immutable project snapshot. Подтверждённый операционный вход сохранён в
tester4-project-context.json; это данные данного запуска, не общий fallback.

project-context/preview адаптирует name/course/project facts к существующим
C01/C02a/C03/C17/C21 Questionnaire 0.2, channel=external_form. Цель, использование
и правила кейсов передаются явно, встроенных предметных defaults нет. Activity
содержит исходные business_problem, expected_result, description, stages и course.
project-context/confirm принимает точный revision/checksum только данного snapshot
и вызывает штатный questionnaire_sources.confirm для новой версии контекста.
Опубликованные спецификации, сценарии, программы и prompts не меняются.

Этап допуска из поручения довести сценарий и прежнего разрешения выпуска на test:
branch_push/pr/merge/deploy/version_bump=true только в пределах двух связанных PR;
artifact_publish — только подтверждённый контекст проекта и профиль после ответов
самого участника. Общий rollout, pilot и новые methodology/program/case definitions
не разрешены. Выбрана владельцем программа specialist_pilot 1.2.

### Локальные доказательства кандидата 2.1.48

- Backend: 1307 PASS, 727 deselected, exit 0.
- HTTP: 227 PASS, exit 0; новый project adapter unit — PASS.
- Integration: 469 PASS / 2 SKIP; 25 setup ERROR у двух owned-stand файлов
  из-за строгого требования имени maintenance DB, а не регрессии продукта.
  Повтор этих двух файлов с localhost/agent4k_pytest: 25 PASS, exit 0.
  Итого применённый integration: 494 PASS / 2 SKIP. SKIP — два explicit real-provider
  acceptance теста tests/llm/test_m10_real_cycle_db.py; реальные LLM не запускались.
- Адресный opaque/admission/project unit+HTTP+DB: 8 PASS, exit 0.
- lint:js, ready:prepare --candidate 2.1.48, py_compile, diff --check: PASS.
- Бот: ruff/mypy PASS, 97 unit PASS; 23 integration PASS; уточнение прав — PASS.
- CI и серверный выпуск PENDING; first Case реального участника NOT_RUN.

Источник → контракт → код → проверка: M4.required context / ADR-002 source binding
→ существующие Questionnaire 0.2 + participant context 1.0 + immutable source
bindings → telegram_channel preview/confirm/prepare → project unit и admission DB;
W02 / PM-04 → acquaintance и M10 → channel actions → durable replay DB/HTTP.
Методология не расширяется; готовность всего продукта по M1 не утверждается.

Контрольные SHA-256 использованных источников:
- ADR-002: 4a4e0170bee7faf137301b342fec46b3e8e0209acd26dcb6b2dc7a788c58b25f.
- Change01 manifest: f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8.
- Participant context 1.0: 3d4c18bbec032822b1c90e912f7ffadb4cd6f2765439d5fec16d2142a2d49071.
- Операционный вход проекта: d61be9d9fd1b29bdbf1ea7cdb29535870de4f38cd175d6c4434e6c329e92c4a4.

Review: без diff в core acquaintance/M2/M5/M7 и без изменения опубликованных
артефактов. Все endpoint требуют bearer + opt-in + org/UUID/project allowlist;
контакты отклоняются; публикация только точного preview. Два разных bot assignment
не могут использовать один runtime assignment одного owner. Scope только первого
Case: дальнейшие завершение/переход/отчёт канала не объявлены реализованными.

### Обновлённая база и кандидат 2.1.49

Пока выполнялся CI, main обновился ADM-FIX-04 (#266), SHA d3f6358e, версия 2.1.48.
Интегрирован merge без изменений чужой логики. Generated-конфликты web/dist
разрешены штатной пересборкой из объединённых исходников; ready:prepare для
непосредственного PATCH 2.1.49 PASS. Политика C17 теперь применяется ко всем каналам.
Подтверждённое владельцем «кейсы по проекту, с его названием» передаётся действующими
вариантами «Близко к реальной работе» / «Можно использовать настоящее название».
Тип контекста остаётся «учебный проект», факты — только из карточки, нормы 4К не меняются.
SHA-256 обновлённого операционного входа:
1e0ea35c707ac8b5fe6562b45d5412deb30bd2d86a4fac78099d4f92cd5074c2.

Совместная адресная проверка нового Questionnaire + project adapter + HTTP/DB:
40 PASS. Повторный probe на полной marker-owned схеме: UUID без auth records,
preview/confirm/replay проекта PASS, transaction rollback, provider_calls=0.
HTTP на новой базе: 232 PASS. Backend и полный integration выполняются заново;
окончательный CI и deploy остаются PENDING до точного head нового кандидата.
