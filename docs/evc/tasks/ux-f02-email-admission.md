# UX-F02 — корпоративный допуск по точному email

Дата: 06.10.2026. Статус: **частично; реализация остановлена обязательным
продуктовым решением о legacy membership**. Выполнен аудит и техническое
проектирование. Политика допуска, схема и runtime не изменялись.

## База и границы

- исходный HEAD: `97547379bc1c6346eee22d2d19b48aff64db4bf9`;
- ветка блока 1: `codex/ux-01-visual-system`, отдельная ветка/worktree не создавались;
- исходный `git status --short --branch`: чистый;
- result SHA: локальный commit, содержащий этот отчёт; проверяется через
  `git rev-parse HEAD` в переданном checkpoint;
- push, PR, merge, deploy, test-среда 10.8/10.9/08.2 и реальные данные не
  затрагивались.

Прочитаны `UX-F02_Email_Admission.docx` редакции 1.0, отчёт UX-00, применимые
AGENTS/EVC/архитектурные источники и текущие `auth_service.py`, `org_access.py`,
`routes.py`, `database.py`, `web_session_service.py`, схемы и тесты. Проверена
история появления domain admission (`547ec1c…`) без чтения пользовательских данных.

## Карта текущего допуска

| Точка | Текущее правило | Риск относительно UX-F02 |
| --- | --- | --- |
| Нормализация | `strip().lower()`; auth дополнительно валидирует один `@` и точку в домене | Соответствует точному email; точка и `+suffix` не удаляются |
| Предварительный add | `POST /users/admin/organizations/{id}/members` создаёт `users`, verified `user_identities` и membership | Exact email существует, но допуск ошибочно помечает identity подтверждённой |
| CSV import | `POST .../members/import` вызывает тот же `_attach_user_to_organization` | Повтор использует user/membership upsert; provenance не сохраняется |
| Кто добавляет | Оба endpoint требуют `_require_superadmin` | Обычный org admin не может вести allowlist; канал есть только у superadmin |
| Request link / mode | `_ensure_email_can_authenticate` вызывается до выдачи auth mode/token | Membership **или любой активный домен** дают доступ |
| Token confirm/register/login | Проверка допуска повторяется, затем `assign_user_organization_from_email` | Domain снова создаёт membership автоматически |
| Forgot password | Ошибки допуска/существования поглощаются, ответ нейтральный | Требование сохранено |
| Restore | `/session/restore` проверяет только действующую cookie-сессию | Изменение allowlist не влияет на уже выданную сессию |
| Reopen profile | Проверяет cookie, затем снова вызывает domain assignment | Возможен повторный auto-membership |
| Session bootstrap | `/{user_id}/session-bootstrap` не проверяет cookie/владельца | Прямой URL обходит admission и session ownership |
| Participant routes | Часть использует `_require_matching_session_user`; базовые get/list/profile endpoints не используют его | Серверная защита неоднородна; UI-проверки недостаточно |

## Происхождение membership

Схема `organization_memberships` содержит только `organization_id`, `user_id`,
`role`, `created_at`, `updated_at`. Явный add, CSV import и domain auto-assignment
для участника создают одинаковую строку `role='member'`. По текущим данным схемы
невозможно доказать, был ли конкретный исторический участник предварительно
разрешён человеком. Даты и домен не являются надёжным признаком и не использовались.

Отдельно различимы только служебные источники по роли/конфигурации:
superadmin определяется конфигурацией; org admin может быть настроен точным email
и получает `role='admin'`. Это не позволяет классифицировать historical members.

## Минимальный технический план после решения

Расширить существующий `organization_memberships`, не создавая параллельную модель:

- nullable `admission_source` с закрытым набором `admin_add`, `csv_import`,
  `configured_admin`, `legacy_unclassified`;
- nullable `admitted_by_user_id` и `admitted_at` для новых явных операций;
- новые add/import записывают источник и не устанавливают
  `user_identities.is_verified=TRUE` до фактического подтверждения почты;
- `email_has_organization_access` для участника принимает только точный email
  активной организации с разрешённым source; domain lookup удаляется из admission;
- `assign_user_organization_from_email` сохраняется только для точных служебных
  admin mapping либо заменяется явной привязкой уже разрешённой membership;
- restore, reopen, bootstrap и participant endpoints получают общий admission gate;
  bootstrap также получает обязательную session-owner проверку;
- при нескольких participant membership возвращается конфликт, а организация не
  выбирается через `LIMIT 1`; предметный выбор остаётся UX-F03;
- forgot-password сохраняет одинаковый нейтральный ответ.

Совместимость: новые записи однозначны, старые получают
`legacy_unclassified` только как признак неизвестного происхождения, не как
автоматическое разрешение или запрет. Откат схемы — сначала возврат чтения старого
контракта, затем удаление новых nullable columns; данные users/membership не
удаляются. До реализации миграции технический план требует подтверждения
архитектора и продуктовой политики ниже.

## Обязательное решение продуктолога

Нужно утвердить два связанных правила:

1. Считать ли все существующие на migration cutoff `role='member'`
   grandfathered-допусками, либо переводить их в `legacy_unclassified` без права
   нового входа до повторного add/import организацией?
2. Для уже выданных сессий legacy-участников: разрешить работу до естественного
   истечения текущей сессии или немедленно требовать повторного допуска при каждом
   restore/participant запросе?

Рекомендуемый безопасный вариант: не удалять memberships, классифицировать их как
`legacy_unclassified`, запретить **новую** аутентификацию до явной сверки, а уже
выданные сессии оставить до естественного истечения (не более действующего
24-часового activity window). Это избегает скрытого массового признания и
немедленного массового logout, но остаётся продуктовым решением.

## Матрица D01–D07

| ID | Статус | Доказательство / блокировка |
| --- | --- | --- |
| D01 | PARTIAL | Exact-email add и CSV существуют, но provenance отсутствует, identity преждевременно verified |
| D02 | FAIL current / BLOCKED fix | `email_has_organization_access` принимает active domain; auth создаёт membership по домену |
| D03 | FAIL current / BLOCKED fix | Auth token проверяется, но restore не revalidate admission; bootstrap не требует session owner |
| D04 | PARTIAL | Глобальный unique index ограничивает participant одним org, но access query и domain assignment используют `LIMIT 1`; политика UX-F03 не реализуется здесь |
| D05 | PARTIAL | Нормализация и upsert препятствуют простым дублям; положительный путь требует исправления verification semantics |
| D06 | BLOCKED | Исторический explicit и domain-auto member неразличимы; требуется решение продуктолога |
| D07 | NOT_RUN | Реализация и новые tests намеренно не начаты до D06; изолированный `STAND_ADMIN_URL` также не предоставлен |

## Проверки и остановка

Выполнены read-only поиск всех auth/admission точек, проверка схемы и git history,
извлечение и визуальная проверка трёх страниц постановки. `git diff --check` для
этого отчёта выполняется перед checkpoint. Unit/HTTP/browser tests не запускались:
runtime-код не изменён, а тест новой политики до выбора legacy semantics закрепил
бы неутверждённое поведение.

После отчёта работа остановлена. UX-F03 и UX-02 не запускаются. Продолжение UX-F02:
получить два решения продуктолога, подтвердить план schema migration, затем одним
отдельным изменением реализовать gate и D01–D07 на disposable localhost БД.
