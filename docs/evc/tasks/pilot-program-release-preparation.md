# PATH-PILOT-PROGRAM-01 — подготовка выпуска программы

## Текущий итог: публикация выполнена — 05.11.2026

Владелец ответил «идем дальше» на конкретные три шага:1.2/publisher4, бесплатная
изолированная retirement-регрессия и только при её PASS/свежем preflight —
публикация новой ProgramDefinition и exact export. Это решение записано в
[owner-decision](../evidence/pilot-program-publication-execution/owner-decision.json);
исторические PENDING ниже и в прежних receipts не переписываются задним числом.

Результат: **PUBLISHED_READBACK_VERIFIED**, `specialist_pilot@1.2`, DB id **2**,
publisher4, configuration11, catalog2, role2, status published.
Серверный наблюдаемый момент —2026-11-05T17:40:31.103491+00:00;
raw published_at —`2026-11-05 17:40:30.345813` (поле timestamp без timezone).
Definition checksum `b4e8270fd10436c417d7b40b8be8049dc2e9329f42a1ffa6d725877480d04718`;
snapshot `daa715b153f16e9ebc4ea6744a1c8541c5e269e248bba4b5c37723571e6ccfce`.
Проверенный exact [source receipt](../evidence/pilot-program-publication-execution/published-release-source.json),
229612 bytes, SHA256 `09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b`.
Он существует также на сервере:
`/home/vadim_bogachev/evidence/pilot-program-1.2-wryr3q10/published-release-source.json`.
Default fixture1.1 не заменялся; программе/receipt нового latest не присваивается.

### Реализация и первичные доказательства

- Новый [SQL test](../../../tests/integration/test_program_publication_retirement_db.py)
  использует точный SQL прежнего операционного проекта и существующий lifecycle.
  17 новых guards +5 lifecycle +7 start/readiness =**29 PASS** в owned localhost
  PostgreSQL16; данные исключительно SYNTHETIC, provider disabled.
- [Регрессия](../evidence/pilot-program-publication-execution/retirement-regression.json)
  сохранена до [cleanup](../evidence/pilot-program-publication-execution/cleanup.json):
  marker/имя проверены,0 active connections, DROP без FORCE, DB/state отсутствуют,
 0 owned DB/connections, точный task-контейнер auto-removed. Постоянная БД не цель cleanup.
- [Свежий preflight](../evidence/pilot-program-publication-execution/prepublication.json):
  main/test e63eba6 /2.0.66, tracked clean; exact32 tables/353 columns/191 constraints/
 84 indexes/16 triggers; legacy1.1/config/catalog/roles/Cases/QA/artifacts совпали.
 1.2 свободна, publisher4 configured superadmin/not suppressed, role resolution id2.
- Выполнен **один** вызов существующего `scripts/publish_assessment_program.py --publish`
  с версией1.2/publisher4; exit0. [argv/итог](../evidence/pilot-program-publication-execution/publisher-invocation.json).
  Одноразовый [операционный driver](../evidence/pilot-program-publication-execution/EXECUTE_APPROVED.py)
  передан через SSH stdin; не установлен на сервер, не новый runtime/API/retire CLI.
  Он не выполняет retry или automatic retirement; до publisher все gates read-only.
- [Post-readback](../evidence/pilot-program-publication-execution/publication-result.json):
  прежние полные program rows/role links сохранены, новая программа и один role link,
  config/catalog/roles/9 Cases/27 исходных QA/15 artifacts без изменений, схема прежняя.
  Полные org connection rows сравнивались только в памяти: неизменны, для1.2 их **0**.
  Подключения, активация, retirement, новая AS/start/ответы/платный PATH не выполнялись.
- Четыре серверных JSON скопированы побайтово, все bytes/SHA совпали. Независимые
  `CHECK.py`/`REGRESSION.py`: actual published selector1.2 PASS,8 испорченных копий
  отклонены, запуск с `-O` запрещён; sockets/DB/LLM0. Пересчитаны Case/QA/artifacts
  существующим validator, полный snapshot равен принятому builder output.
