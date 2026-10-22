# F22-01: изоляция запоздавшего ответа импорта

## Результат

Ответ CSV-импорта, запущенного администратором A, не изменяет состояние, DOM и статус после смены учётной записи на B.

## Область

- Включено: клиентский async-путь импорта участников, его success/error-статусы и регрессия.
- Не входит: изменение API, схемы данных, прав доступа, методологии, остальные F22.

## Контекст и источники

- Основание: `P4K_Full_Verification_2026-10-22.txt`, дефект F22-01; base `c19722629fdcbae009bc9c2810e3b1b921677b0c`, версия 2.0.13.
- Прочитано: `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`, Change 01 README, product context/Registry, ADR-002, Change 01 traceability, затронутый frontend-код и тесты.
- Применимость M1/M5: правила и пакеты не затронуты; runtime-готовность эта задача не меняет.
- Архитектурный адрес: UI/сессия администратора; владелец идентичности — `state.pendingUser` + `state.identityEpoch`.
- Пробелы/противоречия: нет. Отчёт — доказательство дефекта, а не новая предметная норма.
- Стоп-условия: все «нет»; решение владельца не требуется.

## Критерии приёмки

- [x] Перед импортом фиксируются `identityEpoch` и `pendingUser.id`.
- [x] Запоздавшие success/error-ответы не меняют `state.adminOrganizations`, DOM и статус новой сессии.
- [x] Дефект закрыт целевой регрессией; frontend-тесты, lint, build и `git diff --check` проходят.

## Проверка и откат

- Матрица: frontend JS — целевой Node-тест, полный frontend-набор, ESLint, web build; перед merge — CI `frontend` и `pytest`.
- Integration/HTTP и LLM не применимы: серверные контракты не меняются.
- Откат: revert отдельного PR; миграций и потери данных нет.

## Состояние

- Ветка: `codex/f22-01-late-import-isolation`.
- Завершено: guard для data/DOM/success/error; Node 67/67 PASS; Playwright `auth-r03` 46/46 PASS; pytest 485 PASS, 214 deselected; ESLint, build, `git diff --check` PASS.
- CI-диагностика: `pull_request`-запуск полностью PASS; параллельный `push`-запуск выявил флейк S10-B — произвольный тестовый ответ не соответствовал условию детерминированного gateway, хотя тест безусловно ожидал fixture-уточнение. Тестовый вход синхронизирован с версионированным fixture; runtime не изменён. Целевой S10-B на изолированной PostgreSQL test-БД — 1/1 PASS.
- Активный шаг: commit и push.
- Следующий шаг: PR, обязательный CI и решение владельца о merge.
