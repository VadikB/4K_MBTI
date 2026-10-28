# UX-ADM28 — исправления кабинета администратора

## Контур и решение

- Пакет: `P4K_Admin_Fixes_2026-10-28.zip`, задачи UX-ADM28-01..03.
- База: `ca1d7dcccabc9187cad6f78d2e8844e67b7734e2`; ветка: `codex/ux-adm28-fixes`.
- Разрешения пакета: `branch_push`, `pr`, `version_bump`, `merge`, `deploy`; публикация методологических артефактов не разрешена.
- Границы: UI кабинета организации, публичная admin-проекция анкеты и обработка ошибок её загрузки. Права, схема БД, модель назначения, методология, таймеры и генерация кейсов не меняются.

## Прочитанные источники

- `README.md`, `CONTRIBUTING.md`;
- `docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`, `review-checklist.md`;
- `docs/architecture/product-4k/1.0/context.md`, `registry.md`;
- Change 01 (`docs/architecture/product-4k/1.0/updates/2026-10-01/README.md`) и manifest `2026-10-01`;
- `docs/adr/002-cycle-as-dialogue-contracts.md`, `docs/evc/change01-traceability.md`;
- `START_CODEX.txt`, README и карточки UX-ADM28-01..03 из входного пакета.

## Проверка и откат

- Регрессии: unit/frontend/browser и изолированная integration-БД по затронутым контрактам.
- Сборка frontend, `git diff --check`, ревью и обязательный CI до слияния.
- Визуальная матрица: 1440, 1280, 390, 320 px; недоступные устройства отмечаются `NOT_RUN`.
- Откат: revert единственного merge-коммита/PR и повторный deploy предыдущего неизменяемого commit SHA.

## Фактическая проверка

- `tests/unit/test_questionnaire_sources.py`: PASS, 11 тестов.
- `tests/integration/test_questionnaire_sources_db.py` на `f22_integration_pytest`: PASS, 1 тест.
- `tests/frontend/*.test.mjs`: PASS, 79 тестов.
- `tests/browser/auth-r03.spec.mjs`: PASS, 50 тестов; отдельная layout-матрица PASS на 320, 390, 1280 и 1440 px (также промежуточные ширины).
- `npm run build:web`: PASS; точечный ESLint изменённых JS-файлов и `git diff --check`: PASS.
- Полный ESLint репозитория: FAIL из-за 32 ранее существовавших `no-unused-vars` вне изменённых файлов; затронутые файлы проходят.
- Прототип v3 (`source_commit=26076fd…`) открыт через локальный HTTP; SHA-256 `dist/index.html` совпал с `PROTOTYPE_IDENTITY.json` (`fb47acf7…`).

## Стоп-условия

Новая миграция, изменение полномочий, методологии или опубликованного артефакта требуют отдельного решения владельца. На старте задачи эти условия не возникли.
