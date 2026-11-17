# P4K-REPORT-07 — сравнение собственных прохождений

Основание: приложенные `P4K_REPORT_07_Comparison.txt`, `00_START_P4K_REPORTS_2026-11-15.txt`, пакет `P4K_REPORT_REFERENCE_2026-11-15.zip`, редакция 15.11.2026. Результат: выбор двух разных сохранённых личных Cycle, допустимые разности по навыку, отдельные значения с причинами и экран 1440/390 px.

Base: `origin/main` = `6c67dd749d26b68f61c879ce18c1d9ebb0b03389` (merge REPORT-06). Первый `git ls-remote` 17.11.2026 не прошёл из-за DNS; повторный `git ls-remote` и fetch перед PR подтвердили base. Рабочая ветка/worktree: `codex/p4k-report-07` / `worktrees/p4k-report-07`. Основная ветка пользователя с незавершёнными изменениями не затрагивается.

Источники: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/evc/{agent-workflow,verification-matrix,artifact-recipe,task-template,review-checklist}.md`, `docs/architecture/product-4k/{1.0/context,registry,m8-results-report-contract,m8-partial-result-contract}.md`, Change 01 `README.md` и И-1/5–7, `docs/methodology/source-sets/2026-10-01/manifest.json`, M8 v1.2 §7.3, M6 v1.8 адресно; reference `SOURCES_AND_SCREENS.txt`, `CURRENT_PRODUCT_DECISIONS.txt`, prototype scenes. Выбранные M6/M8 FROZEN, CURRENT=NO; Change 01 WORKING. SourceSet SHA — в manifest; подключение источника не доказывает runtime.

PM-05/C-56 даёт фактические Scores, PM-06/C-67 сохраняет Results/Report, PM-07 читает и показывает. Затронуты `Api/m8_report_comparison.py`, `Api/routes.py`, личный экран `web/js/screens/report.js`, его CSS/HTML и адресные тесты. Владелец данных — Cycle owner. Схема и опубликованные snapshots не меняются; исторические недостаточные данные fail closed.

Первичное доказательство дефекта: `_global_evidence` требует равенства `target_profile` и целого `profile_ref`; `compare_reports` запрещает любой partial_score; автопара в SQL сортирует по созданию Cycle, а не закрытию. Существующие unit/HTTP/browser тесты находятся в `tests/unit/test_m8_report_comparison.py`, `tests/e2e/test_m8_report_comparison_http.py`, `tests/browser/auth-r03.spec.mjs`.

План проверки: адресная unit-таблица (включая истинный 0, null, partial 2/3 vs 3/3, технические ID), HTTP и isolated PostgreSQL для выбора/owner scope, browser-действия 1440/390/320 px, lint/build, `git diff --check`; обязательный CI точного head до merge. Fixtures синтетические, 1 worker, retries=0, реальные LLM=0. Откат: отключить новый UI/route версией кода; сохранённые Reports и БД не изменены.

Стоп-условия: новый предметный смысл, миграция, новый артефакт, передача чувствительных данных — нет; таблица M8 задаёт пределы. Публичный response расширяется совместимо. Утверждение смысловой эквивалентности разных версий без mapping запрещено.
