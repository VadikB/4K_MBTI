# M5-01. Банк без авторских примеров

Основание — команда владельца «запусти задание» и критерии карточки 01 от 21.11.2026. Область — один локальный кандидат, автономные проверки в изолированной PostgreSQL, без публикации во внешнем контуре. База `869c88e1dff22d45e6fb86d08b6cda6061be2e23` подтверждена `git ls-remote`. Ветка `codex/m5-01-bank-without-author-as`.

## План

1. Паспортная проекция, контракт AS, сборка и связанный выпуск пакета.
2. Запросы генерации, проверки и repair, обработка первой подготовки и Next.
3. Синтетический прогон импорта, приёмки, совместимости и восстановления. Содержательная приёмка живой моделью учитывается отдельно.

Контракты — Change 01 И-3 (C-23/C-34), ADR-002, M5 v1.1 §§3–6, паспорт v1.1 поля 1–22, M4 v1.0 §§4,6, Glossary WORKING 30.09.2026 W020–W023 (`95bdc36d…`). Предметные основания в паспортах, нормативных M2 и M3 и каталоге CaseType. Контур публикации, неизменяемые снимки, последовательность и данные PM-04 сохраняются. Новых таблиц и миграций нет. Старые версии для чтения; новая подготовка по прежней закреплённой версии использует её паспорт.

Критерии — AC-1 импорт/публикация/readback/повтор, AC-2 фактические запросы, точные ID, repair и ошибки протокола, AC-3 первый старт, Next, закреплённые версии и устаревшие попытки очереди.

Для этапа действуют `branch_push=false`, `pr=false`, `merge=false`, `deploy=false`, `version_bump=false` и `artifact_publish=false`. Прогон публикации только в изолированной QA БД. При откате сохранить совместимый паспортный механизм либо остановить выдачу свежих AS; зафиксированные снимки остаются читаемыми.

## Реализация и версии

- `CaseVersion` schema 4, банк `0.6`, контракт результата AS `m5-functional-as@1.0.0`, пакет prompts `m5-functional-passport@1.0.0`. Девять паспортов, 55 нормативных целей. Пакет не содержит готовых AS.
- `Api/m5_passport.py` сверяет CaseType и ролевую ветвь с реестрами, цели и версии с M2 и Applicability. Для модели проектируются поля паспорта и разрешённые сведения из закреплённого M4. Ошибки источника содержат CaseID, версию и поле или связь.
- `Api/m5_passport_generation.py`, `Api/m5_functional_generation_service.py` и очередь используют одни основания для генерации, Tester, Challenger и repair. Repair получает отклонённую AS и пути нарушений. Нормативная ссылка цели ведёт в паспорт и M2, а ссылка адаптации ведёт в допущенную AS. PM-04 получает материал, персонажей и правила в C-34 snapshot.
- `scripts/build_m5_functional_package.py` и `scripts/plan_specialist_program_release.py` по умолчанию используют паспортный банк. Режим `--historical-0.5` воспроизводит зафиксированный исторический выпуск. Форматы v2/v3, опубликованные версии и исторические данные сохраняются.
- PM-03 для новой AS в старом Cycle получает его CaseID/Version, паспорт, профиль и план. Непривязанный к паспорту результат попытки не переиспользуется для новой генерации; запись в очередь и назначение защищены lease, текущим attempt token и статусом Cycle.

### Контрольные суммы SHA-256

| Основание | SHA-256 |
| --- | --- |
| Change 01 PDF, v1.0/01 | `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081` |
| M5.Methodology v1.1 | `dc96f9b48e0711326c0c4239d63f50a2fa1e63176a728f3e9eb4420f9efb77c1` |
| M5.CasePassport v1.1 | `5560fec1f335bac8f60452d0d1f3659436962d5db1c5d3693848a6a7370d7ace` |
| M4.Context v1.0 | `07875e93ae422668b1b30cd60bc1c6140cae91db12b0b80ba4abca441cfe9291` |
| Glossary 30.09.2026 | `95bdc36d5ccb7d2da93d268ec6cb2012daace2b85878f0ffefc39e9d4c66b95d` |
| Контракт AS 1.0.0 | `c07a8800bfd7228a4c4b91e55dfff4901505821fcf8d8a85b9df7fb3eebd1655` |
| Пакет 0.6, канонический JSON | `153136aa21b59771f6f5fed1472853a2deeccf3a7d67b363ecaf7e203d469003` |

Сверены применимые решения EVC и первичные основания, в том числе
[M5_BANK_PUBLISH_01](../p4k-m5-bank-publish-01.md), [ARCH30-ADD01](../arch30-add01.md),
[ADR-002](../../../adr/002-cycle-as-dialogue-contracts.md) и [карта Change 01](../../change01-traceability.md).
Открытых предметных вопросов для локальной реализации не выявлено. Готовность живой
модели остаётся самостоятельным решением при выпуске.

## Порядок включения и отката

1. Принять исходный код, пакет Case `0.6`, правила `1.3.0` и контракт/prompts `1.0.0`
   как согласованный набор. Контракт ограничивает ответ 60 000 символов. До смены воркеров приостановить выдачу новых задач
   подготовки, дождаться завершения старых воркеров или остановить их и дождаться
   штатного истечения аренды. Перед возобновлением проверить очередь. Операции
   `queued` остаются в очереди. Прежние попытки с просроченной арендой получают
   новый токен. Уже назначенные AS читаются из сохранённых снимков.
2. Включить паспортный код подготовки. Проверить в изолированном контуре штатный
   импорт, publish/readback и повтор. Для продуктивной оценки подготовить решение
   владельца и evidence с тремя `scopes`, контрольными суммами точных паспортов
   `cases` и `as_contract_ref`. Публикация `assessment` проверяет эти ссылки.
