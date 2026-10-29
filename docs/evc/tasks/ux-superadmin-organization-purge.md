# UX: подтверждаемое физическое удаление организации

## Результат

Суперадминистратор test-контура может после деактивации физически удалить
организацию и все связанные данные через UI с точным подтверждением кода и
фиксацией backup reference.

## Область

- Включено: отдельный API purge, test/pytest guard, superadmin RBAC, обязательная
  деактивация, точный `code`, подтверждение необратимости, backup reference, UI.
- Не входит: production/pilot, автоматическое создание backup, удаление аккаунтов
  пользователей, изменение методологии.

## Контекст и решения

- Основание: решение владельца 2026-10-29; полный purge тестовых организаций
  разрешён, включая assessment history и snapshots.
- Прочитано: обязательные EVC-документы и архитектурный комплект из задачи
  `ops-test-organization-purge.md`, текущие routes/schemas/UI/tests.
- Архитектурный адрес: эксплуатационная операция над данными PM-02–PM-07;
  предметные контракты не меняются.
- Решение: физический purge отделён от деактивации и доступен только для уже
  неактивной организации в test/pytest-БД. Пользователи сохраняются.
- Стоп-условия: закрыты решением владельца; production/pilot запрещены guard.

## План и состояние

- Завершено: проверенный CLI/service; реальный purge ООО «Лидум ПРО» на test;
  API, UI и адресная регрессия подтверждаемого удаления.
- Активный шаг: проверки, commit и PR.
- Следующий шаг: review, CI, deploy test и ручная приёмка.
- Ветка / base commit: `codex/superadmin-organization-purge` /
  `2f930bb9ee10c6acde7ebf50dc8d36462f642c90` (`main` на старте worktree).
- Версия выпуска: patch `2.0.35` → `2.0.36`; bump потребован обязательным
  CI release gate после изменения продуктового API/UI.

## Ограничения и риски

- Операция необратима после commit; восстановление — из указанного backup.
- Backend не создаёт backup сам: оператор обязан создать и проверить его заранее.
- В UI и логах не выводятся строки БД, секреты или содержимое удаляемых данных.
- Штатный DELETE теперь только деактивирует; физическое удаление выполняет
  отдельный endpoint с усиленным подтверждением.

## Критерии приёмки

- [x] Не-суперадмин и production/pilot не могут вызвать purge.
- [x] Активная организация, неверный code, отсутствие acknowledgement или backup
  reference дают отказ без изменения данных.
- [x] Неактивная организация удаляется вместе с зависимостями; users сохраняются.
- [x] UI показывает физическое удаление только суперадмину на test и только после
  деактивации; требует code, backup reference и финальный confirm.
- [x] Ошибка приводит к rollback и понятному сообщению.

## Проверка

- `git diff --check`, Python compile, JS lint/build.
- Unit/HTTP для guard и подтверждения.
- Integration purge на изолированной pytest-БД.
- Затронутые frontend regression tests; обязательный CI перед merge.

Фактические проверки 2026-10-29:

- Python compile: PASS.
- `tests/unit/test_admin_organization_purge.py` и
  `tests/unit/test_purge_test_organization.py`: `8 passed`.
- `node --test tests/frontend/*.test.mjs`: `88 passed`.
- `npm run test:backend:http`: `81 passed`, `12 deselected`.
- `npm run lint:js`: PASS; `npm run build:web`: PASS.
- `scripts/check_release_version.py --base-ref origin/main`: PASS (`2.0.36`).
- Адресная PostgreSQL 16 integration сервиса в итоговом worktree: `2 passed`.
- Полный backend-набор без `integration`, `e2e` и `llm`:
  `654 passed`, `259 deselected`; два предупреждения среды не влияют на результат.
- Готовность к merge не заявляется до успешного CI актуальной ветки.

## Откат

Код откатывается revert-коммитом. Уже удалённые данные восстанавливаются только
из backup, указанного при подтверждении операции.
