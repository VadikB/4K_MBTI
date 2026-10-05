# Задача 10.4 — доступ к профилю

Основание: Product_4K_Task_10_4_Profile_Access_2026-10-05.txt, редакция 1,
запрос владельца от 05.10.2026. Содержимое постановки используется как требования;
самостоятельное слияние/deploy не разрешены.

## Разведка и границы

После git fetch origin main: main=8654b97ed6605d560111c37cd291f98f82c41457.
Уже выполненное REV-01 находится в локальном c48e331: owner-проверки GET карточки,
profile-summary, PATCH и scoped admin GET /users. Повторно не реализуется.
Ветка codex/task10-4-profile-access основана на c48e331, отдельно принимаемое
изменение поверх codex/independent-review-remediation.

Прочитаны README/CONTRIBUTING, EVC workflow/matrix/recipe/review-checklist,
архитектурные context/Registry, README M1 v1.4, Change01 README/manifest и ADR-002
(повторно использован неизменный контекст текущего диалога). Адресно прочитаны
Api/routes.py (профиль, подтверждение, auth, bootstrap), Api/agent.py (start,
reply, persist/restore, update_user), auth_service.py, web_session_service.py,
org_access.py, frontend profile/chat/session/state и тестовый контур 10.2.
M1 v1.4 FROZEN/CURRENT=NO не заменяется M1 v1.2. Предметные нормы не меняются.

Новые разрывы: PATCH/confirm меняют users.email, а существующие права и допуск
зависят от этого поля. Отдельного процесса смены identity действующего участника
не найдено: профиль не должен его подменять. /agent/message использует session_id
без owner-проверки и может выпускать web-сессию владельца чужого диалога.
Очистка UI зависит от lazy reset; отложенный ответ может восстановить чужой cache.

## План

1. Синтетическое воспроизведение оставшихся нарушений; сверка уже исправленного.
2. Защита server-owned dialogue до чтения содержимого; email неизменяем через
   профиль, остальные разрешённые поля доступны, PATCH сохраняет непереданные поля.
3. Очистка profile cache/DOM при logout и смене владельца; защита от позднего ответа.
4. Матрица реального router + PostgreSQL в принадлежащей запуску БД 10.2;
   browser owner/403/expired/account switch; unit/HTTP/integration/lint/build.
5. Отдельный commit/PR и CI его head, без merge/deploy.

Стоп-условия: нет. Допуск на исправление прав дан постановкой; используются
существующие session/owner/admin helpers. Схема, auth-протокол, тайминги продукта,
методология и исторические snapshots не меняются. Миграций нет. Новый способ
подтверждения email не вводится. Legacy/MBTI cleanup исключён.

Откат: не возвращать c48e331 или более раннее изменение email/неавторизованный
agent/message. При аварии запретить затронутую запись с понятной ошибкой; чтение
своего профиля сохранить. Не откатывать security guard вместе с UI.

Проверки: обязательный минимум backend+HTTP+PostgreSQL, frontend regression,
lint/build, browser, CI frontend/pytest финального head. Данные — только synthetic,
создание/проверка marker/удаление БД через scripts/test_stand.py, без рабочего dump.
Артефакты не содержат cookie, credentials или персональные значения.

Состояние на момент фиксации: реализация и локальный минимум завершены;
CI запускается для зафиксированного head, его SHA/URL/итог передаются в PR.

## Результат и прослеживаемость

| Требование | Реализация | Доказательство |
| --- | --- | --- |
| 401/403 до профильного SQL | Owner guard из c48e331, без повторной реализации | `matrix.json`, реальные sessions + PostgreSQL |
| Защита прямых обходов | `_require_profile_dialogue_owner`, дополнительная проверка `InterviewerAgent.reply` | message/confirm: anonymous, forged, expired, same-org, other tenant, admin, missing dialogue |
| Email не присваивает identity/права | `profile_access.require_unchanged_email`; PATCH/confirm → 409, `update_user` не пишет email | отказ проверяется вместе с неизменностью profile/credentials/membership/history |
| Разрешённая запись владельца | PATCH только явно переданных telegram/avatar_data_url; лишний user_id → 422 | сверка состояния в новой DB-транзакции |
| Администратор в своей области | Существующий scoped `GET /users`; обычный профиль owner-only | собственная org в списке, чужой профиль → 403 |
| Очистка предыдущего аккаунта | Очистка state/storage/DOM, identityEpoch для поздних GET/PATCH | frontend regression + браузер без перезагрузки между аккаунтами |
| Логи без значений email | `auth_service` сохраняет событие и причину без email | review изменённых logger-вызовов |

