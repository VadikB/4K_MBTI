# PROGRAM01 R05 — карточка, история и разрешённые действия

## Основание и границы

- Audit package `P4K_PROGRAM01_AUDIT_2.0.47_2026-11-02.zip`, `REMAINING_TASKS.txt`, R05 / D05.
- Base: `main@d5d13c379238eb7543deed43cec8a912467eea79`.
- Ветка: `codex/program01-r05`.
- Источники: Change 01 WORKING, M1 v1.4 FROZEN/CURRENT=NO, M8 v1.2 FROZEN;
  `docs/adr/002-cycle-as-dialogue-contracts.md`, `docs/evc/change01-traceability.md`.
- Не входят: R06–R09, новые права доступа, изменение M6–M8, редизайн кабинета,
  отправка писем и работа с реальными персональными данными.

## Проверяемый результат

1. Карточка участника показывает известные серверу состояния письма, ссылки,
   регистрации и историю точного назначения; неизвестные факты не угадываются.
2. В строке не более одного главного действия, соответствующего текущему этапу.
   Административный интерфейс не запускает и не продолжает оценку за участника.
3. Сброс пароля доступен только суперадмину и расположен в карточке участника.
4. Точный M8 Report открывается только получателем, зафиксированным контрактом
   `m8-report-access`; отсутствие права означает отсутствие кнопки и HTTP 403.

## Решения разведки

- `report_ready` без `report_id` недостаточен: фиктивная навигация запрещена.
- `audience=assessee` не является административным правом. Для администратора
  применяется только `m8_cycle_report_recipients` и существующий
  `customer_can_read_report`.
- Текущая `_build_admin_organizations` знает scope организаций, но не actor id.
  Для честной capability-проекции actor передаётся явно из endpoint, а право
  вычисляется сервером; frontend не выводит его из роли аккаунта.

## Проверки

- PASS — `python -m py_compile Api/org_access.py Api/routes.py Api/schemas.py`.
- PASS — `pytest tests/unit/test_admin_assessment_stage.py -q`: `5 passed`.
- PASS — адресный HTTP-набор административных организаций и M8: `17 passed`.
- PASS — Playwright: ADM-STATUS, раздельная отмена и PROGRAM01 R05: `3 passed`.
- PASS — `npm run lint:js`.
- PASS — `node --test tests/frontend/*.test.mjs`: `125 passed`.
- PASS — `npm run build:web`; `web/dist` пересобран из текущих исходников.
- PASS — полный backend-набор через общую project venv: `693 passed, 314 deselected`.
- PASS — PostgreSQL 16, одноразовый контейнер `4k-r05-pytest`, БД
  `r05_integration_pytest`; `pytest tests/integration/test_m8_report_access_db.py
  --run-integration -q`: `2 passed`. Контейнер остановлен и удалён через `--rm`.
- PASS — `git diff --check`.
- NOT_RUN — реальные LLM-вызовы: изменение их не затрагивает.
- NOT_RUN — CI для актуального head: выполняется после публикации Draft PR;
  локальные результаты CI не подменяют.

`npm run test:backend` в изолированном worktree не использован напрямую, потому
что в нём нет отдельной `.venv`; выполнена эквивалентная команда из общей venv.
Скриптов `npm run lint` и `npm run test:frontend` в проекте нет, использованы
существующие `lint:js` и прямой Node test runner.

## Изменённые контракты и трассировка

- `m8_cycle_report_recipients` → server-side capability точного Report →
  `_build_admin_organizations` / `_project_admin_assessment_stage` → unit,
  HTTP, PostgreSQL integration и browser regression.
- `organization_invitations` → даты создания/использования/отзыва в read model →
  карточка участника → browser regression.
- Существующий superadmin scope → capability сброса пароля → действие только
  внутри карточки. Endpoint сброса и его серверная авторизация не ослаблялись.
- Миграции, новые предметные defaults, prompts и runtime-артефакты отсутствуют.

## Review и риски

- Один actor id сохраняется в `AdminScope`, поэтому capability Report остаётся
  корректной и в GET, и в read model, возвращаемой после административной мутации.
- При отсутствии права, actor или точного `report_id` действие fail-closed:
  статус «Отчёт готов» виден, кнопка и идентификатор не выдаются.
- Основной остаточный риск — сочетания старых данных приглашений без timestamps;
  UI показывает явное «история неизвестна», а не вычисляет факт.
- Значимого изменения публичного API нет: response расширен nullable-полями.
- Откат не требует восстановления данных.

## Откат

Revert единственного PR R05. Миграций и изменения сохранённых runtime-данных нет.
