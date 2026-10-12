# UX R02 Состояния входа и персональные приглашения

## Результат

Рабочий блок авторизации соответствует принятому R01 и UX-R02: самостоятельная
регистрация и восстановление проходят через два последовательных ввода пароля,
повторный вход ведёт к актуальному разрешённому этапу, неизвестный email получает
отдельное состояние, а администратор организации может отправлять и отзывать
персональные приглашения со сроком 72 часа без доступа к чужому tenant.

## Область

- Включено: auth UI и маршруты, политика новых паролей, персональные приглашения,
  минимальные поля участника, tenant-права, совместимая схема данных, тесты и сборка.
- Не входит: автоматическое продолжение исходной вкладки, юридический подвал,
  номер релиза, проектирование блока знакомства, изменение методологии M1–M8,
  продуктовая браузерная приёмка R03 и развёртывание test/prod.

## Контекст

- Основание: запрос владельца «Запусти задание UX-R02» от 12.10.2026;
  `UX-R02_Login_States.docx`, редакция 8 от 12.10.2026.
- Значимые точки входа: `web/index.html`, `web/js/wiring.js`, `web/js/session.js`,
  `web/js/router.js`, `web/styles/screens/auth.css`, `Api/auth_service.py`,
  `Api/routes.py`, `Api/schemas.py`, `Api/database.py`, admin organizations UI.
- Архитектура/ADR: изменение относится к UI, auth/invitation application logic и
  infrastructure/data; не меняет предметные контракты оценки.
- Существующие тесты и контракты: `tests/frontend/auth-ux.test.mjs`,
  `tests/unit/test_auth_policy.py`, `tests/unit/test_organization_invitation.py`,
  `tests/e2e/test_email_admission_http.py`, browser runtime tests.
- Применимый комплект: Product 4K Change 01 WORKING и Registry прочитаны для
  границ; M1 v1.4 FROZEN/CURRENT=NO не является runtime-допуском и не затрагивается.
- Архитектурный адрес: auth UI → auth application service → auth/invitation data;
  assessment journey остаётся отдельным потребителем существующей read model.
- Прослеживаемость: UX-R02 §§6–52 → auth/invitation API и UI → перечисленные файлы
  → frontend/unit/HTTP/browser tests.
- Открытые решения: продуктовые параметры UX-R02 приняты Product Lead 12.10.2026;
  новых методологических решений задача не вводит.
- Предметные артефакты: отсутствуют; парольные правила являются принятой политикой
  auth-блока, не methodology/scenario/prompt-артефактом.
- Затронутые записи `docs/evc/artifact-debt-register.md`: нет.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
  `docs/evc/artifact-recipe.md`, `docs/evc/review-checklist.md`,
  `docs/architecture/product-4k/1.0/context.md`, Registry и Change 01 README;
  UX-R01/UX-R02 редакция 8, auth review и offline prototype commit
  `1bd546700515276450ce6f882bc31e2f4b29bb49` с SHA256SUMS.
- Не найдено / устарело / противоречит: browser/device R03 не выполнен; runtime
  email provider и production settings не проверены. Это ограничивает приёмку,
  но не блокирует реализацию и изолированные тесты.
- Для M1/M5: источники не меняются; задача не заявляет соответствие или новый
  runtime-комплект. M6–M8 и CURRENT не затрагиваются.
- Принятое решение: UX-R02 редакция 8 → Product Lead Дмитрий → 12.10.2026 →
  параметры и границы этого файла.
- Стоп-условия: противоречия источников, новый публичный продуктовый выбор,
  опасная миграция и недоступный обязательный артефакт — нет на старте.
- Требуется решение владельца: нет.

## План и состояние

- Завершено: разведка; backend/data персональных приглашений; парольная политика;
  auth UI и journey routing; frontend/unit/HTTP проверки; локальная визуальная
  проверка desktop и 320 CSS px.
- Активный шаг: итоговая сборка, review diff и оформление передачи.
- Следующий шаг и зависимости: PR/CI, миграционная проверка на изолированной
  PostgreSQL и R03 владельцем на обязательной browser/device матрице.
