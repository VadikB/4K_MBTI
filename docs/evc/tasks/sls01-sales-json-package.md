# SLS01 — JSON-native пакет Sales Case/AS

## Результат

Из 18 выбранных авторских JSON воспроизводимо собирается draft-пакет девяти
`CASE.SPEC.01–09` и Sales AS для `specialist_expert`, без XLSX и без допуска людям.

## Область

- Включено: schema v3 JSON source refs, snapshots/checksums, builder, общий verifier,
  совместимый DB import, mapping/preview, регрессии schema v2/v3.
- Не входит: runtime AS и персонажи SLS02, сценарный исполнитель SLS03, публикация,
  GC/методологическая подпись, реальный Cycle/LLM, HR и mini cases.

## Контекст

- Основание: `RUN_CODEX.txt` revision 2.1 и `P4K_Sales_01_Package.txt`, 19.10.2026.
- База: `origin/main` / `193768465f49870aabb3dcb3df8cd04eaa7b831d`.
- Архитектура: PM-03 готовит AS, PM-04 исполняет; M5 v1.1 FROZEN — понятийный
  источник, пакет Sales остаётся WORKING/TEST_DRAFT и runtime disabled.
- Контракты: `docs/architecture/m5-case-execution.md`,
  `docs/architecture/product-4k/m5-catalog-integrity-contract.md`, ADR-002 C-34.
- Прослеживаемость: author file/JSON Pointer/SHA-256 → CaseVersion schema v3 →
  `m5_packages`/`m5_case_*` → unit и изолированный DB integration test.

## Источники и решения

- Прочитано: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, EVC workflow/matrix/recipe,
  Change 01 README/manifest/traceability, Registry, M5 contracts, 34 файла комплекта.
- Целостность комплекта: PASS, 34/34 файлов. Выбор: 9 Case + 9 Sales AS; 55 target
  occurrences; Case 06 имеет отдельное происхождение, ровно как в manifest.
- Решение владельца: Sales, `specialist_expert`, без HR/mini; новый JSON builder;
  публикацию и человеческий допуск не объявлять.
- Стоп-условия: несовместимой миграции нет; schema v2 не переписывается. Открытые
  проекции персонажей и runtime rules переданы SLS02/SLS03 и блокируют admission.
- Требуется решение владельца: нет для SLS01; содержательная приёмка остаётся SLS06.

## План и состояние

- Завершено: разведка, checksum, schema v3, builder, пакет, verifier, import dispatch,
  unit regressions, документация.
- Завершено: локальный минимум backend; 458 PASS. Изолированная DB не настроена,
  поэтому targeted integration корректно SKIPPED/NOT_RUN.
- Активный шаг: commit/PR/CI и человеческое review SLS01.
- Следующий шаг: DB round-trip и SLS02 после отдельного PR/CI/приёмки SLS01.
- Ветка: `codex/sls01-sales-package`.

## Ограничения и риски

- Совместимость: v2 сохраняется; Prompt Lab и исторический XLSX builder не переведены.
- Данные: import идемпотентен по package bytes; конфликт той же версии отклоняется.
- Безопасность: preview формируется allow-list правилом; неизвестное остаётся закрытым.
- LLM: не используется. Runtime/Dialogue/M6 проверки — NOT_RUN в артефакте.
- Case 02/07 валидны без искусственного персонажа.

## Критерии приёмки

- [x] Ровно девять пар, версии и checksums совпадают с source manifest.
- [x] 55 точных IndicatorID сверены с M2 hierarchy; чужая hierarchy отклоняется.
- [x] 02/07 валидны без фиктивного персонажа; закрытое не попадает в preview.
- [x] Повторная сборка детерминирована; подмена source checksum отклоняется.
- [ ] DB round-trip на изолированной БД сохраняет 9 Case/55 targets (NOT_RUN:
  `TEST_DATABASE_URL` не настроен; обязательный CI выполняет PostgreSQL integration).
- [x] Старый schema v2 пакет продолжает проходить прежние тесты.
- [x] Новое предметное содержание не встроено в Python/JS.

## План проверки

- `git diff --check`.
- `pytest tests/unit/test_m5_sales_package.py tests/unit/test_m5_case_package.py`.
- Backend unit набор по verification matrix.
- `TEST_DATABASE_URL=… pytest --run-integration tests/integration/test_m5_sales_package_db.py`.
- GitHub CI `frontend` и `pytest` перед merge.

## Откат

Не выбирать/не импортировать `m5-sales-pilot-cases/0.1`; revert кода schema v3 и
builder. Уже импортированный immutable draft не удалять: оставить вне опубликованного
каталога. Исторический schema v2 пакет и начатые Cycles не меняются.
