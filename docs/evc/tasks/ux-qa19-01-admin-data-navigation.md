# UX-QA19-01: навигация к данным организации

## Результат

Администратор и суперадминистратор могут внутри выбранной организации открыть
существующий раздел «Данные организации» и вернуться к участникам. Навигация не
требует `data-value`, сохраняет `data-organization-id` выбранной карточки и
показывает активный раздел через `aria-pressed` и существующие классы кнопок.

## Источники и решения

- Поручение `P4K_Admin_and_Bugfixes_2026-10-19_v2`, `COMMON.txt` rev 2.0 и
  `tasks/UX-QA19-01_Admin_Data_Navigation.txt` rev 2.0; SHA-256 всех файлов архива
  проверены по `SHA256SUMS.txt`.
- База: `origin/main@788e00dee4ad8358f2eda9d07feb192302cbe2a6`.
- Прочитаны `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, EVC workflow, verification
  matrix, artifact recipe, review checklist, Product 4K context/Registry и
  `docs/evc/tasks/ux-adm01-organization-data-readiness.md`.
- Организация, questionnaire/OrganizationContext, readiness, права и API не
  меняются. Исправляется только порядок адресной обработки UI-действий.

## Изменённые пути

- `web/js/wiring.js` — навигация обрабатывается до общего guard `data-value`;
  синхронизируются панели и доступное активное состояние.
- `web/js/screens/admin/organizations.js` — исходное состояние `aria-pressed`.
- `tests/browser/auth-r03.spec.mjs` — регрессия реального клика туда и обратно.
- `web/dist/` — штатно пересобранный frontend bundle.

## Проверки

- `npm run lint:js` — PASS.
- `node --test tests/frontend/*.test.mjs` — PASS, 61/61.
- `npm run build:web` — PASS.
- `npx playwright test tests/browser/auth-r03.spec.mjs --grep "ADM01 organization navigation"`
  — PASS, 1/1; synthetic organization `3`, без писем и рабочих данных.
- `git diff --check` — PASS.
- Обязательный GitHub CI, deploy-test и smoke опубликованного test — ожидают PR/merge.

## Непроверенное

- Физические Safari, Яндекс Браузер и мобильные устройства — NOT_RUN: нет
  соответствующих устройств в текущем контуре; критерий передаётся владельцу.
- Подтверждение анкеты на живом test — NOT_RUN до deploy; API/содержимое анкеты не менялись.

## Риски и откат

Миграций, новых прав, писем, LLM и изменений методологии нет. Риск ограничен
клиентским переключением панелей. Откат — revert этого PR и соответствующего bundle;
пользовательские данные, анкеты и snapshots не удаляются.