- Backend на текущих неизменённых runtime sources: **908 PASS**,351 deselected,
  exit0; интеграционные17 новых тестов входят в29 выше, не в908. Единственное
  предупреждение — прежнее Starlette/httpx deprecation. [Проверки](../evidence/pilot-program-publication-execution/verification.json).

### Сопоставление шагов и ограничения

| Шаг | Факт | Остаток |
| --- | --- | --- |
| Подтвердить номер/издателя/узкий scope | Решение владельца1.2/publisher4 записано | Нет |
| Проверить восстановление до публикации |29 SQL PASS, guarded retirement/rollback/immutability, cleanup PASS | Не race-proof; retirement не автоматический и не выполнен |
| Повторить свежий preflight | Точный scoped schema/source/publisher/version PASS | Не проверка всей БД или всех функций продукта |
| Опубликовать новую программу | ID2, published, checksum/snapshot точны, один CLI call | Не подключение существующих организаций |
| Экспортировать точные источники |229612 bytes, independent loader/checksum PASS | Не новый human review и не приёмка качества AS |
| Подготовить следующий PATH | Профиль/README содержат полный exact selector; harness уже в main2.0.66 | Free bootstrap этих published bytes ещё NOT_RUN; paid run требует отдельного разрешения |

Полный M2=61 сохранён; принятый план39/22 вне,55 условий, маршрут и7200/259200
не менялись. Новая программа хранит ранее принятый exact P1–P3/M1–M4 snapshot;
публикация не приравнивается к допуску любой AS, LIMITED либо фактическим наблюдениям.
Не менялись M0–M8/CURRENT, исходные QA, prompts, admission и repair.
PREP-DIAG-01 остаётся отдельно с исторической причиной **UNKNOWN**.

### Ветка, CI, main, развёртывание и откат

Локальная `codex/pilot-program-publication`, входящий commit e24255f от e63eba6;
итоговый commit указан в Git/пакете. Изменены только EVC evidence/task/state,
описание профиля/README и новый integration test. Api/scripts/assessment_definitions
и приложение2.0.66 не менялись. Main/test —e63eba67d77fb73f7fb9bb219bc3fe5d3807a909.
Три чужих untracked файла корневого checkout сохранены. Push/PR/merge/deploy здесь нет.
CI/review выпущенного runtime —PR171 PASS (review a60200d, identical tree squash e63);
deploy42047619768 PASS. Для локального evidence/test commit нового CI нет;
он не выдан за CI-проверенный кандидат следующего merge. При будущем PR обязательный
CI/review сохраняются, полномочий на такой PR сейчас нет.

Схема/конфиг/deploy: миграций, смены конфигурации и новой выкладки нет.
Безопасность: секреты/.env/PII не экспортированы; DB настройки только в памяти,
тесты не используют рабочую БД. Scoped readback не доказывает глобального отсутствия
параллельных действий других пользователей; сравниваемые program/role/connection/source
объекты совпали. В собственном publisher нет вызовов LLM, provider operations0.
Published1.2 не удаляется/редактируется; её retirement допустим только по точному
ID/checksum, при отсутствии любых подключений, контролируемом окне и отдельном
проверенном решении при необходимости. Автоматический откат не запускался.
Исторический операционный проект не обещает обратного unretire.

Следующий минимальный шаг — бесплатный bootstrap1.2 с полным selector на новой
owned-БД. После него отдельное решение владельца об одном paid PATH с остановкой
при содержательном отказе, без повторов/изменения правил. В этой операции PATH NOT_RUN;
приёмка первой AS/старта/0 ответов пока не заявляется.

## Историческое продолжение после выпуска harness — 05.11.2026

