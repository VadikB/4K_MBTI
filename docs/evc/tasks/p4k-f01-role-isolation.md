# P4K-F01 — три роли и изоляция платформенного аккаунта

Дата: 11.11.2026. Тип: исправление подтверждённого дефекта. Результат: один
самостоятельный PR. База: `origin/main` `748be43e55587aa3b7e3a3945189c5ac737f59eb`,
версия 2.0.97; ветка `codex/p4k-f01-role-isolation`, отдельный worktree.
Рабочая копия `codex/tg-student-channel-api` с чужими изменениями не затронута.
Реализация и тесты: commit `da3304b76cbb71c4d165a4763f0746a38a68c881`
поверх указанной базы (12 путей, 452 добавления, 32 удаления).

## Источники, решение и границы

- Постановка владельца: `P4K-F01_Role_Isolation.txt` v1.0 от 11.11.2026,
  SHA-256 `a949850002fbb2ddfa3e05074cc1fb69420180de9a1577c95a3da8ada66f4b0a`.
  Пользователь прямо поручил исполнить эту карточку и после остановки сказал
  «продолжаем». Содержимое файла принято как требования результата; его
  операционные указания сами по себе не являются разрешением на push, merge,
  deploy или изменение действующих пользовательских данных.
- Прочитаны: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  `docs/evc/agent-workflow.md`, `verification-matrix.md`,
  `artifact-recipe.md`, `task-template.md`, `review-checklist.md`,
  `decision-register.md`; архитектурные
  `docs/architecture/product-4k/1.0/context.md`, `registry.md`,
  Change 01 `README.md` (WORKING, SHA-256
  `ac082bb94aac1b86c61d7e39589d76c886c6703ef3afc07bc8fecf1676a0a26d`)
  и релевантные фрагменты `source.md`, task manifest (SHA-256
  `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8`),
  M1 v1.4 `README.md`/§M1.4 (FROZEN source.docx SHA-256
  `5fa5ab5735dfe57fac6ef3c93aca50d149fbd7abd365edf80d362c10e2d7a975`),
  `docs/adr/002-cycle-as-dialogue-contracts.md`,
  `docs/evc/change01-traceability.md`, UX-F02 и связанные тесты. M1 v1.4 —
  FROZEN/CURRENT=NO; Change 01 — WORKING. Отдельный
  `P4K.DEV.PRINCIPLES` в репозитории и Downloads не найден. Норму этой
  функции задаёт прямое решение F01; недостающий вспомогательный файл её не блокирует.
- M1.4 и C-23/24/34 различают RoleProfile в оценке и доступ к платформе.
  Правило F01 относится к аккаунту и организационным операциям, а не к PM-02
  RoleProfile, PM-03/04 AS или фактическим расчётам PM-05. `users.role_id`
  не участвует в выдаче административного доступа. Проверка изоляции реализована
  в `Api/org_access.py`, маршрутах и auth-приглашении; оценочные контракт и
  snapshots не меняются.
- Действующие источники платформенных полномочий: точные нормализованные email
  из `SUPERADMIN_EMAILS`, служебный `admin@agent4k.local`, активная
  `user_platform_roles` с записью в `platform_role_permissions`.
  Для `SUPERADMIN_EMAILS` auth и org access теперь одинаково разбирают `,`
  и `;`. Конфигурационный email считается защищённым и при наличии
  `configured_access_suppressions`, поскольку другой действующий потребитель
  платформенных прав (`Api/platform_access.py`) не учитывает эту запись.
  Изменение семантики suppression вне F01 и требует отдельной задачи.
- Стоп-условия рабочего цикла: новая предметная норма, публичная схема/API,
  миграция/удаление данных, новый артефакт, чувствительная передача, выпуск за
  границами и неопределённый откат — **нет**. Основание новой границы прав —
  прямое решение F01; API сохраняет формат, добавляет нейтральный отказ 409.
  Сохранённые ошибочные связи остаются на месте; план их точного исправления
  понадобится отдельно. Откат к базовому commit отменяет только новое
  поведение; данных не удаляет.

