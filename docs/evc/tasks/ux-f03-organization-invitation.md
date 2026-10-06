# UX-F03 — привязка корпоративного приглашения к организации

Дата: 06.10.2026. Статус: **реализовано; DB integration и полный browser runtime
ожидают изолированную БД**.

## Результат и область

Нужна общая защищённая ссылка организации, которая показывает только разрешённые
название и вводный текст, переносит организационный контекст через действующий
email/password auth и не заменяет предварительный допуск по точному email.

Включено: серверная invitation-сущность, выпуск/отзыв ссылки суперадмином,
публичная проверка ссылки, привязка auth-токенов к организации, минимальный auth UI,
unit/HTTP/browser tests. Не входят: массовая рассылка, UX-02, M4 API, B2C,
автоматический запуск оценки и изменение оценочного runtime.

## Источники и решения

- постановка: `UX-F03_Organization_Invitation.docx`, редакция 1.0 от 06.10.2026;
- SHA-256 постановки: `3d319d29dc3589ee9861500b5618a6e1b27fb23da63e9e6e683ac46d7fc1c784`;
- база: `0f4902b95957c55500cd9ce41f6b2750f243e71c`;
- ветка: `codex/ux-01-visual-system`;
- Change 01 и task SourceSet прочитаны по маршруту AGENTS.md; предметные M1/M5
  контракты не меняются;
- SHA-256 Change 01 README `ac082bb94aac1b86c61d7e39589d76c886c6703ef3afc07bc8fecf1676a0a26d`,
  SourceSet manifest `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8`,
  context `effebfc639a572593b6171a7a57cfe60db09bba200909d8a4edafb0e7ac98ebb`,
  Registry `b663db7f557fc3de3abd2d9e86b596926274ba4c5e2170047d4a6e5e60c54001`;
- владелец продукта подтвердил в текущей задаче: ссылка общая; несколько организаций
  для одного пользователя не поддерживаются; default expiry 30 дней и ручной отзыв.

Техническое решение архитектора: отдельный непрозрачный случайный invitation token,
в БД хранится только SHA-256 hash. Запись содержит `organization_id`, expiry,
revocation и автора. Existing verification/reset tokens сохраняют разные purpose;
verification token получает server-side invitation reference. Query/sessionStorage
служат только транспортом и никогда не являются основанием доступа.

Стоп-условия сняты решениями владельца. Глобальная уникальность membership по
`user_id` сохраняется; direct login использует единственную явную membership.

## Реализованный контракт

- `organizations.invitation_intro` — отдельный публично разрешённый текст;
- `organization_invitations` — организация, SHA-256 token hash, expiry, revocation,
  server actor и timestamps;
- `auth_action_tokens.organization_invitation_id` и
  `auth_magic_links.organization_invitation_id` сохраняют серверную привязку;
- `GET /users/organization-invitations/{token}` возвращает только публичное имя,
  intro и expiry;
- `POST /users/admin/organizations/{id}/invitation` выпускает raw token ровно в
  ответе авторизованному суперадмину; `DELETE .../invitation/{id}` отзывает ссылку;
- auth request/login/register принимают optional `organization_invitation_token`;
  verification action продолжает контекст по server-side id;
- session restore возвращает единственный разрешённый организационный контекст;
- password reset не получает invitation ref и сохраняет прежний purpose;
- query/sessionStorage только переносят opaque token; все права проверяются сервером.

Изменены backend, auth UI, собранный `web/dist`, disposable stand и адресные
unit/HTTP/browser tests. Оценка и таймер приглашением не запускаются.

## Матрица I01–I08

| ID | Статус | Доказательство |
| --- | --- | --- |
| I01 | PASS contract | exact member A проходит существующий auth; invitation не создаёт профиль/результат |
| I02 | PASS | публичный endpoint возвращает только name/intro/expiry; token hash хранится в БД |
| I03 | PASS | membership перепроверяется по `organization_id`; B и same-domain negative покрыты tests |
| I04 | PASS contract | refresh сохраняет token, verification action переносит server invitation id; UX-F01 tests проходят |
| I05 | PASS | решение владельца сохраняет one-user-one-org unique constraint; произвольного выбора нет |
| I06 | PASS | invalid=404, expired/revoked=410; ссылка не создаёт заявку или допуск |
| I07 | PASS | verification/reset разделены purpose и схемой вызова; reset не получает invitation ref |
| I08 | PARTIAL | unit/HTTP/frontend PASS; browser test добавлен, runtime NOT_RUN без `STAND_ADMIN_URL` |

## Проверки

PASS:

- `npm run test:backend` — `356 passed`, `116 deselected`;
- `npm run test:backend:http` — `34 passed`;
- `node --test tests/frontend/*.test.mjs` — `6 passed`;
- `npm run lint:js`;
- `npm run build:web`;
- Python `py_compile`, `node --check tests/browser/runtime.spec.mjs`;
- `git diff --check`;
- визуальная проверка auth invitation-блока desktop: без clipping/overlap.

Предупреждения: внешнее `StarletteDeprecationWarning` в TestClient и существующее
Node `MODULE_TYPELESS_PACKAGE_JSON`; тесты успешны.

NOT_RUN:

- DB integration/migration: `TEST_DATABASE_URL` не задан;
- Playwright end-to-end на disposable PostgreSQL: `STAND_ADMIN_URL` не задан;
- startup import с локальной PostgreSQL: sandbox не разрешил TCP, база не задана;
- CI: выполняется перед слиянием, локальным агентом не подменяется.

Влияние: SQL DDL и полный cross-tab браузерный путь не исполнены на PostgreSQL в
этой сессии, поэтому готовность к merge не заявляется. Тестовый stand содержит
организации A/B, shared invitation и negative flow для запуска в CI/локальной test DB.

## Совместимость, безопасность и откат

Новые таблица/nullable columns не меняют существующие ссылки и auth-записи.
Обычный прямой вход продолжает работать по UX-F02. Токен не логируется и не
возвращается повторно после выпуска. Откат кода не требует удаления данных;
таблицу и колонки можно удалить отдельной последующей миграцией после возврата
всех читателей старого контракта.

## Передача

- base SHA: `0f4902b95957c55500cd9ce41f6b2750f243e71c`;
- result SHA: implementation commit указывается после локальной фиксации в handoff;
- UX-02 получает публичный organization context, состояния 404/410/403/network,
  правило one-user-one-org и отсутствие auto-start оценки;
- M4 не менялся; единственная membership остаётся источником organization identity;
- после отчёта UX-02 и другие задачи автоматически не начинаются.