Исторический отчёт ниже относится к3385145/f211e71, не подменяет дальнейшие решения.
По «идем дальше» выполнен бесплатный read-only preflight на main/test
e63eba67d77fb73f7fb9bb219bc3fe5d3807a909 /2.0.66. Профиль/runner уже в main;
повторно не создаются. [Актуальное состояние](pilot-program-release/STATE.md).

Прочитаны текущий паспорт, publisher/source-export/schema collector и compare,
program lifecycle/binding, contract docs/architecture/pilot-plan-start-admission-contract.md,
существующие retirement/first-start SQL tests. Неизменённые README/CONTRIBUTING/EVC
recipe/matrix/context/Registry/Change01 повторно использованы из выполненного выпуска.
Нового смысла M2/плана/P1–P3/M1–M4, API, runtime, prompt или repair нет.

Свежая схема EXACT_SCOPED_SCHEMA_MATCH; все шесть однотипных source objects1.1
(program/configuration/catalog/roles/cases/artifact_readback) совпали с историческим
receipt. Девять Cases,27 исходных QA и15 пересчитанных artifacts без изменений.
1.2 свободна; checksum кандидата b4e8270fd10436c417d7b40b8be8049dc2e9329f42a1ffa6d725877480d04718.
Publisher user_id4 технически является configured superadmin без suppression,
но полномочие на новую публикацию ожидает решения владельца. Новых PII не выгружали:
email использован только внутри SQL boolean-проверки, в evidence лишь ID/два bool.

Две отдельные транзакции read-only с rollback: существующий READ_SCHEMA и exact
collect(program_version='1.1') через прямой psycopg с default_transaction_read_only=on,
repeatable read/timeouts. .env/ключи не печатались; ensure/bootstrap/publish не вызывались.
Рабочая БД не менялась; новых test DB/cleanup/LLM нет. Первичный
[readback](../evidence/pilot-program-publication-preflight/readback.json) сохранён полностью.
Offline проверки collector/source/builder и ссылки/diff выполняются на этом evidence;
старые historical VERIFY не ослабляются и не запускаются как current harness proof.

Блокеры до исполнения: утверждение номера1.2, назначение publisher4 и разрешение
публикации только новой ProgramDefinition; отдельное решение по
[операционной процедуре retirement](../evidence/pilot-program-publication-preflight/operations-proposal.json).
Существующий переход/запреты подтверждены прежним CI171, но готового retire CLI нет;
новый guarded administrative SQL ещё не объявлен проверенной командой. При выборе
этой процедуры сначала бесплатная изолированная регрессия guard-предикатов/immutability,
и лишь при её PASS и свежем preflight возможна разрешённая публикация. Если quiescence,
отсутствие подключений или exact refs не доказаны — STOP без записи/самовольного отката.

Флаги этого продолжения: branch_push=false,pr=false,merge=false,deploy=false,
version_bump=false,artifact_publish=false,paid_llm_run=false,permanent_database_write=false.
Локальная ветка codex/pilot-program-publication от e63eba6; main и три пользовательских
untracked файла не затронуты. Откат подготовки — отдельный revert только docs/evidence;
не published1.1/снимков. Paid PATH/активация существующих организаций — отдельные разрешения.
PREP-DIAG-01 по-прежнему UNKNOWN, не связан агентом с coverage/harness.

Проверка evidence: `CHECK.py` и `REGRESSION.py` — PASS; однотипные source hashes
пересчитаны по свежим/историческим JSON,15 artifacts и candidate checksum проверены
независимо; локальные docs links,11 negative mutations и fail-closed при `-O`.
Прежний schema CHECK —1 positive/11 schema mutations/4 unsafe records PASS.
Первая inline проверка имела TypeError в setup запретительного socket stub (function
мешала ssl subclass); исправлена только проверка на NoSocket subclass, не продукт
или harness. Точные команды/stdout/exit и ограничения —
[verification.json](../evidence/pilot-program-publication-preflight/verification.json).
Полный backend/новый CI не повторялся: runtime/артефакты/потребители не менялись.

## Историческая подготовка на3385145/f211e71

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