- Ветка / commit / связанные PR: `codex/ux-r02-login-states`, commit и PR пока нет.
- Передача в следующую сессию: обновлять этот раздел и итоговый отчёт по факту.

## Ограничения и риски

- Совместимость: старые пароли проверяются без новой клиентской фильтрации;
  общие organization invitations сохраняются отдельно.
- Данные и миграции: только добавочные таблицы/поля; prod/test применение отдельно.
- Безопасность и персональные данные: raw tokens, пароли и персональные данные не
  выводятся в списках и логах; tenant-проверки выполняются сервером.
- Внешние сервисы/LLM: LLM не используется; реальная почта локально не вызывается.
- Производительность и эксплуатация: повторная отправка идемпотентна в рамках
  операции, предыдущая активная персональная ссылка адресата отзывается.

## Критерии приёмки

- [x] Регистрация и reset используют два экрана, одно поле на шаг, без хранения
  пароля в browser storage и без POST до подтверждения.
- [x] Новая парольная политика одинакова на frontend/backend; login legacy-пароля
  сохраняет совместимость; генератор выдаёт ровно 10 допустимых символов.
- [x] Ошибки, loading, возврат, resend и недоступный email соответствуют UX-R02 и
  доступны через `aria-invalid`/`aria-describedby`.
- [x] Персональное приглашение одноразово, привязано к email/organization/purpose,
  живёт 72 часа, поддерживает resend/revoke и не раскрывает raw token.
- [x] Администратор организации управляет только своим tenant; минимальные поля
  участника — email, ФИО, должность; superadmin совместимость сохранена.
- [x] Первый вход ведёт к существующему знакомству, повторный — к актуальному journey;
  auth не запускает Assessment Session/Cycle.
- [x] Новое предметное содержание не встроено в исходный код или генератор пакета.
- [x] Проверены потребители контрактов и неизменность methodology snapshots.

## План проверки

- Применимые строки матрицы: JS/frontend, Python/backend, HTTP/API, schema/data,
  critical auth path; CI `frontend` и `pytest` обязателен до merge.
- Модульные тесты: auth policy, token lifecycle, tenant authorization.
- Интеграция/HTTP: изолированный pytest/test DB; HTTP fixtures без production данных.
- Ручная проверка/test-среда: R03 и обязательная browser/device матрица — NOT_RUN
  локально, выполняется командой продукта после загрузки SHA.
- Наблюдаемость: безопасные статусы отправки и диагностические ошибки без секретов.

## Откат

Revert одного PR возвращает прежние UI/API. Добавочные таблицы/поля можно оставить
неиспользуемыми; их физическое удаление требует отдельной согласованной миграции.

## Передача результата агентом

Результат: реализованы R01/R02 auth UI, два шага нового пароля, reset-состояния,
journey routing и персональные tenant-scoped приглашения на 72 часа.

Проверки:

- PASS `npm run lint:js`.
- PASS `npm run build:web`.
- PASS `node --test tests/frontend/*.test.mjs`: 11/11.
- PASS адресный pytest: 24/24.
- PASS `npm run test:backend:http`: 51/51.
- PARTIAL `npm run test:backend`: 384 PASS, 13 FAIL в несвязанных M6
  provider/material tests (`DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`,
  `INPUT_NOT_READY`); затронутые auth/org tests проходят.
- PASS локальный browser smoke начального экрана: desktop и 320 CSS px, без
  горизонтального overflow; static server не проверяет backend-сценарии.
- NOT_RUN PostgreSQL integration и startup schema: `TEST_DATABASE_URL` не настроен,
  локальное подключение к PostgreSQL недоступно.
- NOT_RUN R03 на реальных устройствах/браузерах и с контролируемой почтой: выполняет
  команда продукта после доступного SHA/стенда.

Откат: revert PR; добавочные колонки оставить неиспользуемыми. Следующий шаг:
изолированная миграционная проверка PostgreSQL, PR CI и продуктовая R03.
