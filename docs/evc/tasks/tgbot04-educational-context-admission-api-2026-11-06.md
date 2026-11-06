# TGBOT-04: регистрация учебного контекста и admission API

## Результат

`POST /integration/v1/educational-contexts/prepare` принимает immutable snapshot
назначения из Telegram-бота, проверяет checksum и опубликованную M3 RoleProfileVersion,
идемпотентно создаёт организацию курса, membership, pending assignment и внешний
контекст. До выполнения runtime prerequisites возвращается `awaiting_admission` с
машинными причинами; Cycle не подменяется фиктивным идентификатором.

## Источники, версии и границы

- Решения владельца и mapping: TGBOT-02, TGBOT-03; курс+поток → Organization,
  проект+роль → immutable assignment context.
- Change 01 `1.0/01` WORKING; M1 `1.4`, M3 `1.0`, M4 `1.0`, M5 `1.1`, M7 `1.3`
  из task SourceSet `2026-10-01`. CURRENT не присваивается.
- Применены существующие `assessment_programs.resolve`, M3 published loader и
  действующие таблицы membership/assignment. Новый параллельный Cycle не создаётся.
- Не входит: автоматическая публикация AssessmentProgram/Configuration/Catalog,
  подтверждение questionnaire и PersonalizedProfile, постановка подготовки Cycle.

## Контракт и безопасность

- Bearer-auth использует существующий `TG_BOT_INTEGRATION_TOKEN`.
- Email, Telegram ID, username и display name в snapshot запрещены рекурсивно.
- Повторный `assignment_ref` с другим checksum отклоняется; сохранённый snapshot
  защищён PostgreSQL trigger от изменения и удаления.
- Membership получает provenance `integration_api`; существующие membership и
  assignment не перезаписываются.

## Проверки

- `py_compile` изменённых backend-модулей → PASS.
- HTTP integration routes → 8 PASS; полный HTTP → 116 PASS, 12 deselected.
- PostgreSQL integration нового store → 2 PASS.
- Реальный LLM → NOT_RUN, не применяется.
- Полный backend → NOT_RUN: адресный DB и полный HTTP покрывают новый адаптер;
  известные предсуществующие M6 failures не относятся к изменению.
- CI → NOT_RUN до push/PR.

## Действия выпуска

`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`.

## Откат

Отключить route и вызов `ensure_schema`. Созданные организации, membership,
pending assignment и immutable context сохранять для аудита; физическое удаление
требует отдельного согласованного data migration.
