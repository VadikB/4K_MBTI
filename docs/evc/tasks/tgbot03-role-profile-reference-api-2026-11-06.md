# TGBOT-03: read-only проверка опубликованной роли 4К

## Результат

Сервисный клиент Telegram-бота получает минимальную проверенную ссылку на published
`RoleProfileVersion` через `GET /integration/v1/role-profile-versions/{version_id}`.

## Область

- Включено: Bearer-auth из TGBOT-01, проверка существующим M3 loader, HTTP contract.
- Не входит: публикация/изменение роли, definition JSON, Organization/Profile/Cycle.

## Источники и решения

- Решение владельца от 06.11.2026: project role обязана явно ссылаться на published
  M3 RoleProfileVersion; fallback запрещён.
- Base: `5ecedee2`; используется `assessment_role_profiles.load_published_role_profile`.
- Ответ содержит только `id`, `code`, `version`, `methodology_version`, `checksum`.
  Draft/retired/missing и нарушенный checksum закрываются 404 без раскрытия содержания.

## Проверки

- Адресный HTTP → 6 PASS.
- `npm run test:backend:http` → 114 PASS, 12 deselected.
- `py_compile Api/integration_routes.py`, `git diff --check` → PASS.
- Full backend не повторялся: предсуществующие 3 M6 FAIL зафиксированы в TGBOT-01;
  изменение изолировано HTTP read-only контрактом.

## Действия выпуска

`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`.

## Откат

Удалить GET route. Данные и опубликованные M3-артефакты не меняются.