3. После допуска выпустить `0.6-passport.1` и `1.3.1` через
   `plan_specialist_program_release.py --publish-admitted-catalog` с отдельной
   версией каталога, ключом идемпотентности, `--decision-basis` и `--assessment-evidence`.
   Активировать только новую версию конфигурации/ProgramDefinition со ссылкой на
   опубликованный каталог. Начатые Cycle сохраняют свои catalog/profile/plan refs.
4. При откате остановить выдачу новых задач и снять новую конфигурацию из выбора
   для новых Cycle. Возвращать предыдущий каталог можно с кодом паспортной подготовки.
   Если для отката нужен код, который ещё читает примеры, оставить новую подготовку
   приостановленной до возврата совместимого worker. Сохранённые AS и Dialogue
   продолжают читаться по своим версиям. Удаление снимков и перенос данных не нужны.

## Проверки 21.11.2026

- `git ls-remote https://github.com/VadikB/4K_MBTI.git refs/heads/main` — PASS,
  база `869c88e1dff22d45e6fb86d08b6cda6061be2e23`.
- `.venv/bin/python scripts/build_m5_functional_package.py --verify-only` и
  повторная сборка этой командой с путём `assessment_definitions/cases/competencies_4k/functional-personalization/0.6`
  — PASS, воспроизведены package и runtime artifacts.
- `.venv/bin/python scripts/plan_specialist_program_release.py` — PASS,
  dry run подтверждает CaseVersion/CaseType и planned gate для assessment.
- `git show 79147b93:<индекс и два файла паспортов>` и сверка
  `build_applicability_plan` — PASS. Совпали точные упорядоченные ID,
  и их порядок. SPEC.02 — 33, SHA-256 массива
  `bf4e1bd5155ef3e152d9c9404cc3bf5df4dbeccc0d2b2f325ed93e5f1c7de091`.
  SPEC.03 — 31, SHA-256
  `cf774927c0e7d0541f462efea62a91c038a5f532537a78be48e045119f8e00f1`.
- `npm run test:backend` — PASS, 1327 пройдено. Первоначальные отказы запуска
  дочерних процессов в песочнице сняты при прогоне с допуском.
- `.venv/bin/python -m pytest --run-integration -q tests/integration/test_m5_functional_package_db.py tests/integration/test_case_admission01_db.py tests/integration/test_m5_cycle_runtime_db.py tests/integration/test_exec_fix02_retry_db.py tests/integration/test_m10_product_path_db.py::test_functional_catalog_builds_a_separate_product_cycle_without_legacy_cases`
  — PASS, 32 проверки в выделенной PostgreSQL. Включены и старый закреплённый
  CaseVersion, и новый паспортный выпуск, восстановление после сбоя и отклонение
  устаревшей попытки.
- `.venv/bin/python -m pytest --run-integration -q tests/integration/test_case_admission01_db.py tests/unit/test_m5_passport_bank.py`
  — PASS, 10 проверок в выделенной PostgreSQL в копии с физически убранными
  `04_as` и отдельно скопированными файлами AS для версий 0.2–0.5.
  Захвачены запросы всех стадий, одинаковый нормативный вход, допуск, repair,
  несовпадение checksum рецензента и диагностика пропущенной связи.
- `TEST_DATABASE_URL=… npm run test:backend:integration` — прогон прервался
  после ошибки диска `No space left on device` при восстановлении локальной PostgreSQL.
  Общий результат полного набора на этой попытке не подтверждён.
- Повтор полного PostgreSQL-набора с `STAND_ADMIN_URL` — 495 PASS,
  2 SKIP (живой провайдер), 3 ошибки настройки fixture: в `TEST_DATABASE_URL`
  не был явно задан тот же пользователь, что и в `STAND_ADMIN_URL`.
  Повтор `.venv/bin/python -m pytest --run-integration -q tests/integration/test_published_release_seed_db.py`
  с одинаковым явным пользователем обеих баз — 3 PASS. Интеграционные результаты
  закрыты двумя прогонами.
- Финальный прогон очереди и допуска —
  `.venv/bin/python -m pytest --run-integration -q tests/integration/test_case_admission01_db.py tests/integration/test_m10_product_path_db.py::test_functional_catalog_builds_a_separate_product_cycle_without_legacy_cases tests/unit/test_product_cycle_preparation_projection.py tests/unit/test_m5_passport_bank.py`
  — 36 PASS. В новом профиле изменены должность и задачи во время
  восстановления. Первый старт и Next используют профиль, закреплённый при плане.
- `git diff --cached --check` — PASS.
- Содержательная приёмка на живой модели — NOT_RUN. Готовность пакета для
  оценки людей требует отдельной проверки. CI и внешний выпуск не запускались.
- Адресный повтор AC-1 после сбоя диска — PASS, 5 проверок. Сверены старый
  снимок AS по исходному UUID после публикации `0.6`, версия правил, CaseType,
  состав и checksum каталога и повтор публикации.


Проверочная копия и Git-коммит подготовлены в локальном каталоге. В рабочей
папке Google Drive чтение `.git/HEAD` завершалось тайм-аутом. Для передачи
используется Git bundle с одним коммитом поверх проверенной базы.


## Допуск к выпуску приложения

Владелец поручил «сливай в main». Для этого этапа разрешены `branch_push=true`,
`pr=true`, `merge=true`, `deploy=true` и `version_bump=true`. База обновлена до
`a31a23df81a2b3a848c611bff32340e84e1cc93a`, кандидат приложения — `2.1.54`.
Публикация банка в каталоге остаётся отдельным действием (`artifact_publish=false`).
Готовность к слиянию проверяется на точном head после CI и человеческого review.
