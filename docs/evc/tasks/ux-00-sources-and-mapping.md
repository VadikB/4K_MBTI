# UX-00 — источники и карта соответствия входа/знакомства

Дата аудита: 06.10.2026. Итог: **готово частично**. Аудит выполнен только чтением
кода и источников; приложение, БД, конфигурация, нормативные файлы и среда 10.8 не
изменялись. Браузерная приёмка не выполнялась и из чтения кода не выводится.

## Результат и область

Подтверждена техническая основа для самостоятельной реализации экранов ввода email,
ожидания письма, установки/ввода/восстановления пароля, выхода и базового
восстановления серверной сессии. Составлена карта существующих UI/API, доступа,
организационного контекста и знакомства. Обнаружены три блокирующих расхождения для
сквозного пути: доменный допуск вместо точного предварительного списка, отсутствие
product API canonical M4 и отсутствие доказанной защиты новой сессии от запоздалого
401 старой вкладки.

Включено: регистрация допущенного email, подтверждение email, парольный вход,
восстановление, выход/смена аккаунта, 401, организационный допуск, переход к
знакомству, legacy и canonical M4, версии профиля и snapshot Cycle.

Не входит: UX-01/UX-02, изменение приложения/БД/API/методологии, браузерный запуск,
тестовая почта, реальные LLM, поддержка, B2C, таймеры, кейсы, результаты, публикация,
push/PR/merge/deploy и изменение среды 10.8.

## Git и идентичность источника

- Фактически прочитан полный SHA:
  `8654b97ed6605d560111c37cd291f98f82c41457`.
- Worktree находится в detached HEAD: `git branch --show-current` вернул пустую
  строку, `git rev-parse --abbrev-ref HEAD` — `HEAD`. Предоставленное владельцем
  описание исходной ветки — `main`, но аудит не выдаёт detached checkout за ветку.
- Ожидаемый архивом сокращённый SHA `15f41a2` отличается. Откат/переключение не
  выполнялись. Исторический S7 `14cf514e...` также не является текущей базой.
- До создания этого документа `git status --short` и `git diff --stat` были пусты.
  Посторонних untracked-файлов с суффиксом ` 2` в данном worktree не обнаружено и
  они не затрагивались.
- ZIP: `/Users/vadim_bogachev/Downloads/Product_4K_Architect_Package_2026-10-06.zip`,
  SHA-256 `8ed7c9fdfef4fc678454acf85aaef192448909c4e9ef886c60e9a09cbde25152` — PASS.
- Внутренний `MANIFEST.json`: SHA-256
  `ce4b9dc5f48beadc3afcd84bc1b7e4ff7530c420ff4f14fc715f2562969dc333`;
  все 25 перечисленных файлов сверены по исходным байтам, failures=0.

## Прочитанные источники и статусы

Репозиторий, SHA выше:

- `AGENTS.md`, `README.md`, `CONTRIBUTING.md` полностью;
- `docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`,
  `task-template.md`, `review-checklist.md`;
- `docs/architecture/product-4k/1.0/context.md`, `registry.md`,
  `m1/v1.4/README.md` (M1 v1.4 FROZEN / CURRENT=NO);
- Change 01 `1.0/updates/2026-10-01/README.md`, task SourceSet
  `docs/methodology/source-sets/2026-10-01/manifest.json`, ADR-002 и
  `docs/evc/change01-traceability.md`;
- применимый код `Api/auth_service.py`, `Api/org_access.py`, `Api/routes.py`,
  `Api/assessment_contexts.py`, `Api/assessment_service.py`, `web/index.html`,
  `web/js/{api,main,router,session,state,wiring}.js`, экраны onboarding/profile/
  dashboard/prechat, auth CSS/tokens и относящиеся тесты.

Архив v1.2/v1.1:

- `00_README_Architect.txt`, полное TXT ТЗ
  `Product_4K_UX_UI_TZ_v1_2_2026-10-06.txt`, `00_Common_Instructions.txt`,
  `UX-00_Sources_and_Mapping.txt`, объединённая постановка UX-00–UX-02;
- `Design_Source_Map.txt`, `READ_FIRST_References_Status.txt`,
  `READ_FIRST_Methodology.txt`, `M6_M8_UX_Clarifications_2026-10-06.txt`,
  `M0.GOVERNANCE_v1.0_FROZEN.md`, `MANIFEST.json`, `QA_Summary.txt`;