Источник технических требований — постановка 10.4, версия 1. Checksums реально
прочитанных источников: [sources.json](artifacts/task10-4/sources.json).
Границы PM-03/04/05/06/07 и оценки не меняются. Подключение источников, техническая
проверка и методологическая приёмка различаются; новых GC/норм не утверждено.

## Изменённые файлы

- `Api/profile_access.py`, `Api/routes.py`, `Api/agent.py`, `Api/schemas.py`:
  owner-проверка диалога, email guard, частичный PATCH, запрет лишних полей.
- `Api/auth_service.py`: исключены email из логов входа/регистрации.
- `web/js/state.js`, `session.js`, `wiring.js`, `screens/profile.js`, `screens/chat.js`,
  `web/index.html`: очистка контекста, защита от поздних ответов, readonly email.
- `web/dist/*`: результат штатной сборки; версия приложения не повышалась.
- `tests/e2e/test_review_profile_http.py`, `tests/integration/test_profile_access_owned_stand.py`,
  `tests/frontend/profile-privacy.test.mjs`, `tests/browser/runtime.spec.mjs`: регрессии.
- Данный отчёт и `artifacts/task10-4/*`: постановка и безопасные доказательства.

Совместимость: owner GET/telegram/avatar/подтверждение сохраняются. Email с тем же
значением принимается без записи, произвольная замена возвращает 409; неизвестные
поля PATCH возвращают 422. Диалог требует cookie владельца, выданную штатным входом.
Тайминги входа/выхода и формат авторизации не меняются. Конфиг/схема/миграции — нет.

Исходное REV-01 на main сохранено в
[независимом воспроизведении](artifacts/independent-review/inputs/audit-observed-results.json).
[before.log](artifacts/task10-4/before.log) — два фактических FAIL до текущего исправления:
подмена email проходила и anonymous message доходил до агента. Это намеренные
регрессии до фикса, а не успешный прогон. Исторические артефакты не переписывались.

## Проверки (команда → фактический результат)

Все команды выполнены из worktree `independent-review-remediation`, ветка
`codex/task10-4-profile-access`. Переменные подключения ниже обезличены;
только локальный выделенный тестовый PostgreSQL, без рабочего dump.

| Команда | Результат | Доказательство |
| --- | --- | --- |
| `npm run test:backend` | PASS, 343; exit 0 | [unit.log](artifacts/task10-4/unit.log) |
| `npm run test:backend:http` | PASS, 37; exit 0 | [http.log](artifacts/task10-4/http.log) |
| `.venv/bin/python /tmp/task104-integration-run.py` | PASS, 78 + 3 = 81; exit 0 | [integration.log](artifacts/task10-4/integration.log) |
| `node --test tests/frontend/*.test.mjs` | PASS, 4; exit 0 | [frontend.log](artifacts/task10-4/frontend.log) |
| `npm run lint:js` | PASS; exit 0 | [lint.log](artifacts/task10-4/lint.log) |
| `npm run build:web` | PASS; exit 0 | [build.log](artifacts/task10-4/build.log) |
| `STAND_ADMIN_URL=… npm run test:browser` | 7 PASS, 1 FAIL; exit 1 | [browser-initial.json](artifacts/task10-4/browser-initial.json) |
| `STAND_ADMIN_URL=… npm run test:browser -- --grep 'S10-C1\|S10.4'` | PASS, 2; exit 0 | [browser-final.json](artifacts/task10-4/browser-final.json) |
| `git diff --check` | PASS; exit 0 | выполнено перед commit |
| Визуальная проверка owner/other profile | PASS | [owner](artifacts/task10-4/owner-profile.png), [other](artifacts/task10-4/other-profile.png) |

