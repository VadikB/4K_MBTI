# P4K-REPORT-11 — третий блок синтетических проверок

Основание: прямое «продолжаем» пользователя после принятия REPORT-10 и приложенное
`P4K_REPORT_11_Synthetic_Block.txt` rev1.0 от 15.11.2026 (SHA-256
`ec6a12d6a5ea72b4bc635264a7edb200613b55cd425a3f57cccad72ef2d040de`).
Вложение задаёт критерии, а поручение пользователя — текущий этап. База
`fffd501a51cae673a4e0ee87ec5d6cbc83069e21`, версия 2.1.26;
ветка `codex/p4k-report-11`, отдельный чистый worktree.
Первичная база `02596d7` была обновлена после merge #241; первоначальные
проверки оставлены диагностикой, bridge и изменённый экран проверены повторно.

## Результат и границы

Один проверяемый комплект S01–S12: независимое ожидание, первичный тест/экран/PDF,
точный SHA, вывод и ограничения. Один новый связующий HTTP/SQL тест использует
валидный seeded pre-close Cycle: фактическое закрытие, M6/M8 worker, сохранённый
Results/C-67, повторное чтение, история и PDF. Это проверка стыка, не повтор пути
от приглашения. Уже существующие fixtures используются по назначению, не выдаются
за новое предметное содержание. Небольшой обнаруженный дефект исправляется
адресно; новая методологическая норма и новый продуктовый объём исключены.

Источники: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/evc/{agent-workflow,
verification-matrix,artifact-recipe,task-template,review-checklist,
assessment-first-case-profile}.md`, `tests/README.md`, Change 01 README
(WORKING, SHA-256 `ac082bb94aac1b86c61d7e39589d76c886c6703ef3afc07bc8fecf1676a0a26d`),
task manifest (SHA-256 `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8`),
M8 report contract draft QA (SHA-256
`9e3bf9d803af9dcc26a0a9443b0b7caa643f2ff62264e867a227313777eeafde`),
`docs/architecture/product-4k/{1.0/context,registry}.md`, REPORT-10 TASK/CHECKS,
`P4K-SYN-LIMITS-FIX-01` и `P4K-PATH-GUARD-01` TASK/CHECKS, соответствующие
M10/M6/M8, access/correction и browser-тесты. M1 v1.4 и M8 v1.2 остаются
FROZEN/CURRENT=NO; Change 01 WORKING. Пакеты и test fixtures не утверждают GC.

Связь: Change 01 И-5/6 и M8 v1.2 → C-46/C-56/C-67 → M10 orchestration,
M8 Results/access/comparison/correction/PDF → интеграционный HTTP/SQL bridge,
адресные backend/browser/PDF проверки и матрица `CHECKS.md`. Для S01/S04
сохранённые профили/назначение читаются из snapshot, для S07 разность допускается
только по REPORT-07 contract. Стоп-условия рабочего цикла: смысл/кардинальность,
API/схема, миграция, новый источник нормы/артефакта, права, откат, выход за границу —
**нет** для тестового контура. Если проверка выявит иной случай, зависимое
изменение остановить и записать в CHECKS.

## Ресурсный профиль до запуска

- `run_id=report11-20261117-02596d7`, свой PostgreSQL 15 на `127.0.0.1:55441`,
  БД `p4k_report11_pytest`, только синтетические данные; один worker, retries=0.
- Общий лимит одной связки 900 с, без содержательного прогресса 180 с;
  отдельный HTTP/worker шаг до 120 с; browser действие ограничено Playwright
  timeout 30 с на test, общий browser batch 600 с, максимум 80 действий
  и 20 снимков для нового связующего browser-маршрута. В этом задании новый
  длинный browser PATH от приглашения не запускается.
- Controlled gateway: всего не более 30 вызовов в связывающем тесте;
  платные LLM и письма — 0. Исчерпание лимита — FAIL. Исходный предел 15 остановил
  первый прогон на 19-м вызове после 18 уже учтённых; исходный FAIL сохранён в
  `evidence/bridge-initial-budget.log`. Повышение до 30 задано до повторного
  прогона по фактическому маршруту M6/M8, без изменения продуктового кода.
  Счётчики не обнуляются при retry. Собственная process group останавливается при
  timeout/error; DB и preview останавливаются даже при FAIL. Ресурсная квитанция
  и итоговая проверка порта записываются в `CHECKS.md`.
- AC07/08: `P4K-PATH-GUARD-01` включён в `main` commit `f5053402`,
  `tests/browser/fixtures/path-action-budget.mjs` и
  `scripts/assessment_first_case.py` имеют bounded action/visual profile и
  отдельную controlled validation. Его старый PASS не переносится на новый прогон.

## План проверки и передача

До кода: зафиксированы затронутые C-46/C-56/C-67, M10 и отдельные тесты выше.
Далее: связующий HTTP/SQL тест → S01–S12 адресные unit/integration/browser/PDF
проверки → реальный просмотр представительских 1440/390 и стресс 320/200% →
матрица с FAIL/NOT_RUN → review, `git diff --check`, docs/tests release preflight,
PR и CI точного head. Продуктовый код и версию менять только при подтверждённом
дефекте; для docs/tests-only номер не назначать по `CONTRIBUTING.md`.

Флаги текущего этапа: `branch_push=true`, `pr=true`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`. Основание — прямое продолжение
серии пользователем; права на merge/deploy этого PR не выданы. Откат: revert
теста и отчётного комплекта, БД после teardown уничтожается, сохранённые
публикации приложения не меняются. Выпуск test/pilot не входит в этот этап.

После открытия PR #242 полный CI на `b7690554` обнаружил дефект S05:
рендер SVG-подписей радара на Linux меньше действующего порога 14/12 px.
Минимальная CSS-правка подготовлена и адресно проверена; это уже продуктовый
PATCH, поэтому прежний `version_bump=false` не даёт права назначить номер.
`npm run ready:prepare` назвал следующий кандидат `2.1.27`. Владелец прямо
согласовал назначение PATCH 2.1.27 и обновление PR #242, сохранив merge/deploy
отдельным решением. Итоговые флаги этого шага: `branch_push=true`, `pr=true`,
`version_bump=true`, `merge=false`, `deploy=false`, `artifact_publish=false`.
`npm run ready:prepare -- --candidate 2.1.27` прошёл; CI head `364aaf9a`
дал 9/9 PASS. Позже PR #243 продвинул `main` до `0aadde0a` и занял 2.1.27.
Владелец прямо разрешил новый PATCH 2.1.28 и обновление PR #242, сохранив
merge/deploy отдельным решением. Ветка интегрирована со свежим `main` через
`f188dd8f`, конфликт generated `web/dist` решён пересборкой; release preflight
2.1.28 PASS. Для нового head обязателен повторный CI.