- визуальные PDF учтены как визуальные источники и проверены manifest, но
  браузерным доказательством и web-ассетами не являются.

Статусы не смешиваются: ТЗ v1.2 и задачи v1.1 — продуктовая постановка; M0/M4/M7
в ZIP — копии для сверки и не переключают CURRENT; M0 из ZIP отсутствует в task
SourceSet репозитория и не зарегистрирован этим аудитом; Change 01 — WORKING;
canonical M4 package существует, но его наличие не доказывает product runtime.
M4 и M7 в ZIP побайтово совпадают с SHA task SourceSet
(`07875e...` и `50a0d5...`).

## Реестр требований и заменённых правил

| ID | Действующее требование UX-00 | Тип / влияние |
| --- | --- | --- |
| П-01 | 60 минут — общий бюджет всех Sessions одного Cycle; Additional Session использует остаток | Норма/продуктовая фиксация; не меняется в UX-00 |
| П-02 | M7 сейчас исключает блокирующее AI-ожидание; целевой учёт требует новой версии нормы/контрактов | Открыто у методолога, продуктолога и архитектора; auth не блокирует |
| П-03 | Предварительное знакомство и инструкция после старта — разные участки | Требует отдельного события; не вычитать время скрыто |
| П-04 | Порог отсутствия 3 минуты принят, но событие/вкладки/версия материала открыты | Вне первого блока |
| П-05 | Неизменный повтор не создаёт профиль; изменение версионируется; начатый Cycle хранит snapshot | Backend-механизмы частично есть; product path не подтверждён |
| П-06 | `processing` и подтверждённый `failed` различимы; refresh не запускает повтор | Вне UX-00/02 |
| П-07 | Обязательны reset, истёкшая/использованная ссылка, bad password, недопуск, повтор, account switch, late-401 | Контракты частично есть; late-401 — подтверждённый gap |
| П-08 | Поддержка, B2C и регистрация вне списка — этап 2; вход парольный | Не добавлять фиктивную заявку/поддержку |

Ранние правила «OTP», саморегистрация вне списка, обязательные три ответа,
закрытые пять ролей, ровно шесть кейсов, лимит на кейс, старые проценты/MBTI и
60 минут на Session заменены ТЗ v1.2. В код/нормативные артефакты это аудитом не
переносилось.

## Фактический auth-контракт на текущем SHA

Префикс маршрутов — `/users`.

| Операция | API и код | Доступ / различимость |
| --- | --- | --- |
| Определить режим | `POST /users/auth/email/request-link`; `routes.py:2808`, `AuthService.get_password_auth_mode` | Гость; 403 для недопуска, 400 для иных ошибок; `password`, `password_registration`, `verification_pending` |
| Подтвердить email | `POST /users/auth/email/confirm`; `routes.py:2919` | Гость с action token; invalid/used и expired различаются сообщениями, оба HTTP 400 |
| Задать пароль | `POST /users/auth/email/password-register`; `routes.py:2898` | Проверяет допуск и verification token; HTTP 403/400 |
| Войти | `POST /users/auth/email/password-login`; `routes.py:2982` | Недопуск 403; неверный/не заданный пароль 401 с разными `detail` |
| Запросить reset | `POST /users/auth/password/forgot`; `routes.py:2936` | Нейтральный ответ намеренно не раскрывает наличие аккаунта/допуска |
| Проверить reset | `POST /users/auth/password/reset/validate`; `routes.py:2960` | Invalid/used и expired различимы текстом при HTTP 400 |
| Изменить пароль | `POST /users/auth/password/reset`; `routes.py:2969` | Token одноразовый; после reset текущие сессии отзываются в auth service |
| Dev magic link | `POST /users/auth/email/verify`; `routes.py:3001` | Только существующий dev/magic-link режим, не целевой OTP UX |
| Восстановить сессию | `GET /users/session/restore`; `routes.py:3052` | Cookie session; возвращает user/dashboard/admin projection |
| Текущий этап | `GET /users/{user_id}/journey-state`; `routes.py:3165` | Авторизованный пользователь; серверный state |
| Выход | `POST /users/session/logout`; `routes.py:6036` | Удаляет серверную сессию и cookie |

UI сосредоточен в одном `#auth-panel` (`web/index.html:56`) с формами
`#auth-email-form`, `#auth-token-form` и состоянием `#auth-email-sent`.
Оркестрация — `web/js/wiring.js:484–751`; обработка query
`auth_action=email_verification|password_reset` — `web/js/main.js:111–145`.
Ошибки сервера выводятся как `detail`; отдельной типизированной модели error code
нет, поэтому UI может безопасно различать только HTTP status и текущий русский текст.
Стабильную продуктовую семантику на разборе текста строить нельзя.