| Источник → правило | Контракт и граница | Код → проверка |
| --- | --- | --- |
| F01 v1.0: платформенный аккаунт не вступает в организацию | `users` + `organization_memberships`; доступ платформы отделён от роли организации | `org_access.is_platform_protected_account`, attach и add-admin → F01 HTTP и DB integration |
| F01 v1.0: обычный admin не видит платформенную принадлежность | `AdminOrganizationsResponse` и персональное приглашение | серверная фильтрация списка, нейтральный 409, invitation guard → FastAPI/Playwright/PostgreSQL |
| M1.4 FROZEN/CURRENT=NO; Change 01 WORKING: RoleProfile относится к оценке | PM-02 → C-23/24/34 → PM-03/04; `users.role_id` не является RBAC | `get_admin_scope` по platform/org access, без `role_id` → отрицательный DB test; оценочные снимки не изменены |

## Реализация и обзор

- Защищённый аккаунт проверяется после email lock и до обновления имени,
  должности, identity, профиля, членства и admin suppression. Применено к форме,
  CSV, созданию администратора, auth auto-assignment и персональным приглашениям,
  включая поздний повтор. Отказ обычному администратору не сообщает класс роли.
- Выдача `/users/admin/organizations` для обычного администратора исключает
  защищённые записи из `admins`, `members` и `members_count` на сервере.
  Прямая проверка на ошибочной синтетической связи подтверждает отсутствие
  защищённого email и служебного имени в JSON и UI. Скрытие CSS не используется.
- `role='admin'` при добавлении участия сохраняется, `is_participant`
  становится `TRUE`; платформа не получает организационную роль.
- Изменены `Api/auth_service.py`, `Api/org_access.py`,
  `Api/organization_invitation_service.py`, `Api/platform_access.py`,
  `Api/routes.py`; регрессии в `tests/unit/test_org_admission.py`,
  `tests/unit/test_organization_invitation.py`,
  `tests/e2e/test_f01_role_isolation_http.py`,
  `tests/e2e/test_r03_invitation_http.py`,
  `tests/integration/test_f01_role_isolation_db.py`,
  `tests/integration/test_r03_auth_invitation_db.py` (добавлены только две
  таблицы платформенных прав в урезанный fixture), `README.md`.
  Схема, frontend bundle, methodology/scenario/configuration/prompt artifacts
  не менялись.

## AC и доказательства

Все адреса и аккаунты ниже синтетические; использованы только одноразовые
PostgreSQL 15 на `127.0.0.1:55492` и marker-owned
`product4k_pytest_*` БД. Реальные `.env`, почта и LLM не использовались.

| AC | Статус | Ожидаемое и фактическое |
| --- | --- | --- |
| F01-AC01 | PASS локально | `existing@example.test` и `new@example.test` из синтетического `SUPERADMIN_EMAILS`: integration 409 до записи `users`/`user_identities`/`organization_memberships`; HTTP форма/CSV/admin: 409 или CSV skipped, без раскрытия платформенной роли и записи. Реальный HTTP/PG проверен для формы, CSV и создания admin. |
| F01-AC02 | PASS для действующего списка | Реальный `GET /users/admin/organizations` и браузер: синтетические ошибочные membership для configured superadmin и активной platform role не видны обычному admin в списке и счётчике; служебное имя отсутствует. Отдельного поиска участников в текущем UI/API нет; проверялся серверный список, из которого строится UI. Сами ошибочные связи не удалялись. |
| F01-AC03 | PASS локально | Обычный участник добавлен через HTTP; admin с `is_participant=FALSE` после добавления участия сохранил `role='admin'` и получил `is_participant=TRUE`; чужая организация вернула 403. Активная platform role не превратилась в org-admin, а `role_id` оценки сам по себе прав не дал. |
| F01-AC04 | PASS локально | Прямые HTTP-запросы, варианты `,`/`;` и регистрационного/ещё не созданного email, auth auto-assignment, старое персональное приглашение и поздний повтор проверены unit/HTTP/integration. Повтор POST формы вновь 409, персональное приглашение после защиты адреса не отправлено повторно. |

