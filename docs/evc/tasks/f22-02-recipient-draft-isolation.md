# F22-02 — изоляция черновика получателей анкеты

## Основание и результат

Основание — F22-02 P1 из `P4K_Full_Verification_2026-10-22.txt`: выбор получателей
в предпросмотре анкеты сохранялся под косвенным ключом `unknown:organization` и мог
переноситься между разными назначениями одной организации.

Результат: черновик получателей предпросмотра адресуется явным контекстом
`user → organization → assignment_ref → questionnaire_revision_id`. Черновики форм
и выбор участников сохраняют существующие области.

## Прочитанные источники и границы

- `README.md`, `CONTRIBUTING.md`;
- `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`;
- `docs/architecture/product-4k/1.0/updates/2026-10-01/README.md`;
- `docs/methodology/source-sets/2026-10-01/manifest.json`;
- `web/js/screens/admin/organizations.js`, связанные frontend/browser-тесты.

Change 01 `1.0/01` имеет статус WORKING; M1 `1.4` — FROZEN, CURRENT=NO. Задача
не меняет предметную методологию, API, схему БД, права и опубликованные артефакты.

## Реализация и проверка

Предпросмотр получает явный `data-draft-action`, `data-assessment-ref` и
`data-questionnaire-revision-id`; capture/restore используют эти значения в ключе.
Регрессия проверяет различие ключей для другого пользователя, назначения и редакции,
а также наличие всех частей контракта в runtime-источнике.

Локальный минимум выполнен: адресная frontend-регрессия — 1 PASS; полный
frontend-набор — 67 PASS; `npm run lint:js` — PASS; `npm run build:web` — PASS;
`git diff --check` — PASS. Browser/live-сценарий не запускался локально; перед
слиянием обязательны зелёные CI jobs `frontend` и `pytest` для актуального head.

## Риски и откат

Риск ограничен потерей ранее сохранённого только в памяти вкладки выбора после
смены редакции; это ожидаемая изоляция. Откат — revert PR; миграция не требуется.