## Карта экранов, состояний, API и доказательств

| Пользовательская цель / состояние | Действие → следующий экран | Данные / API | Доступ и подтверждение | Готовность / изменение |
| --- | --- | --- | --- | --- |
| Гость вводит email | submit → пароль либо ожидание письма | email; `request-link` | Серверный допуск | Готово для UX-02 |
| Email отправляется / сеть потеряна | pending → ответ или ошибка | fetch в `wiring.js` | Нет отдельного retry state; повтор формы | UI-компонент готовить; browser NOT_RUN |
| Ожидание подтверждения | resend/change email | `verification_pending`, TTL | resend backend rate limit 429 | Готово на существующем контракте |
| Ссылка обрабатывается | query token → установка пароля | `email/confirm` | Token purpose/email/access | Готово; не называть сам входом |
| Invalid/used/expired | ошибка → новый запрос | HTTP 400 `detail` | expired отличается от invalid/used; used и invalid объединены | Частично готово; тексты не должны обещать более точную причину |
| Пароль создан / вход выполнен | submit → dashboard/chat/admin | register/login + cookie | Сервер выбирает роль и bootstrap | Готово, но дальнейший corporate path зависит от gaps |
| Неверный пароль | ошибка → повтор/reset | login 401 | `recoverUnauthorized:false`, поэтому login-401 не logout | Готово |
| Нет допуска | ошибка → другой email/вход | 403 | Серверное решение | UI готово; политика доступа не соответствует точному списку |
| Reset запрошен | нейтральное сообщение → письмо | forgot | Anti-enumeration | Готово |
| Новый пароль | validate → reset → login | reset endpoints | Token consumed, sessions revoked | Готово; browser NOT_RUN |
| Повторный вход | restore → server journey | restore/journey-state | Cookie и owner checks | Частично; несколько назначений не исследованы как готовый UX |
| Выход/смена аккаунта | logout → auth | `session.js:133–156` | Server delete + local clear | Базовый выход готов; late-401 gap |
| Знакомство legacy | onboarding → agent/profile/dashboard | `/onboarding`, `/agent/message`, `/agent/profile/confirm` | Пользовательская сессия | Существует, но не является canonical M4 |
| Canonical M4: draft/confirm/profile | отсутствующий product flow | функции `assessment_contexts.py` | Только прямые сервисы и admin M5 migration | Блокировано отдельной backend/API задачей |
| Явный старт | prechat → assessment | существующие preparation/start API | Серверная сессия | Вне UX-02; snapshot связи ниже |

## Допуск и организационный контекст

`AuthService._ensure_email_can_authenticate` вызывает
`email_has_organization_access`. Проверка разрешает: superadmin; configured org
admin; существующий membership по email; **любой email настроенного активного
домена** (`Api/org_access.py:177–223`). После auth
`assign_user_organization_from_email` автоматически создаёт membership по домену
(`org_access.py:139–175`). Следовательно, фактический контракт не реализует
требование UX1.3 «только заранее внесённый точный email» и может допустить нового
человека домена без предварительной записи.

Организационный контекст после входа сохраняется membership и возвращается в
dashboard/read models; email action token привязан к нормализованному email.
Приглашение с отдельной organization identity в action token не найдено: выбор
организации следует из существующего membership/admin mapping/domain. Прямой
переход к `journey-state` и последующим owner endpoints проверяет текущую cookie
session; local screen не является основанием доступа.

## Late-401 и смена аккаунта

`readApiResponse` (`web/js/api.js`) при любом protected 401 запускает глобальный
`resetStaleUserState`; `unauthorizedRecovery` только объединяет одновременно
пришедшие 401. Поколение/идентичность сессии или проверка, что ответ относится к
текущему аккаунту, отсутствует. После входа B запоздалый 401 запроса аккаунта A
может вызвать logout/reset аккаунта B. Найденные frontend-тесты проверяют только:
login 401 без recovery, protected 401 с recovery и дедупликацию concurrent 401.
Регрессия именно late-401 после account switch не найдена. Поэтому утверждение S11
на текущем SHA не подтверждено и должно считаться gap, а не сохранённой гарантией.

