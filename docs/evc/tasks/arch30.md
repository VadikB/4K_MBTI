# ARCH30 — согласованная поставка 01–08

## Результат

Суперадминистратор подключает допущенную программу оценки через UI; контекст
организации сохраняется и подтверждается с первого прохода; членство, перенос и
удаление имеют явные безопасные правила; администратор возвращается в управление;
статусы понятны; разрешённый путь до первой ситуации проверен.

## Область

- Включено: ARCH30-01…08 редакции 1.1 от 30.10.2026.
- Не входит: реальные организации №3/№4, массовый purge/рассылки/LLM-матрица,
  новая методология, удаление модели выбора ролей, изменение frozen snapshots,
  общий рефакторинг и повтор UX-AUD29 как отдельного списка.

## Контекст и источники

- Основание: пакет `P4K_ARCH30_Architect_Package_2026-10-30_v1_1.zip`, все 64
  файла прошли `SHA256SUMS.txt`.
- Base: `e08c6f51acaf5a59b08b73cc98f05e9d03be0bd4`, `origin/main`, 30.10.2026.
- Прочитано: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, обязательные EVC,
  архитектурные и Change 01 источники; README/SOURCE_PRIORITY/FINDINGS/tasks/
  ACCEPTANCE пакета.
- Приоритет: решения владельца и контракты репозитория выше наблюдений и
  исторических прототипов. FINDINGS не доказывает live-причины №3/№4.
- M1 v1.4 — понятийный FROZEN / CURRENT=NO; опубликованные M1–M8 и snapshots
  неизменяемы. Предметные нормы этой задачей не добавляются.
- Архитектурная граница: подключение и назначение подготавливают AS/refs;
  подготовка, исполнение, фактический расчёт, интерпретация и представление не
  смешиваются (PM-03/04/05/06/07).

## Delta на старте

| Требование | Существующий механизм | Расхождение | Проверка |
| --- | --- | --- | --- |
| Подключение программы | pilot/source bindings, операторский script | нет продуктового UI | HTTP + DB + UI |
| Контекст организации | draft/preview/confirm/readiness | риск восстановления старого draft, legacy profile | unit + HTTP + browser |
| Членство | unique user membership | конфликт INSERT не соответствует индексу | integration + HTTP |
| Удаление | dependency plan + deletion ledger | нужен product UI и production activation | isolated DB + HTTP + UI |
| Перенос | единственная membership | нет явной атомарной product-операции | integration + HTTP |
| Навигация/logout | admin areas/session reset | неполный reset и блокировка управлением | frontend + browser |
| Статусы/UI | readiness и принятые компоненты | смешанные/технические состояния | frontend + screenshots |
| Сквозной путь | PATH29/ADM28/W02 тесты | требуется актуальный preflight/delta | HTTP + isolated browser |

## Стоп-условия и решения

- Решения владельца от 30.10.2026 зафиксированы в
  `docs/adr/003-arch30-program-and-deletion-lifecycle.md`: ProgramDefinition,
  полный purge и различие удаления/переноса согласованы.
- Любая несовместимая миграция, изменение публичного API/смысла ролей, расширение
  артефактного контура или реальное удаление требуют отдельного решения владельца.
- История организаций №3/№4 и live-причины: ожидается независимая диагностика;
  не блокирует изолированные доказанные исправления.
- ARCH30-01: предметный блокер снят; реализуется минимальный immutable
  ProgramDefinition и историческое подключение точных версий.
- ARCH30-04: предметный блокер снят. Независимый deletion ledger, обязательный
  replay tombstones после restore и product endpoints реализованы. Production
  работает fail-closed и требует provisioned `DELETION_LEDGER_PATH`.

## План и состояние

- Завершено: целостность пакета; свежий main; чтение обязательных источников;
  начальная delta-карта; ARCH30-03 — precheck до изменения профиля, сериализация
  по email, безопасный 409 без tenant leak, readback после UniqueViolation и
  классификация UI-ошибок реализованы; unit/HTTP/frontend/PostgreSQL race PASS;
  ARCH30-02 — legacy textarea удалена из обеих форм и больше не перезаписывается;
  ARCH30-06 — общий logout reset и browser re-login PASS; ARCH30-07 — основной
  этап участника отделён от технических подробностей; ARCH30-04 — bootstrap больше
  не реактивирует и не переименовывает существующую организацию.
