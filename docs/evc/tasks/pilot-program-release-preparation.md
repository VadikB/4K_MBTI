# PATH-PILOT-PROGRAM-01 — подготовка выпуска программы

05.11.2026. Статус: PREPARED_WITH_EXECUTION_BLOCKERS. Только docs/evidence;
не публикация, не изменение runtime и не итоговый PATH.

## Результат и область

Основание — запрос пользователя «делаем» после предложения подготовить конкретный
выпуск программы и план прогона без публикации/активации/LLM.
Подготовлены [паспорт и последовательность](../reports/pilot-program-1.2-release-plan.md),
[рецепт кандидата1.2](../evidence/pilot-program-release-plan/program-1.2.proposed.json),
[offline evidence](../evidence/pilot-program-release-plan/offline-verification.json)
и [состояние](pilot-program-release/STATE.md).

Включено: точная база, новая предлагаемая версия immutable ProgramDefinition,
повторное использование принятого P/M и T1, источники/checksum, пригодность текущих
инструментов, условия разрешённого будущего release/run, риски и откат.
Не входит: исправление обнаруженных ошибок harness в этой design-only подготовке,
изменение Api/scripts/tests/пакетов, новые платные calls, публикация, подключение
рабочих организаций, запись/миграция/cleanup постоянной БД, push/PR/merge/deploy.

## Источники и чтение

База кода `3385145201d5d365e08e9e8a6a6fb7e12a0aa258` /2.0.65.
Прочитаны AGENTS.md, README.md, CONTRIBUTING.md; workflow, verification-matrix,
artifact-recipe, task-template, review-checklist; архитектурные context/Registry,
M1v1.4 README (FROZEN/CURRENT=NO), Change01 README/manifest и применимые ADR-002
C-24/C-34/совместимость; assessment-runtime и m7-cycle-planning-contract.
M0–M8 и CURRENT не изменяются; нормативные определения/пороги не вводятся.
Прослеживаемость T01–T04/T10 — адресно проверены в change01-traceability, не объявлены
целиком закрытыми наличием этого проекта.

Адресные источники: path-pilot-approved-design.md, pilot-plan-start-admission-contract.md,
профиль assessment-first-case/1.1, tests/README.md (раздел профиля), manifest admission0.1,
source receipt `path-start-release.json`, Api/pilot_plan_admission.py,
Api/pilot_plan_binding.py, Api/assessment_programs.py; publisher/runner,
tests/path_start_release_source.py, tests/path_start_release_inputs.py,
tests/path29_browser_inputs.py и browser path29; unit tests snapshot/source/readiness.
Побайтовые refs этих потребителей — в offline-verification.json.
Опубликованные source receipt/QA не изменены. Старые PENDING/NOT_RUN внутри
исторических EVC-карточек не отменяют последующие owner decisions и release closure.

Архитектурный адрес: PM-02 frozen profile/assignment C-24 → PM-03 Case/AS и C-34 →
PM-04 immutable program/plan binding/first start. Владелец смысла — пользователь,
уже принявший exact P1–P3/M1–M4; агент не принимает новую норму. Публикация и
допуск каждой AS остаются раздельными. Нового artifact debt/legacy fallback нет.

## План и критерии

- [x] Источники, точные SHA/checksum и текущие границы проверены.
- [x] Предложен воспроизводимый новый кандидат1.2 без ID/published_at и без изменения1.1.
- [x] Полный M2=61, план39, вне22,55 условий, маршрут/время сохранены.
- [x] Пригодность инструментов проверена; SEED-01/BROWSER-01/SOURCE-01 названы,
      препятствие не выдано за успешный bootstrap/PATH.
- [x] Порядок release/readback/платного PATH/cleanup и решения владельца перечислены.
- [x] Документационные ссылки, существование команд, diff и адресные тесты проверены.
- [ ] Исполнение release/run: ожидает исправления harness и отдельных полномочий;
      не критерий успеха нынешней подготовки.

## Проверки и применимость

- `VERIFY.py` — exit0, `OFFLINE_PROPOSAL_VALIDATED_EXECUTION_BLOCKED`, не runtime PASS.
  Без dotenv, sockets запрещены, DB/LLM0; стандартный builder/checksum/validator,
  exact baseline и ожидаемый отрицательный reservation probe.
- Адресный pytest: source/snapshot/first-start readiness — **72 PASS** на неизменённом
  runtime базы3385145; лог/точная команда сохранены. Не новая оценка качества AS.
- Publisher/runner `--help` — exit0; database validation/publication не запускались.
- Docs-минимум: `git diff --check`, ссылки/пути/аргументы CLI и review согласованности.
- Backend/full integration/browser runtime не повторяются: код не менялся; исходный
  обязательный CI/review/deploy подтверждён PR170, не переносится на будущий fix.
- Новый CI NOT_RUN: remote push/PR не разрешены. Для будущего PR обязателен весь CI.
- Свежий server schema/data readback NOT_RUN. Сверка32 tables/353 columns/
  191 constraints/84 indexes/16 triggers из прошлого выпуска — только исторический
  baseline; перед разрешённой записью нужен актуальный preflight.

## Стоп-условия и независимые флаги

1. Предметный смысл: нет — принят exact v0.1, новые нормы не добавлены.
2. API/схема/владение: нет — код и данные не меняются.
3. Миграция/удаление: нет — не выполняются; постоянная БД защищена от cleanup.
4. Нет источника: нет для рецепта; свежий readback отсутствует и блокирует будущий выпуск.
5. Новый runtime-формат: нет — документальный рецепт, существующий builder/publisher.
6. Чувствительные данные/развёртывание: нет в подготовке; в выпуске нужны полномочия.
7. Откат: не блокирует docs, но retirement/остановка новых подключений должны быть
   проверены **до** постоянной публикации; готовой команды сейчас не заявлено.
8. Вне scope: да для fix/pub/активации/paid run — зависимая работа не выполняется.

`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`, `paid_llm_run=false`,
`permanent_database_write=false`. Локальная ветка/коммит разрешены рабочим циклом.

## Риски и откат

Config: рецепт не выбирается runtime автоматически. Схема: нет миграций.
Deploy: в этой задаче отсутствует. Безопасность: credentials/.env/PII не читались
и не экспортировались; unit окружение принудительно isolated/не подключается к БД.
LLM:0. Новая опубликованная программа будет видима в списке даже без подключения —
это часть будущего отдельного scope. Откат сейчас — только новых docs/evidence,
не удаление чужой работы. Будущие published версии и snapshots не удаляются;
старый reader2.0.64 не объявляется безопасным для созданных v2 Cycles.

## Передача

Рабочая ветка `codex/pilot-program-release-plan` от main3385145. Main и три
пользовательских untracked файла в корневом checkout сохранены. Точный коммит
передачи — в Git и сопроводительном пакете; последний принятый main/test остаётся2.0.65.
Следующий шаг — бесплатный адресный fix harness, затем отдельное решение по
программной версии/публикации и после readback — отдельное разрешение paid PATH.
Детали/стоп-условия — §3–6 паспорта. PREP-DIAG-01 остаётся отдельно UNKNOWN;
новые ошибки harness и покрытие не назначаются его первопричиной.
