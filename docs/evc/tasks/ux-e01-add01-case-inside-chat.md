# UX-E01-ADD01 — ситуация как начало чата оценки

## Результат и границы

Текущая предъявленная версия ситуации отображается одним стартовым сообщением
«4К Ассистента» в общей истории. Отдельная колонка/список ситуаций отсутствует.
Case, AS, Turns, Evidence, таймеры, допуск, переходы и API не меняются.

## Источники и решения

- Основание: `UX-E01_ADD01_Case_Inside_Chat_2026-10-17.txt`, поручение владельца
  Дмитрия, Product Lead; дополнение заменяет только двухколоночную компоновку UX-E01.
- Base: `main@0376640ec432dde9ce069a81f65f4bfbeecef387`.
- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, EVC workflow/matrix,
  Product 4K context/Registry, Change 01, task manifest, действующий interview UI и тесты.
- Переиспользуется `current_situation.participant_payload`; новой записи Turn/event и
  LLM-пересказа нет. Показываются только разрешённые поля presenter-а, без JSON fallback.
- Стоп-условия: нет; публичный API, схема, предметная норма и данные не меняются.

## План и состояние

- Завершено: post-merge CI/deploy UX-UI01; новая ветка от актуального `main`; разведка.
- Завершено: единая история, безопасный presenter, прокрутка/reload и адресные тесты.
- Активный шаг: review, commit и PR.
- Далее: обязательный CI и визуальная приёмка на test.
- Ветка: `codex/ux-e01-add01-case-inside-chat`.

## Проверки

- `git diff --check`, `npm run lint:js`, frontend tests, `npm run build:web`.
- Browser: короткий/длинный payload, первая позиция истории, reload без дубля,
  авторы/порядок, неизвестный payload без JSON, 320–430 px без overflow.
- Физическая браузерная матрица — NOT_RUN, если среды недоступны.

## Риски и откат

Риск ограничен компоновкой и прокруткой interview UI. Откат — revert squash-коммита;
миграций, изменения конфигурации и данных нет.

## Фактические проверки

- `git diff --check` — PASS.
- `npm run lint:js` — PASS.
- `node --test tests/frontend/*.test.mjs` — PASS, 53/53.
- `npm run build:web` — PASS; committed `web/dist` обновлён.
- `npx playwright test tests/browser/auth-r03.spec.mjs --grep "E01 renders accepted active assessment"`
  — PASS, 1/1: единственное стартовое сообщение, отсутствие sidebar, начало истории,
  автор персонажа, reload/draft и мобильный viewport 375 px.
- Полный локальный browser suite с БД — NOT_RUN: локальный PostgreSQL не содержит
  изолированной роли `pytest`; обязательный полный набор выполняется в CI.
- Физические iOS/Android/Windows/macOS браузеры — NOT_RUN: среды недоступны.
