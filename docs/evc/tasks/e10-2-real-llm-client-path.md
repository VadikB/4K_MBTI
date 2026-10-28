# E10.2 — полный клиентский путь с реальным LLM

## Результат и границы

На test-стенде `http://178.236.26.203:8002/` создать нового участника организации
«Синтетическая организация E10.2» с ролью «Специалист», пройти полный клиентский
путь с реальными provider-вызовами, зафиксировать и исправить воспроизводимые
дефекты, выполнить регрессию и передать один PR. Методологические нормы, статусы
CURRENT/FROZEN, опубликованные пакеты и рабочие данные других пользователей не
изменяются. Секреты, cookies, пароли, auth tokens и полные пользовательские Turns
в Git не сохраняются.

## Разведка и источники

- База ветки после сверки с опубликованным стендом: `0b44c265c11f702f9755563ce6ebcdac4f18d831`
  (`origin/main`), ветка `codex/e10-2-real-llm-client-path`.
- Прочитаны: `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `verification-matrix.md`, `artifact-recipe.md`, `task-template.md`,
  `review-checklist.md`, архитектурные `context.md`, `registry.md`, Change 01,
  task manifest, ADR-002, `change01-traceability.md`, M1 v1.4 README и
  `tests/browser/README.md`.
- Технический контекст E10.2: `scripts/test_stand_seed.py`,
  `docs/evc/tasks/task10-2-reproducible-test-environment.md` и существующий
  browser-контур. Локальный fixture не считается учётной записью удалённого стенда.
- M1 v1.4 остаётся FROZEN / CURRENT=NO. Реальный прогон проверяет фактический
  продуктовый путь PM-03…PM-07, но сам по себе не утверждает GC/Reliability или
  методологический допуск.

## План

1. Получить допущенную административную сессию test-стенда и создать отдельного
   синтетического участника без реальных персональных данных.
2. Пройти регистрацию/вход, знакомство, профиль/контекст, подготовку и исполнение
   assessment, завершение, расчёт, Results/Report и повторный вход. Реальные
   provider-вызовы отмечать как `llm`.
3. Для каждого сбоя записывать шаг, ожидаемое/фактическое, версию стенда и безопасное
   доказательство; локализовать в коде, добавить регрессию, исправить и повторить путь.
4. Выполнить объединённый минимум матрицы для фактически изменённых типов, review,
   commit/push, создать PR и дождаться обязательного CI.

## Стоп-условия и текущее состояние

- Новая предметная норма, публичный контракт, схема/миграция, новый контур
  артефактов или изменение прав заранее не требуются. Если дефект потребует один
  из этих шагов, зависимая реализация будет остановлена до решения владельца.
- Безопасный откат исправлений: revert коммита PR; стенд развёртывается только
  штатным CI. Созданного synthetic-пользователя не удалять без отдельного допуска.
- 2026-10-28: стенд доступен, UI показывает версию `2.0.31`. Проверенный synthetic
  адрес локального fixture на удалённом стенде не допущен; UI корректно показал
  «Доступ пока не открыт». Рабочие учётные данные не угадывались и секреты не
  читались. Создание участника и дальнейший прогон ожидают административный доступ.

## Журнал проблем

### E10.2-LOGIN-01 — новый участник не маршрутизируется после успешного входа

- Наблюдение владельца 2026-10-28, стенд `2.0.31`: после ввода пароля UI показывает
  «Вход выполнен. Загружаем профиль…», затем «Не удалось определить актуальный этап».
- Пароль принят; сбой находится после аутентификации, в загрузке защищённого
  `GET /users/{user_id}/journey-state` либо в клиентской маршрутизации его ответа.
- Ожидание: свежий участник получает `wait_for_acquaintance_data`, `show_onboarding`
  или `complete_profile` в зависимости от готовности назначения/профиля.
- Пароль, cookie, auth headers и полные response headers не собирать и не сохранять.
- После reload пользователь снова видит гостевой email-экран, но общий текст ошибки
  сохраняется. Это подтверждает отсутствие восстанавливаемой browser session и
  отдельный дефект очистки/диагностики auth UI.
- Гипотеза `Secure` cookie отклонена доказательством: фактический test `.env` и
  runtime config дают `AUTH_SESSION_SECURE_COOKIE=false`, `APP_BASE_URL` использует
  `http`; server-side сессия существует, а `updated_at` совпадает с reload.
- С явного разрешения владельца выполнен один внутренний защищённый диагностический
  `GET journey-state` существующей test-сессией; token/cookie не выведены. Ответ:
  HTTP 200, `profile=incomplete`, `onboarding=not_started`,
  `next_action=show_onboarding`, readiness организации готова. Значит backend и
  session restore исправны, исключение возникает при клиентском открытии onboarding.
- Проверены опубликованные JS chunks onboarding/screen-loaders и зависимости:
  HTTP 200, `text/javascript`, файлы присутствуют.
- Console Яндекс Браузера дала точную причину: `TypeError: crypto.randomUUID is not
  a function` в импортируемом chunk. Стенд работает по HTTP, где этот Web Crypto API
  не гарантирован; top-level и runtime-вызовы в `interview.js`, `wiring.js` и
  административной M5 Lab обходили существующий совместимый `createOperationId()`.
- Исправление: все прямые browser-вызовы переведены на `createOperationId()` с
  совместимым fallback; W02 browser-регрессия запускает onboarding с намеренно
  отсутствующим `crypto.randomUUID`.
- Статус: FIXED_IN_BRANCH, публикация на test ожидает штатного PR/CI.

Дополнительно защищённый `journey-state` с `401` теперь
показывает потерю сессии, а не ошибочно неизвестный продуктовый этап; `5xx` сохраняет
прежний fail-closed текст. Добавлены unit и browser-регрессия login 200 → journey 401.

Отказ недопущенному локальному fixture email остаётся ожидаемым поведением допуска,
а не отдельным дефектом.

## Проверки

- Удалённый smoke: `GET /` через браузер — PASS, версия `2.0.31`.
- Недопущенный synthetic email — PASS ожидаемого отказа доступа.
- `npm run lint:js` — PASS.
- `node --test tests/frontend/api-unauthorized.test.mjs tests/frontend/auth-ux.test.mjs`
  — PASS, 14 tests.
- `npm run build:web` — PASS.
- `npx playwright test tests/browser/auth-r03.spec.mjs --grep "successful password response reports a missing browser session|refresh obeys server journey" --workers=1`
  — PASS, 2 tests.
- После исправления `crypto.randomUUID`: `npm run lint:js` — PASS;
  frontend suite — PASS, 14 tests; `npm run build:web` — PASS;
  `npx playwright test tests/browser/auth-r03.spec.mjs --grep "W02 does not present plan cards|successful password response reports a missing browser session|refresh obeys server journey" --workers=1`
  — PASS, 3 tests, включая HTTP-совместимый onboarding без `randomUUID`.
- Первый CI запуска `57e4a72` остановлен release gate: продукт изменён при версии
  `2.0.31`. По штатному `prepare_release.py` подготовлен patch `2.0.32`, frontend
  пересобран; повторный локальный минимум — PASS с теми же 14 frontend и 3 browser
  тестами. Публикация допускается только после успешного повторного CI.
- Вход нового участника — FAIL на опубликованной версии `2.0.31`, причина
  E10.2-LOGIN-01 локализована и исправлена в ветке.
- Полный клиентский путь и real LLM — BLOCKED до штатной публикации исправления.

## Непроверенное, риски и следующий шаг

Не проверены assessment, LLM, Results/Report, повторный вход и CI. Готовность не
заявляется. Следующий минимальный шаг — проверить регрессию, передать PR, дождаться
штатной публикации на test и продолжить путь тем же новым участником.
