# P4K-REPORT-05 — радар и выбор навыка

## Результат и границы

На базе `4160a589fc542b7bb4e3a35f49cfa15444887d6f` (REPORT-04 в main) привести радар, шкалы и связанную панель навыка к сохранённым данным одного Report и прототипу v9. Без изменения Results, C-67, расчётов M6, PDF и сравнения прохождений.

## Источники и решения

Прочитаны `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/evc/{agent-workflow,verification-matrix,artifact-recipe}.md`, `docs/architecture/product-4k/1.0/{context.md,updates/2026-10-01/README.md}`, `docs/architecture/product-4k/registry.md`, `docs/methodology/source-sets/2026-10-01/manifest.json`, M8 v1.2 §2/7, REPORT-03/04 TASK, переданные START/REPORT-05, `reference/{CURRENT_PRODUCT_DECISIONS,SOURCES_AND_SCREENS}.txt`, `prototype/{RADAR-REVIEW-2026-10-17,UI_BASELINE}.md` и адресные части `prototype/dist/{report.mjs,report.css}`. Change 01 — WORKING, M1 v1.4 — FROZEN/CURRENT=NO, M8 v1.2 — FROZEN; статусы не меняются. Продуктовое решение от 15.11.2026: три режима, пропуски без ложного нуля, панель рядом/ниже, каталог своего Cycle. Внешний GitHub недоступен из контейнера; локальный `origin/main` совпадает с `main` на указанном SHA.

Идентичность: START SHA-256 `593959b60edf0eab30c19a1e8cc2e9acb6496a0c9bf6b0df2bde211883168d1e`; REPORT-05 `46ddad2548d82f66750c1d533cfacd1dfe4e9ee8f0542620c21386793fb9cebb`; ZIP `887f7200a85bb4f97a52b2035efd72e234ca42919460fb8f0b5ea30c458a346a`; task manifest `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8`; M8 derived `f0272e304f36dc2d58777080b753a5fcc55578d22947e3afbae308b8afb71e0e`; Change 01 `source.md` `ee03f59d78e441f69964352bcd94a1e7c375c2ce306433a8d0cd056ba3af93d2`. Статусы источников и CURRENT не меняются.

## Связь и первичные проверки

M8.2/7 → C-67, сохранённые `c67.skills` → PM-07, `web/js/utils/report-radar.js`, `web/js/screens/report.js`, `web/index.html`, `web/styles/screens/report.css` → `tests/frontend/rad01-report-radar.test.mjs`, адресный browser fixture и снимки. До изменения: `focusM8Skill` вызывает `scrollIntoView` к строке под графиком; на узком экране общий график скрыт CSS даже при выбранных fill/outline.

M6/PM-05 рассчитывает SkillScore; M8/PM-06 сохраняет Results и C-67; PM-07 показывает сохранённую проекцию. Экран не выводит Skill Level, CompetencyScore, средний показатель К или фиктивный ноль. `projectReportRadar` сохраняет порядок, ID, исходную строку числа, частичность, ограничения и непрерывные участки; `radarPoint` рассчитывает только геометрию. PDF остаётся отдельным REPORT-10 и может читать проекцию без DOM.

## План проверок и откат

Адресные Node тесты геометрии, Playwright со статичными сохранёнными fixtures на 1440/390/320 и 200%, затронутые lint/build, `git diff --check`. Без БД/LLM, так как чтение отчёта не меняется. Откат — revert единственного commit REPORT-05; схема и данные не меняются. Обязательный CI на точном head — после публикации PR.

Стоп-условия рабочего цикла: предметная сущность, контракт, схема, права, артефакты и граница развёртывания не меняются; нового предметного решения не требуется. Точный удалённый `main` не подтверждён из-за недоступности сети; подготовленный PATCH требует повторного `ready:prepare` на свежем `origin/main` до Ready.