Базовая смена аккаунта через реальные кнопки «Выйти» существует; предыдущий
browser-отчёт task10-3 подтверждает выход и скрытие чужого UI на другом commit,
но не late-401 и не является новым прогоном данного SHA.

## Canonical M4, версии и snapshot

Canonical M4 реализован в `Api/assessment_contexts.py`:

- `create_user_context_draft` всегда получает следующий `version`;
- `confirm_user_context` фиксирует конкретную версию пользователя;
- `create_personalized_profile` принимает опубликованный OrganizationContext,
  RoleProfile и confirmed UserContext, проверяет checksum и сохраняет immutable
  content/provenance;
- уникальность `(user_id, assessment_configuration_id, checksum)` через
  `ON CONFLICT` переиспользует неизменный профиль, то есть повтор без изменения не
  создаёт новый logical профиль.

Однако product routes для draft/confirm/create не найдены. Единственная видимая
точка переноса — superadmin M5 lab `POST /users/admin/m5-lab/migrate-current-profile`.
Пользовательский `/users/agent/profile/confirm` относится к legacy
`user_role_profiles` и не доказывает canonical M4. Поэтому следующий блок
знакомства нельзя подключить без отдельного backend-контракта и проверки прав.

Новый Cycle/AS путь сохраняет ссылку на `personalized_profile_id`, content/checksum
и execution snapshots; M7 planner также принимает конкретный profile id. Это
техническая основа запрета подмены начатого Cycle. Сквозная связь обычного
пользовательского подтверждения → canonical profile → Cycle на этом SHA не
существует как подтверждённый product flow. Legacy `assessment_service` имеет
собственный execution snapshot, но не должен выдаваться за тот же контракт.

## Подтверждённые gaps и владельцы

| Gap | Влияние | Владелец решения / следующий контур |
| --- | --- | --- |
| G-UX00-01 домен автоматически даёт доступ и membership | Нарушает точный предварительный список и отрицательный A02 | Продуктолог подтверждает политику; архитектор — отдельная backend/auth задача и совместимость существующих domain users |
| G-UX00-02 нет product API canonical M4 | Нельзя реализовать следующий блок знакомства без выдуманного контракта | Методолог/владелец M4 — смысл; архитектор — API, права, idempotency и тесты |
| G-UX00-03 late-401 не защищён поколением сессии | Старая вкладка может сбросить новый аккаунт | Архитектор; отдельная frontend/auth задача с регрессией account switch |
| G-UX00-04 error model основана на `detail` | Тексты нельзя стабильно связать с причинами | Архитектор выбирает совместимый typed error contract; продуктолог утверждает тексты |
| G-UX00-05 action token не несёт organization/invitation ref | При нескольких membership/доменах контекст приглашения неоднозначен | Архитектор + продуктолог; адресно до corporate invitation UX |
| G-UX00-06 Onest и актуальный logo web asset не найдены | UX-01 не может заявить точное соответствие PDF | Катя предоставляет лицензионные web-font/logo assets; продуктолог принимает fallback |
| G-UX00-07 browser/email flow на текущем SHA не запущен | Нет доказательства доставляемости и переходов | UX-02 на отдельной локальной среде/test mail; не среда 10.8 |

## Адресный план UX-01

Предполагаемые файлы: `web/styles/tokens.css`, `base.css`, `components.css`,
`screens/auth.css`, при необходимости отдельные общие компоненты; `web/index.html`
только для структуры/доступности; web assets — только после предоставления Onest и
логотипа. Не менять API, JS auth orchestration, backend, DB и методологию.

Проверки: `git diff --check`, локальные ссылки/ассеты, keyboard/focus/reduced motion,
mobile/desktop визуальная проверка по актуальным страницам PDF, `npm run build:web`
только если затронут entry/bundle. PDF — reference, не web-asset. При отсутствии
Onest не подменять его случайным шрифтом и не заявлять pixel match.

## Адресный план UX-02

Предполагаемые файлы: auth-section в `web/index.html`, `web/styles/screens/auth.css`,
`web/js/wiring.js`, при необходимости `router.js`, `main.js`, `session.js`, `api.js`,
`dom.js`; после JS — обязательный `web/dist`. Сохранить один auth-клиент и текущие
cookie/session semantics. Backend не менять в UX-02: G-UX00-01/02/03/04 выносить
отдельными задачами, если без них критерий экрана недостижим.