- Завершено независимое ядро ARCH30-05: атомарный перенос с явными source/target/role,
  блокировкой последнего администратора, активного Cycle и незавершённого знакомства;
  старые назначения/приглашения отзываются, mutable acquaintance state и web-сессии
  очищаются. Для перенесённого `configured_admin` сохраняется suppression, поэтому
  bootstrap и проверка допуска не возвращают прежнее членство.
- После решения владельца завершены ProgramDefinition, API/UI подключения,
  release-команда, lifecycle, точный purge preview и изолированная проверка
  удаления организации/отдельного аккаунта, включая незавершённый Cycle,
  detached account и сохранность другой организации.
- Текущий шаг: локальная реализация и применимая матрица завершены; следующий
  внешний gate — человеческий review, commit/PR и exact-head CI только после
  отдельного разрешения владельца.
- Ветка: `codex/arch30`.

## Действия выпуска

- `branch_push=true`, `pr=true` (`#131`), `version_bump=true` (`2.0.39`),
  `merge=false`, `deploy=false`, `artifact_publish=false`.
- Флаги меняются только по действующему release-процессу после локальной проверки.

## Проверки

- Применяется объединение строк матрицы: JS behavior/UI, backend, DB,
  auth/snapshots/queues. Минимум: `git diff --check`, lint, frontend tests/build,
  backend unit/HTTP, isolated PostgreSQL integration и адресные browser tests.
- Реальные LLM не запускаются. Письма — только mail sink.
- Визуал: одинаковые viewport 1440/1280/390/320 и доказательства без ПДн.

Фактические адресные результаты ARCH30-03:

- `tests/unit/test_arch30_membership.py`: 7 PASS.
- `tests/e2e/test_arch30_membership_http.py`: 2 PASS.
- `tests/unit/test_arch30_organization_profile.py`: 1 PASS.
- `tests/frontend/arch30-membership-errors.test.mjs`: 1 PASS.
- Все `tests/frontend/arch30-*.test.mjs`: 8 PASS.
- Полный `tests/frontend/*.test.mjs`: 99 PASS.
- `tests/integration/test_arch30_membership_db.py --run-integration` на
  `f22_integration_pytest`: 1 PASS; конкурентный readback после advisory-lock.
- `npm run lint:js -- --quiet`: PASS; `py_compile`: PASS; `git diff --check`: PASS.
- Адресный Playwright logout/re-login: 1 PASS; `npm run build:web`: PASS до
  последующей правки ARCH30-07; финальная пересборка PASS.
- Полный `tests/browser/auth-r03.spec.mjs`: 71 PASS, включая viewport 320–1440
  и явный перенос legacy profile в пустой C01 draft.
- Полный HTTP/e2e: 84 PASS, 12 deselected.
- Backend без integration/e2e/llm: 668 PASS, 268 deselected.
- ARCH30/W02/PATH29 DB: 4 PASS; PATH29 disposable owned-stand: 1 PASS.
- `tests/unit/test_org_admission.py`: 9 PASS, включая запрет bootstrap-reactivation
  и возврата подавленного `configured_admin`.
- `tests/integration/test_arch30_transfer_db.py --run-integration`: 3 PASS;
  атомарный успешный перенос и неизменность данных при двух stop-конфликтах.
- Объединённый ARCH30 DB integration: 4 PASS. ARCH30 HTTP/e2e: 4 PASS.
- `tests/integration/test_arch30_program_definition_db.py`: 2 PASS на изолированной
  PostgreSQL БД; подключение/resolve/idempotency/immutable/retired.
- Финальный после ARCH30-05 `npm run build:web`: PASS; полный
  `tests/browser/auth-r03.spec.mjs`: 71 PASS; frontend 99 PASS; lint и
  `git diff --check`: PASS.
- После решений владельца и ProgramDefinition/purge-preview: backend 668 PASS
  (271 deselected), HTTP/e2e 98 PASS, frontend 100 PASS, browser 71 PASS,
  объединённый ARCH30 PostgreSQL integration 9 PASS; build, JS lint, py_compile
  и `git diff --check` PASS.
- Финальный полный browser discovery: 71 PASS; ещё 16 owned-backend сценариев
  классифицированы NOT_RUN из-за отсутствия обязательного явного
  `STAND_ADMIN_URL` (не продуктовые FAIL). Реальный stand/deploy не запускался.
