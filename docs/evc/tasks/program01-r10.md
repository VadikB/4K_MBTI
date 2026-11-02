# PROGRAM01 R10: конечное состояние подключения программы

## Результат и область

Подключение опубликованной ProgramDefinition завершается по точному PUT и точному
GET readback той же организации. Фоновая загрузка анкет не удерживает операцию в
`loading`; null readback, ошибка и смена identity имеют конечный безопасный исход.

Не входят: R01–R09, изменение ProgramDefinition, прав, БД, назначения, методологии,
общий рефакторинг административного кабинета и публикация нового артефакта.

## Источники и границы

- Пакет аудита `P4K_PROGRAM01_AUDIT_2.0.47_2026-11-02.zip`, `START.txt`,
  `REPORT.txt`, `MANUAL_TEST_2026-11-02.txt`, `REMAINING_TASKS.txt`, R10.
- База: `main@0e18d31497736c54c5cc9517451fc8f9f7c4030a`, приложение `2.0.47`.
- Существующий контракт: `PUT/GET /users/admin/organizations/{id}/assessment-program`,
  scoped `operation_id`, immutable published ProgramDefinition.
- PM/предметная логика оценки не меняются; это UI/API orchestration административного
  подключения. Новые предметные значения и артефактные контуры не вводятся.
- Стоп-условий для узкого совместимого изменения нет. Реальные данные, приглашения,
  назначения и published definitions не изменяются.

## План и проверка

1. Отделить точный connection readback от общего списка и загрузки анкет.
2. Сохранить `operation_id` до подтверждённого исхода; после потерянного ответа
   проверять тот же результат точным GET.
3. Не показывать результат после смены identity; null/error завершать сообщением.
4. Проверить frontend-контракт, Browser-путь с настоящими обработчиками, общий
   frontend-набор, lint/build и `git diff --check`.

Откат: revert одного изменения frontend и пересборка `web/dist`; API и данные не
меняются.

## Фактический результат

- Найдена причина живого бесконечного `loading`: `connectAdminOrganizationProgram`
  отсутствовал в code-split entry `web/js/entries/admin-organizations.js`. Настоящий
  submit-обработчик получал `undefined`; изолированный source-function probe этого
  не воспроизводил.
- Экспорт восстановлен. Точный readback переведён на существующий
  `GET /users/admin/organizations/{id}/assessment-program` и больше не ждёт общий
  список/анкеты всех организаций.
- Карточка обновляется подтверждённым readback. Анкета выбранной организации
  обновляется отдельно в фоне без удержания исхода операции.
- При потерянном ответе PUT используется точный GET; scoped `operation_id`
  сохраняется до подтверждённого исхода. При смене identity результат не выводится.
- `readback=null` даёт терминальную ошибку; кнопка остаётся доступной.

## Проверки

- `node --check web/js/screens/admin/organizations.js` — PASS.
- `npm run lint:js` — PASS.
- `node --test tests/frontend/*.test.mjs` — 124 PASS, 0 FAIL.
- `npm run build:web` — PASS; `web/dist` пересобран.
- `npx playwright test tests/browser/auth-r03.spec.mjs --grep "PROGRAM01 R10" --workers=1`
  — 5 PASS, 0 FAIL: pending/error анкеты, null readback и повтор того же
  `operation_id`, потерянный PUT, повторное чтение карточки, смена identity.
- `npx playwright test tests/browser/auth-r03.spec.mjs --workers=1` — 79 PASS, 0 FAIL.
- `git diff --check` — PASS.
- Backend/HTTP/PostgreSQL — NOT_RUN: API и данные не менялись; изменён frontend
  orchestration поверх существующих PUT/GET контрактов.
- GitHub CI и live test — NOT_RUN до push/PR/deploy. Реальные организации,
  программы, анкеты и назначения не изменялись.