Минимальная проверка: `git diff --check`, `npm run lint:js`,
`node --test tests/frontend/*.test.mjs`, `npm run build:web`; адресные backend unit/
HTTP auth tests; browser flow на изолированной среде: register → email confirm →
password login → reset, expired/used link, bad password, denial, repeat login,
logout/account switch, network loss. Late-401 не помечать PASS без специальной
регрессии, воспроизводящей вход B до завершения старого запроса A. Не использовать
production/developer DB и не менять 10.8.

## Стоп-условия

1. Смысл/кардинальность предметной сущности меняется — **нет** в UX-00; изменений нет.
2. Публичный контракт/PM/данные меняются без допуска — **нет** в аудите; для
   G-UX00-01/02 это **да** и зависимая реализация остановлена.
3. Миграция/удаление данных — **нет**.
4. Нет источника/есть противоречие — **да адресно**: точный список против доменного
   допуска; UX-02 может рисовать denial, но не исправлять политику молча.
5. Нужен новый формат артефакта — **нет**.
6. Меняются права/чувствительные данные — **нет** в аудите; будущий fix допуска
   требует отдельного review.
7. Нет безопасного отката — **нет** для документа; `git revert` локального коммита
   либо удаление единственного файла.
8. Действие вне области — **нет**; UX-01/UX-02 не запускались.

## Проверки

| Команда / проверка | Результат |
| --- | --- |
| `shasum -a 256 ...zip` | PASS, ожидаемый SHA совпал |
| Сверка 25 entries внутреннего manifest | PASS, failures=0 |
| `git rev-parse HEAD`, branch/status/diff | PASS; exact SHA, detached HEAD, исходный diff пуст |
| Статический поиск маршрутов, UI, auth, org access, M4 и тестов | PASS как code-reading evidence |
| `node --test tests/frontend/api-unauthorized.test.mjs` | PASS, exit 0: 3 tests, 0 fail; предупреждение Node о package type не влияет на результат |
| `.venv/bin/python -m pytest tests/unit/test_auth_policy.py tests/unit/test_m4_personalized_profile.py` | NOT_RUN: `.venv/bin/python` отсутствует (exit 127); fallback `python3 -m pytest ...` также не выполнен — модуль pytest отсутствует (exit 1) |
| `git diff --check` | PASS, exit 0 |
| Browser, test email, HTTP/integration, внешний provider/LLM | NOT_RUN: UX-00 read-only, отдельная среда не поднималась |
| GitHub CI / PR / deploy | NOT_RUN и запрещены границами задачи |

Статический PASS означает лишь наличие/поведение прочитанного кода. Он не является
browser PASS, доставкой email, проверкой развёрнутой среды или методологической
приёмкой.

## Риски и откат

- Конфиг: не менялся; фактический допуск зависит от configured domains/admin emails.
- Схема/данные: не менялись; доменная auto-membership — наблюдаемое существующее
  поведение, не исправленное аудитом.
- Деплой: отсутствует.
- Безопасность: секреты/production/test PII не читались; в отчёте только контракты.
- Откат: удалить/ревертировать только этот Markdown. Runtime откат не нужен.

## Передача состояния и следующий минимальный шаг

Независимо готовы к UX-01/UX-02: ввод email, ожидание/повтор письма, обработка
verification/reset link, установка пароля, password login, bad password,
нейтральный forgot-password, базовый logout и сетевые/error visual states на
существующих контрактах.

Не готовы без отдельных решений/работ: точный corporate allow-list; canonical M4
знакомство/подтверждение; гарантия late-401 при account switch; устойчивые typed
auth errors; точная organization invitation; Onest/logo assets.

Следующий минимальный шаг после человеческого принятия UX-00 — UX-01 в отдельной
локальной ветке/коммите, не UX-02 и не backend. Параллельно архитектору нужно
оформить отдельные адресные задачи G-UX00-01 и G-UX00-03; знакомство canonical M4 —
отдельный следующий блок с решением владельца M4.

Открытые адресные вопросы:

1. Продуктологу: доменный допуск должен быть полностью отключён для participant
   auth этапа 1 или сохранён только для уже созданных memberships/admins?
2. Архитектору: какой совместимый session-generation/request-epoch контракт
   блокирует 401 запроса A после успешного входа B?
3. Методологу/владельцу M4 и архитектору: какой product API публикует существующие
   draft/confirm/create операции без дублирования canonical M4?
4. Кате: где находятся утверждённые web-файлы Onest и логотипа и каковы права их
   включения в репозиторий?