- Purge-preview явно сохраняет текущий и заданные конфигурацией аккаунты; execute
  блокирует удаление организации, пока соответствующая конфигурация не изменена.
  UI показывает блокирующий аккаунт и причину до необратимого подтверждения.
  Отдельное удаление detached account доступно даже при нуле организаций.
- После этой граничной правки: purge backend unit 7 PASS, полный frontend
  102 PASS, финальная `build:web`, `py_compile` и `git diff --check` PASS.
- Ревизия execution path выявила и исправила попытку читать fingerprint до
  построения временного плана на новом соединении. Теперь порядок: построение
  плана → сверка fingerprint → durable intent callback → удаление → DB receipt.
  Stale preview не пишет intent. Purge integration 5 PASS; объединённый ARCH30
  PostgreSQL integration после исправления 11 PASS.
- Финальный стандартный backend после правки endpoint: 671 PASS / 273 deselected
  (`not integration and not e2e and not llm`), только Starlette deprecation warning.
- Финальный HTTP/e2e после той же правки: 86 PASS / 858 deselected; `npm run
  lint:js -- --quiet` PASS.
- Purge fixture включает незавершённый `m5_cycles.status='active'`, credentials,
  email-only action token, detached account и другую организацию. После удаления
  тот же email/код создаются заново без прежних credential/token/Cycle rows.
- External ledger restore-модель: 4 purge integration PASS, включая fail-closed
  startup при отсутствующем receipt и успешную reconciliation после replay.
- Первый адресный browser-запуск legacy migration дал FAIL, потому что после
  изменения source не был пересобран `web/dist`; после обязательной пересборки
  тот же неизменённый тест и полный browser suite PASS.

## Матрица приёмки ARCH30 v1.1

Окружение: локальный worktree `codex/arch30`, base/HEAD до коммита
`e08c6f51acaf5a59b08b73cc98f05e9d03be0bd4`; PostgreSQL
`f22_integration_pytest` на `127.0.0.1:55437`; browser fixture и disposable
owned stand; synthetic mail sink; реальные LLM/письма/удаления не запускались.

| ID | Результат | Доказательство / граница |
| --- | --- | --- |
| A01–A04 | PASS (local) | `assessment_program_definitions` + allowed exact role versions + connection history; published immutable, retired запрещает новые назначения, старые bindings не переписываются. API/UI суперадминистратора и release-команда; DB integration 2 PASS. Фактическая публикация девяти кейсов NOT_RUN (`artifact_publish=false`). |
| A05 | PASS | Browser `ADM19-01 saves early organization data…`; F22 first-save/readback tests; legacy runtime write удалён. |
| A06 | PASS | F22-01/02/03/04/06 и browser поздних ответов/смены аккаунта. |
| A07 | PASS | ADM28 confirm/readback/recipient browser-сценарии и HTTP readiness используют revision id. |
| A08 | PASS | ADM28 lost response/invalid JSON/retry tests; busy снимается, результат читается. |
| A09 | PASS (local) | Legacy textarea отсутствует; старый непустой `organizations.profile` показан read-only и переносится в пустой C01 только явным действием; browser regression. CSV validation остаётся общим preview route. |
| A10–A11 | PASS | Unit 7, HTTP membership/rbac, PostgreSQL race: advisory lock, savepoint/readback после UniqueViolation, tenant скрыт обычному админу, admin не понижается. |
| A12 | PARTIAL | Известные 401/offline/deadline/409/5xx разделены. Общего correlation-id контракта и безопасного журнала обращения в репозитории нет; не введён локально только для одной формы. |
| A13 | PASS (local) | Явные deactivate/restore endpoints и UI; bootstrap не реактивирует/не переименовывает; unit/HTTP. Restart/live-readback не запускался. |
| A14–A19 | PASS (local product path) | UI/API организации и отдельного detached account строят FK/email dependency plan и fingerprint, требуют повторную проверку и внешний intent. Изолированно удалены активный Cycle, credentials/tokens и detached account; другая организация/общий account сохранены; чистый re-add доказан. В runtime нет постоянных user files: exports memory/temp, очереди PostgreSQL. Production fail-closed без provisioned `DELETION_LEDGER_PATH`; restore требует replay. |
| A20 | PASS | Атомарный transfer, явная target access role, last-admin block, повтор после потерянного ответа идемпотентен; DB integration 3 PASS. |
| A21 | PASS (local) | История не перепривязывается; прежние assignments/invitations отзываются; acquaintance mutable state и web sessions очищаются. Реальная старая вкладка не запускалась. |
| A22 | PASS (local) | `prepared/active/paused/interrupted` закрываются штатным M7 `complete` с причиной `organization_transfer`; `collection_closed/calculation_pending` перенос не блокируют и остаются в старом контексте. Универсальный `cancelled` не введён. При physical purge Cycle удаляется без terminal status/расчёта/отчёта. |
| A23 | PASS (local) | ADM19/R03/W02/PATH29 browser matrix возвращает admin в management из доступных состояний. |
| A24 | PASS | Общий reset покрывает logout/exit/restart; logout→login browser regression. |
| A25 | PASS (local) | Серверная session generation/scope, stale response и account-change tests; URL не является источником прав. Live вкладка после transfer/purge не запускалась. |
| A26 | PASS | Один human stage + раскрываемые raw details; frontend и browser состояния. |
| A27 | PASS (technical), NOT_RUN (owner visual) | Browser 1440–320 и long-text geometry PASS; palette lint PASS. 200% zoom/screenshot parity и визуальное принятие владельцем/Катей не выполнялись. |
| A28 | PASS (local) | Readiness разделён на early/context/roles/preparation; действия маршрутизируются; существующие QA19/UX-FIX20 browser tests. |
| A29–A30 | PASS (fixture/owned stand) | W02/PATH29/M10, HTTP/backend/browser regression; preparation отделена от start/timer. |
| A31 | PARTIAL | ProgramDefinition и подключение готовы; реальный smoke ждёт технической публикации программы с существующим допущенным nine-case catalog. Synthetic fixture не объявлен продуктовым каталогом. |
| A32 | PASS (local) | R03 invitation tests используют разрешённый public base URL и server identity; mail sink, не реальное письмо. |
| A33 | PASS (regression), NOT_RUN (performance evidence) | Version/browser recovery tests PASS; отдельные cold/repeat timing traces не снимались, потому что доказанной новой задержки нет. |
| A34 | IN_PROGRESS | Ветка и PR #131 созданы; обязательный CI выполняется. Patch-кандидат `2.0.39` подготовлен после release guard. Merge/deploy/publish не выполнялись. |

