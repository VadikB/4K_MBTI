# UX-W02-ADD02 / ADD03 — источник анкеты и финальные переходы

## Результат

Единый входной контракт анкеты заказчика с обязательным CSV-адаптером,
предпросмотром и авторизованным подтверждением; W02 использует опубликованную
редакцию источника. Участнику показываются утверждённые тексты и фактические
параметры плана. Завершение промежуточной ситуации не закрывает весь Cycle.

## Источники и версии

- `AGENTS.md`, `README.md`, `CONTRIBUTING.md`.
- `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`.
- `docs/architecture/product-4k/1.0/updates/2026-10-01/README.md`.
- `docs/methodology/source-sets/2026-10-01/manifest.json`.
- `docs/adr/002-cycle-as-dialogue-contracts.md`.
- `docs/evc/change01-traceability.md`.
- `UX-W02-ADD02_Questionnaire_Input_2026-10-16.txt`, редакция 1.0.
- `UX-W02-ADD03_Final_Copy_and_Transitions_2026-10-16.txt`, редакция 1.0.
- База: `origin/main@d4a886fb40485022f7be355d15722f70408705c1`.

## Границы

- В объёме: организация, corporate template `0.1`, CSV UTF-8/BOM с `,`/`;`,
  единый нормализатор для `product_form`, `external_form`, `csv`, immutable
  revisions, preview/confirm, происхождение, шаблон/пример, admin UI, W02 copy,
  промежуточный межситуационный переход и регрессии.
- Вне объёма: подключение конкретного внешнего провайдера форм, полный мастер
  кабинета, произвольные TXT/PDF/DOCX, новая модель прав, студенческий runtime,
  Stage 2 и дополнительные пять минут, содержательная/визуальная приёмка владельца.
- Опубликованные контексты и начатые Cycle не изменяются; подтверждение создаёт
  новую редакцию.

## Проверки

- Python compile и unit для CSV/нормализации.
- HTTP + PostgreSQL: права, preview/confirm, idempotency, provenance, readiness.
- Frontend tests и `npm run build:web`.
- Многошаговый Cycle: close AS → server-side break → explicit next; последний
  case → completion. Browser acceptance на доступном Chromium; реальные Safari,
  Chrome/Яндекс на iOS/Android/Windows/macOS — `NOT_RUN`, отдельная приёмка.
- Обязательный GitHub CI до merge.

## Фактический результат локальной проверки

- `py_compile` изменённых Python-модулей — PASS.
- `tests/unit/test_questionnaire_sources.py` и затронутые M5/M7 unit — `9 passed`.
- `tests/frontend/*.test.mjs` — `22 passed`.
- PostgreSQL 16, изолированная `agent4k_pytest`: clean bootstrap/drift,
  questionnaire preview/confirm и двухпозиционный inter-case flow — `5 passed`.
- `npm run build:web` — PASS; версия кандидата `2.1.36`.
- Полный `npm run test:backend` — `421 passed`, `13 failed`: несвязанные M6
  проверки frozen provider contract/operation identity; изменённые пути ими не
  затронуты. Окончательный gate — GitHub CI.
- Реальные Safari, Chrome/Яндекс на iOS/Android/Windows/macOS — `NOT_RUN`;
  это остаётся частью независимой визуальной приёмки после `main`.

## Ограничения

- `product_form` и `external_form` используют общий принимающий контракт, но
  конкретный внешний провайдер и отдельный полноэкранный мастер не подключены.
- Университетский шаблон и runtime не объявляются готовыми; corporate CSV `0.1`
  является доказанным положительным путём этой задачи.
- Stage 2 и дополнительные пять минут не входят в результат.

## Откат

Squash-revert PR. Новые source revisions сохраняются для аудита; отключение UI и
маршрутов не удаляет опубликованные OrganizationContext или историю Cycle.
