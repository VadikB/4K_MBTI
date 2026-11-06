# TGBOT-06: явный выбор AssessmentProgram для учебного контекста

## Результат

Сервисный API позволяет преподавателю получить список совместимых published
AssessmentProgram и явно подключить выбранный `program_definition_id` к организации
курса. Автоматический выбор или публикация программы запрещены.

## Контракт

- `POST /integration/v1/educational-contexts/program-options` фильтрует по точному
  `assignment_ref` и RoleProfileVersion из immutable snapshot.
- `POST /integration/v1/educational-contexts/connect-program` повторно проверяет
  published status, scope и роль, затем вызывает существующий
  `assessment_programs.connect` с идемпотентным operation ID.
- Service integration не подменяется 4К-пользователем: `connected_by_user_id=NULL`,
  а решение преподавателя аудитируется в Telegram-боте.

## Границы

- Закрывается только `PROGRAM_NOT_CONNECTED`.
- Questionnaire, active assignment/source binding и PersonalizedProfile остаются
  в существующих human admission сценариях 4К.
- Предметные артефакты не создаются и не публикуются.

## Проверки

- `py_compile` → PASS.
- Адресный HTTP → 11 PASS; полный HTTP → 119 PASS, 12 deselected.
- PostgreSQL integration → 4 PASS.
- CI → NOT_RUN до push/PR; LLM → NOT_RUN, не применяется.

## Действия выпуска

`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`.

## Откат

Удалить два service endpoint. Существующее подключение программы сохранять как
аудируемое решение; смена выполняется штатным versioned connection path.
