# P4K-REPORT-06 — личная история оценок

## Результат и границы

Один завершённый Cycle даёт одну запись в истории владельца. История показывает сохранённую программу и дату закрытия, обновляет подготовку/ошибку/готовность в той же записи и открывает точный Report. Текущая оценка W02 остаётся в своей карточке. Удаляется действующий UI выбора внутренних версий и legacy-архива; исходные данные и audit сохраняются. Сравнение REPORT-07 и сервисное исправление REPORT-09 используют те же Cycle/Report.

## Источники и решения

- Владелец подтвердил 16.11.2026, что REPORT-05 слит и CI прошёл. После `git fetch origin main` подтверждён merge `7e96d4dc49e8e37356aa93a736d1373fb58eb779` (#233); его Git-дерево совпало с временной базой REPORT-05 `9ea439af`. Ветка перенесена на точный merge commit без изменения рабочих файлов. Перед merge REPORT-06 требуется CI точного head.
- Поручение: `P4K_REPORT_06_History.txt` 1.0 от 15.11.2026, SHA-256 `bcb396320297660ba4a76d9d85dd350ce6a3773ec28b3a7e4ebe3e421344ab51`; общий пакет `00_START...txt`, SHA-256 `593959b60edf0eab30c19a1e8cc2e9acb6496a0c9bf6b0df2bde211883168d1e`; reference ZIP, SHA-256 `887f7200a85bb4f97a52b2035efd72e234ca42919460fb8f0b5ea30c458a346a`.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/evc/{agent-workflow,verification-matrix,artifact-recipe,task-template,review-checklist}.md`, Change 01 `README.md`/`source.md` (И-1/5/6/7), `docs/methodology/source-sets/2026-10-01/manifest.json`, `derived/M8-v1.2.md` (§7.1, §7.3, §9), `docs/architecture/product-4k/{1.0/context.md,registry.md,m8-results-report-contract.md}`, ADR-002, reference `SOURCES_AND_SCREENS.txt`, `CURRENT_PRODUCT_DECISIONS.txt`, прототип `report-history`.
- Статусы: Change 01 WORKING; M1 v1.4 FROZEN/CURRENT=NO; M8 v1.2 FROZEN в task SourceSet, без утверждения CURRENT. Ноябрьское решение владельца: одна запись на Cycle, технические версии скрыты, владелец сохраняет доступ после членства.
- Выбранные оригиналы по `manifest.json`: Change 01 SHA-256 `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081`, M1 v1.4 `5fa5ab5735dfe57fac6ef3c93aca50d149fbd7abd365edf80d362c10e2d7a975`, M6 v1.8 `2e5f60a5f1c430458a253ec0bb4638555de1bec704ea02f1e5c2127a3abd39b4`, M7 v1.3 `50a0d53a3aaf6258957ecc6d9e89f27d922bfbe4cd55668185d475c87f4e2f10`, M8 v1.2 `a61909c996f66e88668c4cf713fb91129f3ab778ed843d0e796c7d4e226b73fa`. Полная ревизия методологии не выполнялась.
- Правило M8.7.1/7.3/9 и Change 01 И-5 → один Results/Cycle, отдельные технические версии и историческая трасса → C-46/C-56/C-67, PM-06/07 → `Api/m8_results.py`, `Api/routes.py`, `web/js/screens/{reports,dashboard,report}.js` → HTTP/SQL, browser.
- Нового предметного артефакта, нормы или миграции нет. Публичный API сохраняется; добавления только совместимые. Стоп-условий по смыслу, данным, правам и откату не выявлено. Свежий `main`/CI — выпускной gate.

## План и проверки

1. Сервер: стабильная сортировка по закрытию, одна актуальная Report-ссылка на Cycle, историческая программа, права владельца; регрессия SQL/HTTP на несколько Cycle/revisions, исключённое членство.
2. UI: история без legacy и version-selector, рабочая пагинация, состояния/ошибка/пусто, точный deep link/возврат/гонка; кабинет W02 без регрессии.
3. Адресные backend/frontend/browser тесты, lint/build, `git diff --check`; визуальная сверка 1440/390, адресно 320/200%. Integration — только изолированная test/pytest PostgreSQL. CI `frontend`, `pytest`, `full-verification` точного head перед merge.

Откат: revert REPORT-06 и новый штатный PATCH при выпущенной версии; БД и опубликованные артефакты не изменяются. `branch_push`/`pr` — после локального минимума и сверки base; `merge=false`, `deploy=false`, `artifact_publish=false`. `version_bump=true`: штатная `ready:prepare` подготовила 2.1.19 на `origin/main=7e96d4dc`.
