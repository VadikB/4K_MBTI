# P4K-POSTW02-QA-03 — Next и время

## Результат и граница

Устойчивое применение медленных runtime GET, восстановление подключённой кнопки
проверки прежней Next-операции, правдивое представление двух времён. PM-04,
представление Cycle/AS и команд; сервер владеет состояниями и интервалами.
Новые сущности, паузы/кнопки, изменение M7, источников, бюджета, схемы и данных,
индикатор, QA-04, merge/deploy исключены. Одна ветка `codex/p4k-postw02-qa-03`.
База свежего main: `71a9c535cee4aea094d2b49c2b73f39e22f99bbe` / 2.1.28,
fetch 17.11.2026. Чужие каталоги QA-02 и REPORT-FIX-02 не меняются.

## Требования и полномочия

Прямое сообщение владельца 17.11.2026: «запусти задание» с указанием
`QA03_Runtime_Next_and_Time.md`, редакция 1.1. Файл — источник требований;
полномочие — прямое поручение пользователя. Разрешён локальный цикл реализации,
синтетические регрессии, сборка, доказательства, собственные коммиты и подготовка
передачи. Исполнитель — Codex владельца на его машине, без делегирования.
`branch_push=false`, `pr=false` на локальном этапе; concrete diff/отчёт передаются
владельцу. `merge/deploy/version_bump/artifact_publish=false`. Нового номера нет.
Внешняя публикация остаётся отдельным этапом. Прежние допуски других карточек
не переносятся. QA-04 в списке активных чатов не обнаружена; её не запускаем.

## Прочитанные основания

- AGENTS.md; README.md; CONTRIBUTING.md; EVC agent-workflow, verification-matrix,
  artifact-recipe, task-template, review-checklist, decision-register; начальный
  актуальный раздел корневого STATE и STATE карточек POSTW02-03/04/QA-01.
- Product Architecture v1.0 context/Registry, Change01 WORKING 01.10.2026 README,
  И-2/И-4/И-6 source.md; ADR-002. SourceSet manifest 2026-10-01: архитектура WORKING,
  M1 v1.4 FROZEN/CURRENT=NO, M7 v1.3 FROZEN (не утверждение runtime readiness).
  M1 README и определения Cycle/Session/Dialogue сверяются с source.md.
- M7 v1.3 §5.3–5.6, относящиеся правила §6; рабочая выдержка глоссария
  POSTW02-04/evidence/glossary-sections.txt (30.09, производная, не новая норма).
- `PILOT-120` в decision-register и первичная карточка arch-a05-coverage-pilot:
  два фиксированных параметра. Числовые правила этой задачей не меняются.
  CONTRIBUTING-MERGE-AUTH-01 применим как процесс, merge-поручения здесь нет.
- Production interview.js, api.js, product-cycle-preparation.js,
  m10_product_flow.py, m7_completion.py, m5_cycle_runtime.py; связанные frontend,
  browser и persisted DB регрессии, tests/README.

Пробелы: отдельный документ P4K.TASK.RULES v1.0 не найден в Git; применяем явно
заданные ограничения текущей постановки и EVC. Это не мешает техническому fix.
Новых предметных правил/артефактов нет. Все восемь стоп-условий EVC — «нет»:
смысл, API, PM/LU, схема, сохранённые данные, внешние права/сервисы и lifecycle
не меняются; совместимость старого ответа и revert сохраняются.

## Подтверждённая причина

1. Каждый poll повышал serial даже при незавершённом GET: медленные ответы
   постоянно теряли право применяться. Теперь один актуальный контекст разделяет
   return-state/runtime chain; новый контекст/команда по-прежнему её инвалидирует.
2. `finally` отпускал удалённую кнопку; fast path новой карточки не пересчитывал
   disabled. Теперь подключённая кнопка выводится из pending map и server retry.
3. Между AS серверный finish закрывает collecting, открывает authorized_pause,
   возвращает paused + blocking=false. UI принимал false за ошибку чтения.
   Теперь paused/interrupted и blocking=true независимо подтверждают исключённое
   время; недостоверное чтение очищает остаток и сообщение, без подстановки true.

Прослеживаемость: Change01 И-2/4/6 + M7.5.3 → существующий runtime/command readback
→ interview.js → qa03-runtime.test.mjs / qa03-runtime.spec.mjs / DB test.
Новых контрактов/артефактного долга нет.

## План

- [x] Сверить свежий main, источники, владельца общих функций и дефекты.
- [x] Исправить чтения, кнопку и время в существующем renderer.
- [x] Адресные behavior-регрессии, HTTP/isolated DB и настоящий browser.
- [x] Матрица локального минимума, review, evidence, коммит/STATE/передача.

## Профиль проверки и откат

Один worker, ноль реальных LLM/писем, синтетические сведения, retries=0,
browser run ≤300s, шаг/HTTP ≤20s, искусственные долгие timeout — clock.
БД — собственная новая localhost PostgreSQL test/pytest; `.env` не читается.
Проверки: production handlers/renderer controlled I/O, адресная persisted
регрессия интервалов, desktop1440/mobile390/320 и снимки, frontend suite, lint,
build, diff. Серверная проекция не меняется, дополнительный HTTP тест readmodel
не требуется; существующий затронутый HTTP контракт проверяется ограниченно.
CI перед merge остаётся обязательным, локальные результаты его не заменяют.

Откат: revert diff UI/tests/dist; операции, интервалы и snapshots не меняются.
QA-05 — независимая read-only диагностика, её результат не подменяется этим fix.

Итог: [REPORT.md](REPORT.md), [STATE.md](STATE.md). Код/тесты/dist: `8b3ca49`.