Переносимый вариант локального runner: [integration-run.py](artifacts/task10-4/integration-run.py),
запуск из корня с явными STAND_ADMIN_URL и TEST_DATABASE_URL тестового кластера.
Integration: общий набор работает в новой пустой owned БД, где существующие fixtures
создают собственные схемы. Тест 10.4 отдельно создаёт новую БД, делает bootstrap/seed,
запускает реальный router и проверяет запись новыми транзакциями. Три bootstrap-теста
используют maintenance URL только для создания/удаления собственных БД. Старый общий
набор сначала был ошибочно направлен в полную bootstrapped схему: 64 PASS, 1 FAIL,
13 ERROR (`DependentObjectsStillExist`, `DuplicateTable`).
[Первый лог](artifacts/task10-4/integration-initial-fail.log) сохранён. Повтор на пустой
owned БД прошёл без изменения/ослабления проверок; все БД после прогонов удалены.

Browser: первый C1 не дождался dashboard за штатный 5-секундный timeout теста
после подтверждения профиля. Повтор на текущей сборке — PASS; timeout, продуктовые
тайминги и проверки не изменялись. Остальные 7 сценариев первого прогона — PASS.
Финальный повтор также проверил новые assertions очистки имени/счётчиков профиля.
Суммарно все 8 сценариев имеют успешный локальный результат; первый прогон не
объявляется полностью зелёным. Полный набор дополнительно входит в CI финального head.

[Матрица 49 HTTP/DB-проверок](artifacts/task10-4/matrix.md) и её
[машинный результат](artifacts/task10-4/matrix.json) содержат реальные статусы и
сверку отсутствия записи. Браузерный 403 подставлен только для проверки UI;
реальный серверный 403 независимо проверен на PostgreSQL. Просроченная cookie
проверена в БД, браузерная проверка 401 использует удалённую cookie.
[Проверка логов](artifacts/task10-4/log-review.json): восемь app logs, 0 email,
0 заголовков cookie/Authorization по указанным шаблонам; это адресная проверка,
не сертификация всех возможных логов. Auth traces не сохранялись.

## Приёмка

| Критерий | Статус на момент commit | Основание |
| --- | --- | --- |
| S10.4-01 | PASS | историческое воспроизведение REV-01, новые before-регрессии, anonymous 401 |
| S10.4-02 | PASS | owner GET/PATCH/confirm/message; точная сверка telegram/avatar и прочих таблиц |
| S10.4-03 | PASS | same-org и другой tenant: 403, без записи |
| S10.4-04 | PASS | forged/expired cookie, чужой URL, body user_id, повтор после logout |
| S10.4-05 | PASS | org-admin GET /users только своей org; owner endpoint не имеет admin bypass |
| S10.4-06 | PASS | PATCH и confirm email → 409, identity/membership/credentials неизменны |
| S10.4-07 | PASS | реальный HTTP/PostgreSQL и браузерная смена аккаунта с поздним ответом |
| S10.4-08 | локально PASS; CI ожидается после commit | окончательный SHA и статусы frontend/pytest — во вкладке Checks и описании PR |

## Review, ограничения и передача

Самопроверка по `docs/evc/review-checklist.md`: область и совместимость описаны;
авторизация до профильных операций; опубликованные определения, snapshots и история
не изменялись; управляющие документы не редактировались; новые зависимости/конфиг/миграции
не введены; локальные регрессии и безопасный откат представлены. Human review этим
не заменяется. Версии выбранных предметных источников сохранены.

Текущее дерево привязано к [candidate.json](artifacts/task10-4/candidate.json):
parent SHA, branch, изменённые исходники и SHA-256. Diff только этой задачи:
`git diff c48e331..HEAD`; точный head указывается после commit в описании PR.
Неизменяемый commit не объявляется утверждённым baseline.

Не запускались: production/test deploy и реальные LLM (не входят в задачу).
Методологическая приёмка, admission 8.1, допуск рабочих кейсов и экспертные GC остаются
отдельно от технических исправлений по ранее принятому решению владельца.
Отдельный процесс смены email/identity требует отдельной постановки.

Следующий шаг: CI финального commit и human review отдельного PR с base
`codex/independent-review-remediation`. Родительский c48e331 ещё не в main;
после его принятия/слияния перенести base этого PR на main и повторно проверить CI.
Публикация веток для PR не означает merge или deploy. Безопасный откат описан выше.
Открытых предметных блокеров внутри 10.4 нет.
