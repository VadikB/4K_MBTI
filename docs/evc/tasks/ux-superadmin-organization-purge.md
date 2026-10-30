# UX: подтверждаемое физическое удаление организации

## Результат

Суперадминистратор test-контура может после деактивации физически удалить
организацию и все связанные данные через UI с точным подтверждением кода и
фиксацией backup reference.

## Область

- Включено: отдельный API purge, test/pytest guard, superadmin RBAC, обязательная
  деактивация, точный `code`, подтверждение необратимости, backup reference, UI,
  удаление orphan-аккаунтов и их auth/profile/session-зависимостей.
- Не входит: production/pilot, автоматическое создание backup, удаление аккаунтов
  участников других организаций, изменение методологии.

## Контекст и решения

- Основание: решение владельца 2026-10-29; полный purge тестовых организаций
  разрешён, включая assessment history и snapshots.
- Прочитано: обязательные EVC-документы и архитектурный комплект из задачи
  `ops-test-organization-purge.md`, текущие routes/schemas/UI/tests.
- Архитектурный адрес: эксплуатационная операция над данными PM-02–PM-07;
  предметные контракты не меняются.
- Решение: физический purge отделён от деактивации и доступен только для уже
  неактивной организации в test/pytest-БД. По решению владельца 2026-10-30
  orphan-users удаляются полностью; пользователи с membership в другой организации
  и их глобальные данные сохраняются.
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
- [x] Неактивная организация удаляется вместе с зависимостями и orphan-users;
  shared-users сохраняются.
- [x] UI показывает физическое удаление только суперадмину на test и только после
  деактивации; требует code, backup reference и финальный confirm.
- [x] Ошибка приводит к rollback и понятному сообщению.

## Проверка

- `git diff --check`, Python compile, JS lint/build.
- Unit/HTTP для guard и подтверждения.
- Integration purge на изолированной pytest-БД.
- Затронутые frontend regression tests; обязательный CI перед merge.

Фактические проверки 2026-10-29:

> Результаты ниже относятся к предыдущей редакции контракта без orphan-user purge.
> Текущая регрессия отдельно проверяет удаление orphan-аккаунта и сохранение shared-user.

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

Фактические проверки расширения 2026-10-30, кандидат `2.0.38`:

- предупреждение UI явно перечисляет orphan accounts, identities, credentials и
  sessions и сообщает о сохранении shared-аккаунтов.
- frontend regression: `91 passed`; ESLint и `npm run build:web`: PASS.
- unit purge/API: `8 passed`; адресная PostgreSQL integration: `2 passed`;
  backend без integration/e2e/llm: `655 passed`, `260 deselected`.
- HTTP/e2e contract: `82 passed`, `12 deselected`; release check `2.0.38`: PASS.
- полный integration: `172 passed`, `2 skipped`; первый запуск дал 6 ошибок из-за
  неверного `STAND_ADMIN_URL`, все затронутые stand-тесты повторены с разрешённой
  локальной maintenance DB: `7 passed`. Обязательный CI ожидает точного SHA кандидата.

## Откат

Код откатывается revert-коммитом. Уже удалённые данные восстанавливаются только
из backup, указанного при подтверждении операции.
