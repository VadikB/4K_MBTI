# TGBOT-02: учебный контекст и создание Assessment Cycle

## Результат

Согласованный целевой путь: курс представлен организацией 4К, а опубликованный
snapshot учебного проекта, проектной роли CRISP-DM и спецификации оценки становится
контекстом конкретного назначения и создаваемого Assessment Cycle.

Документ фиксирует проектирование и стоп-условие перед runtime-реализацией. Он не
выдаёт отсутствующий методологический допуск за работающий Cycle.

## Область

- Включено в проектирование: стабильная идентичность курса, project assignment,
  immutable snapshot, сопоставление ролей, PersonalizedProfile и существующий путь
  prepare/start Cycle.
- Не входит в текущий шаг: новая методология, автоматическая публикация M3-роли,
  AssessmentProgram/Case Catalog, реальные LLM-вызовы, деплой и миграция production.

## Принятые решения владельца

- Решение от 06.11.2026: курс — организация верхнего уровня 4К.
- Учебный проект и точные версии ролей CRISP-DM — неизменяемый контекст назначения.
- Проект не выдаётся за предприятие.
- Email связывает Telegram-участника с существующей моделью пользователя 4К.

## Фактический контракт runtime 4К

До `m10_product_flow.start_prepared` действующий admission требует:

1. пользователя и активное назначение `organization_assessment_assignments`;
2. confirmed `questionnaire_response_revision` с точным `assignment_ref`;
3. published OrganizationContextVersion, RoleProfileVersion и confirmed
   UserContextVersion;
4. immutable PersonalizedProfile на опубликованной AssessmentConfiguration;
5. published AssessmentProgram с тем же `assignment_ref`, разрешённой M3-ролью,
   опубликованным Case Catalog и M7 parameter revision;
6. подготовленный Cycle; только затем разрешён start.

Источники: `Api/assessment_contexts.py`, `Api/assessment_programs.py`,
`Api/assessment_start_readiness.py`, `Api/acquaintance.py`,
`Api/product_cycle_preparation_queue.py`, `Api/m10_product_flow.py`,
`Api/routes.py`, ADR-002 и Change 01 traceability.

## Целевое отображение

| Учебный контур | 4К | Правило |
| --- | --- | --- |
| Курс + поток | Organization | Стабильный внешний ключ, не название проекта |
| Опубликованный проектный snapshot | Questionnaire revision / assignment scope | Один `assignment_ref` на проектную оценку |
| Роль CRISP-DM | Project context + явная ссылка на published M3 RoleProfileVersion | Без неявного fallback |
| Участник проекта | User + organization membership + active assignment | По сохранённому `agent4k_user_id` |
| Спецификация оценки | Published AssessmentConfiguration ref/checksum | Точная версия |
| Назначение | PersonalizedProfile + AssessmentProgram binding | Точные frozen refs |
| Прохождение | Prepared Assessment Cycle | Запуск только после admission |

`assignment_ref` должен быть стабильным машинным идентификатором, например
`edu:<integration-client>:<project-id>:<assessment-spec-version>`. Название курса,
проекта или email не используются как ключ.

## Необходимое расширение бота

Перед отправкой в 4К бот публикует отдельный immutable
`ProjectAssessmentContextSnapshot`, содержащий:

- стабильный `course_external_id`, название курса и поток;
- `project_id`, code, business problem, expected result и CRISP-DM stages;
- точные `ProjectRoleVersion` и функции участника;
- для каждой роли — обязательный `agent4k_role_profile_version_id` и checksum;
- точный `ProjectAssessmentSpec`, configuration ref/checksum и methodology ref;
- participant/assignment IDs, timestamp, publisher ref и общий checksum.

Email и Telegram ID в предметный snapshot не входят. `agent4k_user_id` передаётся
отдельно как техническая ссылка владельца Cycle.

## Предлагаемый сервисный API

1. `POST /integration/v1/educational-contexts/prepare`
   принимает immutable snapshot и идемпотентно создаёт/находит курс-организацию,
   membership, assignment и draft admission record.
2. Если published program/config/role/catalog не согласованы, возвращает
   `status=awaiting_admission` и список точных причин; Cycle не создаётся.
3. После human admission повторный вызов создаёт confirmed source bindings,
   PersonalizedProfile и ставит подготовку Cycle в существующую очередь.
4. `GET /integration/v1/educational-contexts/operations/{id}` возвращает состояние.
5. Бот сохраняет `external_cycle_id` только после `status=prepared`.

Новый API является адаптером к существующим PM-02/03/04, а не параллельным Cycle.

## Стоп-условие

Проектная роль CRISP-DM сама по себе не является опубликованной M3-ролью 4К.
Автоматическое использование `specialist_expert` либо автоматическая публикация новой
RoleProfileVersion изменили бы смысл оценки без источника и human admission.

До реализации зависимого runtime владелец должен подтвердить:

> При публикации роли проекта администратор обязан выбрать конкретную уже
> опубликованную RoleProfileVersion 4К; без выбора назначение и Cycle не создаются.

Рекомендуемый ответ: **да**. Если подходящей роли нет, сначала выпускается новая
версия M3 отдельным методологическим процессом.

## План после решения

1. Бот: добавить стабильную сущность курса и mapping проектной роли на M3.
2. Бот: публиковать `ProjectAssessmentContextSnapshot` с checksum.
3. 4К: добавить versioned external educational context store и service API.
4. 4К: адаптер существующих Organization/Assignment/M4/Profile/Program contracts.
5. 4К: очередь prepare Cycle и readback без cookie, с owner=`agent4k_user_id`.
6. Бот: сохранять operation/cycle IDs и показывать причины admission.
7. Проверки: unit, HTTP, PostgreSQL integration и синтетический first-case профиль.

## Проверки текущего шага

- `git diff --check` и проверка ссылок → требуется перед коммитом.
- Runtime/DB/HTTP → NOT_RUN: зависимая реализация остановлена на предметном решении.

## Действия выпуска

`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`.

## Откат

Текущий шаг меняет только проектную документацию. Откат — удалить документ; данные и
runtime не изменены.