## Изменения данных и совместимость

- Добавляется обратимо-совместимая таблица
  `configured_organization_membership_suppressions`; существующие memberships,
  assignments, contexts и frozen snapshots не переписываются.
- Добавляются `assessment_program_definitions`, allowed-role versions и история
  подключений. Опубликованная версия immutable; существующие pilot bindings
  остаются временным read-only compatibility path до явного переподключения.
- Transfer пишет suppression только для исходного `configured_admin`, меняет одну
  membership в транзакции, отзывает старые active assignment/invitation и web
  sessions. Исторические ответы/отчёты остаются в исходном scope.
- Автоматический backfill pilot bindings не выполнялся: точная ProgramDefinition
  подключается суперадминистратором после технической публикации.
- Специальный backup и 90-дневное хранение не вводились; реальные
  destructive DB/files/queue операции не запускались.

## Эксплуатационная граница

Предметные решения владельца получены. Независимый ledger, DB receipts,
fail-closed startup и replay-команда реализованы и проверены. В production нужен
provisioned путь вне backup БД с durability/access/monitoring/runbook. Без него
необратимые organization/account endpoints закрыты конфигурацией; отдельного
повторного продуктового согласования решений ADM30 не требуется.

## Откат

До первого purge приложение можно откатить revert продукта; новые таблицы оставить
инертными, чтобы не терять историю подключений и receipts. После первого purge
нельзя откатывать startup reconciliation или удалять внешний ledger: это может
вернуть данные из старого backup. Сначала восстановить совместимую версию replay,
сверить все intents/receipts и только затем менять приложение. Таблицы удалять лишь
отдельной согласованной миграцией после проверки зависимостей; исторические bindings,
assignments, snapshots и подтверждённые контексты не переписывать.

## Непроверенное и следующий gate

- NOT_RUN: реальный test deploy, production purge, публикация программы, реальные
  письма/LLM, owner visual и exact-head CI; локальные PASS их не заменяют.
- Browser discovery: 71 PASS, 16 owned-backend сценариев требуют явного
  `STAND_ADMIN_URL` и поэтому остались NOT_RUN.
- Открытых продуктовых вопросов по трём решениям ADM30 нет. Для продолжения выпуска
  требуется не новое продуктовое решение, а разрешение на commit/PR и затем CI.
