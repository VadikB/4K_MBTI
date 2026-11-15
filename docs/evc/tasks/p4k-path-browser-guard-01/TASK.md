# P4K-PATH-GUARD-01

## Результат и область

Один конечный бюджет реальных browser-действий PATH29 до первой AS, безопасный FAIL при превышении и явный controlled-итог. Изменяются только browser harness, его валидатор, локальный runner и адресные тесты. PM-02/03/04, C-23/24/34, admission, Case, provider, схема БД и предметные артефакты не изменяются. Полный PATH здесь не запускается.

## Источники и решения

- Запрос владельца: `P4K_PATH_GUARD_01_Remain07_2026-11-15.txt`, редакция 1.0, 15.11.2026. Он определяет технические критерии, но сам по себе не даёт новые полномочия push/PR/merge/deploy/version_bump.
- Прочитаны: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/evc/{agent-workflow,verification-matrix,artifact-recipe,task-template,review-checklist,assessment-first-case-profile,decision-register}.md`, `docs/architecture/product-4k/1.0/{context,updates/2026-10-01/README}.md`, `docs/architecture/product-4k/registry.md`, `docs/methodology/source-sets/2026-10-01/manifest.json`, затронутые browser fixtures/runner/tests. Применим Change 01 WORKING; M1 1.4 FROZEN/CURRENT=NO, M7 1.3 в выбранном комплекте. Предметная норма не меняется.
- `P4K.TASK.RULES` и `P4K.DEV.PRINCIPLES` из задания как отдельные локальные файлы не найдены; технические AC заданы самим приложенным текстом и действующими EVC. Это не препятствует ограничителю harness, новых предметных правил не вводим.
- Task SourceSet `manifest.json`: Change 01 `source.pdf` SHA-256 `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081` (WORKING); M1 v1.4 `source.docx` SHA-256 `5fa5ab5735dfe57fac6ef3c93aca50d149fbd7abd365edf80d362c10e2d7a975` (FROZEN/CURRENT=NO). Эти байты не менялись; task guard не назначает CURRENT/runtime.
- Адресно прочитаны Change 01 И-1/6/7, M1 v1.4 §M1.9 (время Cycle), M7 v1.3 (введение и граница времени Cycle, original SHA-256 `50a0d53a3aaf6258957ecc6d9e89f27d922bfbe4cd55668185d475c87f4e2f10`), ADR-002 C-23/24/34. Счётчик действий Playwright — лимит технического теста; он не меняет два эффективных параметра времени участника и frozen snapshot Cycle.
- Старый REMAIN-07 worktree `codex/p4k-remain-07` проверен: готового code candidate нет, его отчёты и receipts сохранены без изменений. Исторический controlled PATH служит только offline-примером валидатора; старый action profile остаётся FAIL.
- Стоп-условия: смысл/кардинальность/публичный контракт/миграция — нет; новый предметный артефакт/допуск — нет; внешние записи и полномочия выпуска — да, ожидают отдельного решения владельца. Секреты, рабочие БД и real LLM не используются.

## Прослеживаемость и план

Change 01 И-2/3/6, M1 1.4 и C-23/24/34 задают сохранённые profile→candidate/admission→AS→explicit Start; `tests/browser/path29-participant.spec.mjs` проверяет этот путь. Задача добавляет только технический предохранитель вызовов Playwright: `path-action-budget.mjs` → PATH29 и его helper → native smoke/unit. `assessment_first_case.py` → `preparation-receipt.mjs` сохраняют существующую проверку фактов и отдельный controlled-режим → offline historical receipt + отрицательные controls.

1. Проверить base/кандидат и локальные источники — завершено.
2. Guard, controlled-итог, адресные регрессии — реализовано, проверки идут.
3. Полный локальный минимум, self-review, точный code/release commit — завершено.
4. STATE/CHECKS — активно; push/PR, CI и человеческое review — после прямых решений владельца.

Проверенный code/release commit: `8523340a036fe06bc7f61c8e227b273fd4c550d2` от base `e8773ca80b9e3089a0faec16e9722680d126d8bb`. Документационный commit добавляет только эту карточку; актуальный PR head указывается при передаче.

## Бюджет и проверка

Профиль включается только `P4K_PATH_BOUNDED=1`, с обязательными положительными целыми `P4K_PATH_ACTION_LIMIT` и `P4K_PATH_VISUAL_LIMIT` до `cli('create')`. Один proxy для browser→contexts→pages→locators, счёт резервируется перед delegate. `actions`: navigation/reload, ввод, click/dblclick/check/select, keyboard/focus и аналогичные вызовы. `visuals`: newPage, viewport, screenshot, scroll, page activation и pointer. Read/assertions ограничены Playwright/test/runner deadlines. Bounded first-case оставляет один 1440px geometry/screenshot и first-case proof, прежняя полная матрица остаётся default соседних тестов.

Для передачи 07 кандидат пределов: `actions=120`, `visuals=40`. Основание: прошлый PATH зафиксировал 97 input/navigation, а дополнительные 33 viewport, 56 trial-click и 30 screenshot создавали общую сумму выше 100. Здесь четыре повторные матрицы и 5-control first-AS матрица не исполняются; остаются одна основная geometry и single-control first-AS, четыре обязательных screenshot, несколько viewport/scroll/activation и создание дополнительных страниц. Резерв 23 action покрывает учитываемые keyboard/focus/retry до hard stop; visual 40 покрывает страницу/снимок/viewport с резервом, не является бесконечным default. Фактическая квитанция будущего единственного PATH 07 покажет обе суммы.

## Совместимость, риск и откат

Default PATH29 и соседние визуальные тесты сохраняют полную матрицу; controlled full PATH требует bounded. Старые receipts без `bounded_path=true` не получают новых гарантий. Новый bounded receipt должен быть completed, совпадать с run и иметь конечные пределы; иначе общий FAIL даже при функциональном completion. Отмена — revert commit этого PR, без миграции и потери данных. Teardown owned DB не расходует browser budget; destroy ограничен 30 с, server stop — 5 с. Если terminal export неизвестен, существующий deferred cleanup сохраняет owned state.

## Полномочия выпуска

`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`, `version_bump=true`, `artifact_publish=false`. Прямой запрос пользователя разрешает реализацию и локальные проверки этой задачи. Владелец отдельно подтвердил PATCH 2.1.10 в ответе 15.11.2026; `npm run ready:prepare -- --candidate 2.1.10` прошёл и обновил release-файлы. Предыдущие решения для PR #223 не расширяются на этот PR; вложение содержит требования, не полномочия. Push/PR/merge/deploy остаются отдельными этапами.