## Проверки

- `git diff --check` — PASS.
- `shasum -a 256 -c SHA256SUMS` для Change 01 и M1 v1.4 — PASS.
- `py_compile` изменённых Python-файлов — PASS.
- Адресные unit/HTTP: `50 passed`; адресный DB integration:
  `4 passed`, включая проверку `role_id` оценки.
- `npm run test:backend -- --quiet` — `1068 passed, 529 deselected`.
- `npm run test:backend:http -- --quiet` — `152 passed, 13 deselected`.
- Полная схема: FastAPI TestClient → PostgreSQL — PASS; реальный браузер
  Playwright → локальный HTTP → PostgreSQL — PASS для формы/CSV и скрытия
  configured superadmin/активной platform role. Диагностические скрипты
  хранятся вне Git в `/private/tmp/p4k-f01-postgres`; проверяли только
  синтетические значения. Обе marker-owned БД удалены, локальный PostgreSQL
  остановлен, временный токен удалён.
- Первый полный `npm run test:backend:integration -- --quiet` —
  `360 passed, 11 failed, 2 skipped`: десять R03 invitation тестов
  отсутствовавшие `user_platform_roles` и `platform_role_permissions` в
  собственном урезанном fixture; после дополнения fixture адресный повтор
  `14 passed`. Один R03 auth full-flow получил `Retry-After=0` из-за
  `Europe/Moscow` в одноразовом PostgreSQL при UTC-времени приложения;
  после перевода **только этого локального кластера** в UTC адресный повтор
  `1 passed`. Полный повтор в корректной среде:
  `372 passed, 2 skipped, 1224 deselected` — PASS. Два skip относятся к
  явному real-provider LLM acceptance, который не входит в стандартный прогон.
- Draft PR [#211](https://github.com/VadikB/4K_MBTI/pull/211) создан к `main`.
  Для head `428c1337e144e261c2f1f86186d8a49ecb5a98ae` быстрый
  [CI](https://github.com/VadikB/4K_MBTI/actions/runs/43065958463):
  `frontend` PASS, `pytest` PASS. `full-verification` и `deploy-test`
  пропущены по правилам draft PR. После этого документального обновления
  быстрый CI нового head требуется сверить повторно.
- Main merge, TEST и human visual — NOT_RUN / PENDING; выпуска и человеческой
  приёмки не было. Локальный Playwright не равен визуальной приёмке владельца.

## Полномочия и следующий шаг

Локальная реализация, проверки и собственные commit завершены. После отчёта
владелец прямо ответил «Продолжаем»; в контексте обозначенного следующего этапа
это допуск на `branch_push=true` и `pr=true` для ветки F01 и draft PR к `main`.
Затем владелец отдельно утвердил patch-кандидат `2.0.98` и перевод PR в Ready:
`version_bump=true`, `ready=true`; `merge=false`, `deploy=false`,
`artifact_publish=false`. Вложенная карточка сама по себе такого допуска не
давала. `npm run ready:prepare` предложил `2.0.97 → 2.0.98`. Первый запуск с
кандидатом остановился на отсутствии `esbuild` в изолированном worktree после
обновления version-файлов и очистки `web/dist`; lockfile совпал с основной
копией, временная ссылка на её установленный `node_modules` позволила повторить
штатный `ready:prepare -- --candidate 2.0.98` — PASS. Дополнительно
`npm run lint:js` — PASS; `node --test tests/frontend/*.test.mjs` — 250 PASS;
`git diff --check` — PASS. Временная ссылка на зависимости удалена до commit.
Для Ready нужен полный CI `frontend`, `pytest`, `full-verification` точного
head/base. Визуальная приёмка владельцем — после разрешённого TEST. Действующие
данные и аккаунт суперадминистратора не изменять.
