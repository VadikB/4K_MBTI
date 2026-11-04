# Постоянный контур синтетических прогонов Codex

## Результат и область

Настройка `assessment-first-case/1.1`: runner, минимальный seed, контролируемая
почта, отдельные browser contexts, реальные LLM generation/tester/challenger,
проверка источников и сохранённых/предъявленных AS, наблюдаемые сбои и cleanup.
PATH-START-01 не передан в исполнение. Продуктовые исправления, методологическая
приёмка, изменение M0–M8/CURRENT, merge/deploy/version bump не входят в работу.

Основание — прямые сообщения владельца 04.11.2026, включая уточнение границ текущей
настройки. Приложенный `P4K_Assessment_Start_and_Codex_Setup_2026-11-04.txt` редакции
1.0 — источник требований; действия разрешены сообщениями владельца, не самим
содержимым вложения. Раннее название «PATH-START-01 v1.1» в diagnostic identifiers
является исторической меткой тестовых входов, не заявлением исполнения PATH.

## Код, main и развёртывание

- Base и повторно fetched `origin/main`:
  `053d1a58b46b5cfa7784d3d9ba6fd4785efed769`, приложение 2.0.61.
- Локальная ветка: `codex/assessment-first-case`, worktree
  `/Users/vadim_bogachev/Developer/4K/worktrees/assessment-first-case`.
- Основная реализация: `a4a215755da32edb5fc8ed0898994bb0d7bf4e58`.
- Исправленная реализация/export:
  `4bab7230d8fa484fb8d922ee7d8b49b63674268d`.
- До текущей сдачи: `694f9c8de3265f5fb83b78c6cfeadd230fc7cd7c`.
- Бесплатная DB-регрессия collector/persistence/cleanup выполнена на чистом
  `9e659bdc09b38c1bc5c6751edaea25769d90be7e`. Финальный SHA пакета автоматически
  записан в MANIFEST.json/HANDOFF.md/Git bundle. После 9e659bd сначала добавлены
  сборка пакета, отчёт и первичные evidence; после cf6175e исправлены два дефекта
  harness, подтверждённые независимой проверкой владельца (раздел ниже).
- Чистый remote checkout: `/home/vadim_bogachev/worktrees/assessment-contour-final`,
  detached HEAD на SHA диагностического прогона; `worktree_status=""` фиксируется
  в code-identity.json вместе с SHA-256 исполняемых файлов.
- Read-only сверка deployed checkout `/home/vadim_bogachev/projects/Agent4K-Test`:
  main@`053d1a58…`; GET `https://test.4k-assistant.ru/users/version` вернул
  `2.0.61`, public_origin `https://test.4k-assistant.ru`.
  Это подтверждение checkout/version, не новый deploy текущей настройки.
- `branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
  `version_bump=false`, `artifact_publish=false` вне owned fixtures.
  Опубликованные общие версии и файлы `assessment_definitions/`, `Api/` не изменены.

## Источники, решения и прочитанные контракты

Повторно использован неизменившийся контекст: README/CONTRIBUTING, EVC workflow,
verification matrix, artifact recipe/task/review checklist, Product 4K 1.0
context/Registry, M1 v1.4 FROZEN/CURRENT=NO, Change 01 WORKING, task SourceSet,
ADR-002/ADR-003 и traceability. Прочитаны потребители и тесты:
`scripts/test_stand{,_seed,_check}.py`, PATH29 harness/spec, publication/authoring/
program services, `m5_storage`, `m5_catalog_integrity`, `m5_case_runtime`,
`m5_functional_generation_service`, `product_cycle_preparation_queue`,
`m10_product_flow`, `cycle_execution_manifest`, DeepSeek gateway/provider contract,
`tests/llm/test_m10_real_cycle_db.py` и затронутые unit/HTTP контракты.

PM-03 — генерация и независимый допуск AS; PM-04 — старт/предъявление по snapshot.
M6–M8 не исполняются: ни одного оценочного ответа. Нормы оценки не изменены.
Открытых решений, блокирующих настройку, нет; методологическая приёмка не заявляется.

## Происхождение CASE.SPEC.02 v0.6

Полный фактически импортированный JSON находится в
[evidence/source-provenance.json](../evidence/assessment-contour-2026-11-04/source-provenance.json),
поле `case.imported_json`. Seed изменяет два технических поля, не одно:
`/status: WORKING → FROZEN` и `/author_case/Status: WORKING → FROZEN`.
Pydantic `validate_case_version().model_dump(exclude_unset=True)` дальнейших отличий
не добавляет. Полный рекурсивный diff включён в evidence.

| Объект/преобразование | SHA-256 |
| --- | --- |
| Case в main, исходный JSON | `4e93e2a0487ef8cebfe0430c6abd5b9e4c262473d8118f0fe51923c294278549` |
| Только внешний /status=FROZEN | `663bfc6c7452761ee951b92f7ebf45e77be2e06edfbacbf2dc8b58adbe45d231` |
| Оба поля FROZEN, JSON из БД | `179fa0f8192862bee6af3190c8560f9c5ed133cc2fe07d6f5b6a98e6e3c9b729` |
| Исходный package JSON отдельно | `4c127cbb8ed3573885cccdadfc9ae8199b6f266bd3f8077644b45a3d7c8e486c` |
| Исходный import envelope {package,manifest} | `1efea268d9682a8712b62b07a5c27112b28231eb7d1a49966aa8c2fdb30c01b9` |
| DB import envelope после двух status-изменений у 9 Cases | `b9e2889b5a7b19dda6b88ebec30bffba87cf76afc3df4cb14df10de0036eb7b0` |

Case/package/QA/snapshot checksum использует compact sorted UTF-8 JSON **с LF**,
как `Api.m5_case_runtime`. Генератор хеширует candidate **без LF**.
Разные объекты и разные контракты хеширования не приравниваются.

Точные файловые источники (raw-byte SHA-256):

| Файл | SHA-256 |
| --- | --- |
| functional-personalization/0.5/case-package.json | `f6e6c11c2e84ddf5c429b2631b57318530606de30d4ee46388b7634f8b83ef9d` |
| functional-personalization/0.5/manifest.json | `fddb7bbbb036b2054126f65fd034656b52b0178dd33ae6e0615c904607746722` |
| functional-personalization-runtime/1.2.0/manifest.json | `8e2077bf27a87748102951cb6a1a444139134f6aba5901f339b7169ea60d4d56` |
| providers/deepseek/v1/manifest.json | `a9b20456f413a8828ee2cca47356490ae98844542c8ad31c015f937abe951c8c` |

### Основание тестового допуска

Публикация catalog выполняется существующим lifecycle только внутри новой owned-БД.
`m5_catalog_integrity/1.0.0`, policy checksum
`3e8e242ffab96f89e88b7974f9b51bcbd70f8acfe79f96b9de741554619c4691`.
Требуемые scopes, evidence checksum и точный case_ref проверяются admission.

| Scope | Evidence checksum |
| --- | --- |
| case_format | `ab31c00af1831d461143984d2586c21ca116acc4894d00b6d24de4441e5ad6d6` |
| case_dialogue | `a31e77c8a07167442996adfca5dcc4d3d8b1b155aabea0f3d63b2f06178753b3` |
| assessment_situation | `cee75c7de0a138ec73e5294af2706c5171c898739d413eff8570825433d2eb0c` |

Payload: eligibility `user_admission`, usage_scopes `["assessment"]`,
case_ref `CASE.SPEC.02/v0.6/179fa0f8…`, base_role `specialist_expert`, result PASS.
Обычный product flow имеет usage scope assessment; политика допускает там только
origin.type human_review. Fixture явно указывает
`synthetic-fixture:assessment-first-case/1.1`, `synthetic=true`,
`methodology_approval=false`. Исходный Case QA — **явная тестовая подстановка**.
Это технические assertions тестовой установки,
не свидетельство реального человеческого review и не методологическое согласование.
Ограничение этого моделирования раскрыто; policy и продукт ради теста не менялись.
Реальный tester/challenger выполняют новый независимый допуск сгенерированной AS.

### Причина прежнего LLM_CALLS=0 и null prompt ref

Прежний full-path seed копировал статический `e102_controlled_catalog` из
`cases/competencies_4k/1.1`. Для таких Case ID штатная очередь корректно не включает
functional preparation. Теперь диагностический catalog содержит `CASE.SPEC.02`:
runner/seed → `path29-browser-specialist/1.0` → точная configuration → catalog
`path-start-functional-diagnostic/1.0` → `CASE.SPEC.02 v0.6` →
ProductCyclePreparationQueue → functional generator/tester/challenger.

`prompt_bundle_checksum=null` был дефектом fixture: переменная `other` содержала
результат create_configuration до publication. В БД publication уже записала
checksum, но ProgramDefinition построили по устаревшему объекту. Seed теперь
использует возвращённую опубликованную configuration; browser проверяет непустое
и равное значение. Опубликованные старые строки не переписываются.

## Реализация и соответствие первоначальному заданию

| Пункт | Реализация | Проверка и evidence | Остаток |
| --- | --- | --- | --- |
| 1. Фактический контур | SSH машина; чистый exact SHA; localhost maintenance DB; реальный Chromium/provider | preflight.json, code-identity.json; PostgreSQL connect/CREATEDB и Chromium launch | Нет |
| 2. Переиспользовать средства | test_stand create/bootstrap/destroy; PATH29 harness; отдельная minimal full-path ветка seed | source-provenance.initial_counts: users=1, остальное=0; полный DB/browser сценарий | Общий legacy seed сохранён только для прежних тестов |
| 3. Постоянный профиль | assessment-first-case/1.1, AGENTS.md, tests/README.md | ссылки и читаемый профиль; защищённый env 0600 | Профиль в рабочей ветке, main не менялся |
| 4. Действительный путь | UI/API/реальная БД: superadmin → org/connection/admin → questionnaire/member/assignment → acquaintance/profile/prepare/start | browser spec, receipt, screenshot; три независимых contexts, controlled email | Внешняя доставка почты вне области |
| 5. Реальный LLM | DeepSeekGateway; generation + все final tester/challenger batches + конечный repair admission | unique operations, provider contract/model/usage; запрет статического fallback | Tokens malformed JSON retry доступны не полностью |
| 6. Повторяемая команда | scripts/assessment_first_case.py; env-file, preflight, итог/failure, штатный destroy | run/runner-result/cleanup JSON; step и точный API error в failure receipt | Последняя диагностика дошла до admission INCOMPLETE |
| 7. Честные статусы | READY машины отдельно; failure шаг/ожидание/факт; один hash для однотипной ссылки | source→candidate→snapshot→runtime/DOM; исторический FAIL сохранён | PATH-START-01 не исполнялся |
| 8. Сдача настройки | профиль/код/тесты/evidence/откат в одной ветке и ZIP-пакете | commits.bundle, оба diff, MANIFEST.json и автономный VERIFY.py | CI/review/merge/deploy отдельно |

## Завершение после независимой проверки cf6175e

Основание: владелец подтвердил VERIFY.py (50 файлов), восстановление Git bundle,
19 адресных Python и Node persistence test; поручил исправить только два дефекта
harness. Это не разрешение исполнять PATH-START-01 или исправлять продукт.
Восстановление БД и расследование исключены. Все восемь стоп-условий workflow —
«нет»: нет изменения предметного смысла/API/схемы/публикаций/прав/границ deploy,
нет новых операций удаления, миграций или неподтверждённых норм. Откат — revert
только доработки harness; прежние evidence и guards сохраняются.

Прочитаны: прежний отчёт/профиль и тесты на cf6175e, README/CONTRIBUTING,
workflow/matrix/artifact recipe/review checklist, архитектурный context 1.0,
Registry/Change 01 README и task manifest (выбранный комплект не изменяется).
Применимый технический источник допуска —
`Api/m5_functional_tester.py::aggregate` (PASS и PASS_WITH_WARNINGS допускают
участника), `Api/m5_functional_generation_service.py::prepare` (конечные
generation/tester после repair). Источники продукта только прочитаны, не изменены.
Неизвестное: первопричина исторического INCOMPLETE — по-прежнему UNKNOWN.

1. `summarize_runs`: наличие receipt больше не равно завершению. Проверяются
   actual process exit (отдельный `process-result.json` для новых run ID), completion
   после всех assertions/cleanup, run ID/hash receipt, отсутствие любых failure
   artifacts, структура/связи pre-start и final receipts, screenshot и ownership
   cleanup. Пустые/повреждённые данные, отсутствие completion, nonzero exit,
   недоступность validator и пустой набор runs дают FAIL. Общий runner exit тоже
   ненулевой, даже если child завершился 0, но evidence недостаточно. В смешанном
   наборе индивидуальные process records сохраняют разные результаты прогонов.
2. `verifyPreparation` вынесен в общий чистый Node-модуль, используемый без копий
   browser и Python summary. Принимаются только PASS/PASS_WITH_WARNINGS и boolean
   `admitted_for_participant=true`. Обязательные generation/tester/challenger,
   final repair/generation ID, ownership операций, candidate/compiled Case/snapshot/
   execution/participant refs сохранены; отсутствующие hashes не сравниваются как
   «undefined равно undefined». Pre-start → saved/presented AS проверяется тем же
   модулем. INCOMPLETE/FAIL/REVIEW_REQUIRED и недопущенная AS запрещены.

Регрессии не используют БД или LLM. `first-case-success.json` содержит явно
синтетические технические значения и служит только проверке validator. Это не
реальное предъявление AS, human review, методологический допуск или LLM PASS.
Исторические JSON/receipt/cleanup не переписываются; старым прогоном не добавляется
выдуманный completion. Текущие ошибки harness **не объявляются причиной**
PREP-DIAG-01: доказательства такой связи отсутствуют.

Изменены только runner, browser validator/completion, его fixtures/unit-регрессии,
профиль/tests README/отчёт/STATE и упаковщик (добавлен diff после cf6175e).
`scripts/test_stand.py`, `tests/conftest.py`, `Api/`, `assessment_definitions/`
остаются byte-identical cf6175e; защита постоянной БД от cleanup сохранена.
Новые результаты и SHA проверенного кода фиксируются в
`evidence/assessment-contour-2026-11-04/harness-regression/verification.json`.
Применимость прежних проверок: provenance/seed/DB export/lifecycle и их первичные
факты переиспользованы без изменений; логика summary/validator проверяется заново.

## Проверки

- `/Users/vadim_bogachev/Developer/4K/.venv/bin/python -m pytest -q -m "not integration and not e2e and not llm"`:
  PASS 704, 318 deselected, 65.74s на 9e659bd; переиспользуется для неизменённых
  collector/persistence/seed. Runner и preparation validator после cf6175e
  проверяются новым набором ниже; прежний PASS не подменяет их регрессии.
- `… -m pytest -q -m e2e tests/e2e`: PASS 106, 12 deselected, 27.94s.
- Адресные stand/evidence tests после всех исправлений выгрузки: PASS 19.
- `node --check tests/browser/path29-participant.spec.mjs`, py_compile изменённых
  Python и `git diff --check`: PASS.
- Независимая offline проверка сохранённых evidence: source file raw hashes,
  полный Case JSON, package import envelope, все QA payload checksums, prompt refs,
  10 уникальных операций и отсутствие AS/start при отказе — PASS.
- Static functional package verify-only: ранее PASS, 9 Cases/55 targets; файлы
  пакета не менялись. Это не методологическая приёмка.
- Изолированный DB/browser диагностический путь на реальном provider: итог ниже.
  Полный DB integration набор не повторялся: runtime/схема не менялись, изменённый
  fixture-путь проверяется реальной новой БД в browser.
- Бесплатная регрессия существующего PATH29 с gateway=1 на отдельной новой БД:
  PASS 1, 27.2s; проверены явный start и дальнейший legacy flow. Это не real-LLM
  доказательство нового полного сценария и не заменяет его отказ admission.
- Полный CI NOT_RUN: ветка не передавалась в PR, merge/deploy не выполнялись.

## Заключительная регрессия достаточности диагностики перед cleanup

Новых платных вызовов нет. На SHA 9e659bd выполнена команда
`/home/vadim_bogachev/projects/Agent4K-Test/.venv/bin/python tests/assessment_first_case_export_regression.py --directory /home/vadim_bogachev/evidence/assessment-export-regression-9e659bd`
с STAND_ADMIN_URL из защищённого окружения. Это отдельная отрицательная fixture:
в новую owned-БД вставлена синтетическая failed operation, реальные generation,
admission и browser onboarding не исполняются. Причины этой fixture не переносятся
на PREP-DIAG-01.

Результат PASS, LLM_CALLS=0. Последовательность проверена фактически:

1. Создана `product4k_pytest_1a8fadedc38a434ba26cac9ff9367e56`.
2. Штатный handler `tests.path29_browser_app.path_receipt()` прочитал из БД
   отрицательный результат и выполнил исправленный collector.
3. Общий с browser runner `receipt-file.mjs` выполнил write/fsync/readback.
4. При существующей БД сверены candidate checksum/ref, input snapshot checksum,
   preparation/generation operation ID, три check ID, статусы и безопасные причины.
   Сырые prompt/response/key sentinel-поля не попали в JSON.
5. Выполнен штатный `test_stand.py destroy` после проверки owner marker, без FORCE.
6. После DROP JSON читается с тем же SHA-256
   `163083b768dbdcdf2599934bfc4784909244c59d099c7f569a475ad8aed6160a`.

Сохранённые статусы fixture: NOT_RUN, TECHNICAL_ERROR, INDETERMINATE; причины
полностью видны в `export-regression/export-receipt.json`. Первичные доказательства:
`export-before-cleanup.json`, `regression-result.json`, `run.json`, `cleanup.json`,
`code-identity.json` в том же каталоге. Это подтверждает persistence, не причину
исторического отказа. Старая выгрузка не переписывается и не дополняется домыслами.

Дополнительно `node --test tests/unit/test_assessment_receipt_file.mjs` — PASS 1:
terminal/running distinction, ошибка записи, file mode 0600, readback. Python
stand/evidence subset — PASS 19. В full-path runner при отсутствии сохранённого
terminal receipt cleanup откладывается, а owned-БД/state сохраняются для разбора.

## Diff после 4bab723 и доступный пакет передачи

Все изменения после реального прогона относятся к настройке и доказательствам:
в 694f9c8 — completeness export/failure screenshot/llm annotation и отчёт;
в 9e659bd — candidate_ref, явная UNKNOWN-метка отсутствующих details, общий durable
persistence, guard перед cleanup и бесплатная DB-регрессия; далее — упаковщик и
первичные результаты. `Api/`, методология, admission, repair, M0–M8 не менялись.
После cf6175e добавлены исправления итогов/validator harness; дополнительный diff
`diff/after-cf6175e.patch` отделяет их от уже принятой независимо части настройки.
Полный машинный diff хранится в пакете как `diff/after-4bab723.patch` и `.stat.txt`.

`scripts/package_assessment_contour.py` строит пакет только из committed Git bytes
чистого HEAD. ZIP содержит профиль, runner/fixtures/tests, первичные source-provenance,
code-identity/run/runner-result/cleanup, оригинальный отрицательный receipt,
бесплатную регрессию, точные исходные JSON, Git bundle и diff к main/4bab723.
MANIFEST.json содержит final SHA и hashes файлов. VERIFY.py проверяет пакет
стандартным Python без проекта, БД или секретов. Внешний .zip.sha256 контролирует ZIP.
Пакет и краткая инструкция передаются в «Загрузки» владельца, отдельно от worktree.
State/env/passwords/keys и сырые prompts/responses в allowlist упаковщика не входят.

## Диагностические результаты и очистка

Повторяемость без LLM: на чистом `a4a2157` создана новая
`product4k_pytest_1b1a69b2dd8843939107833b6ef88d46`, минимальный seed PASS,
owner marker проверен, DROP без FORCE, БД/state отсутствуют.
`bootstrap-repeat-run.json` и `bootstrap-repeat-cleanup.json` сохраняют доказательство.

Первый заключительный прогон `a4a2157`:
`product4k_pytest_03bebcfdecb749d58d32cc70404dae6f`, admission PASS,
остановка **до старта**: collector ошибочно хешировал candidate по snapshot-контракту
с LF. Это ошибка harness, исправлена в `4bab723` с regression; продукт не менялся.
11 завершённых HTTP-вызовов, из них один JSON retry; БД штатно удалена.
Не выдаётся за продуктовый дефект или успешный старт.

Старый receipt `path-start-01-v1.1-functional-receipt.json` сохранён как исторический:
он заканчивается prepared/admitted и содержит 21 ссылку на 20 уникальных операций.
Повторная ссылка на repair не увеличивает число operations и tokens.
Новый collector дедуплицирует operation_id и сохраняет полный после-start receipt.
Старые source/fixture доказательства переиспользованы; новый платный прогон требуется
потому, что БД старого прогона удалена и недостающий start readback не восстановить.

### Законченная диагностика на 4bab723

Настройка работает; реальный сценарий остановлен штатной подготовкой:
`M5_FUNCTIONAL_AS_NOT_ADMITTED:INCOMPLETE`, операция
`c570a030-a47a-4eed-81f9-37c92e1441d8`, attempts=1. Создан новый
`product4k_pytest_f2735772affe47b2a3b49dddb2e4fa4e`; код clean, schema/seed READY.
Первый неуспешный шаг `real_llm_preparation`:
ожидались допуск конечного кандидата и сохранённая AS; фактически operation failed,
AS отсутствует, Cycle/Session prepared, started_at=null, оценочных ответов 0.
Start и предъявление первой AS в этом прогоне **NOT_RUN**: серверный admission
не разрешил продолжение. Runner exit 1 не превращён в PASS продукта.

Вызваны generation, 5 tester batches, 4 challenger batches: 10 уникальных
operations и 11 завершённых HTTP-запросов (один JSON retry). Сумма длительностей
завершённых provider-запросов 166130.47 ms. Доступные usage по сохранённым ответам:
711318 prompt + 36509 completion = 747827 tokens; usage первого malformed JSON
ответа не сохранён продуктовым trace, поэтому это не полный расход всех 11 запросов.
Repair не запускался: текущий алгоритм запускает его при blocking/deterministic
failures, которых в этом результате нет; INCOMPLETE отклоняется без такого repair.

Точная цепочка фактической БД:

- ProgramDefinition id=1, `path29-browser-specialist/1.0`, definition checksum
  `50ac188a25becdcebdd48f363dcdab513b4757a98929faf395789ff5051252af`;
- configuration id=3, `path29_browser_explicit_second`, published;
- в обеих ссылках prompt bundle
  `9b572bee4b990052f03909822aa995666245e6155170a0eb04547381206a4688`;
- catalog id=1, `path-start-functional-diagnostic/1.0`, manifest checksum
  `2c798ab2eb27748de6127f32aeba8393d6934f811d1e5d237c455f799ede744b`;
- CaseVersion id=2, `CASE.SPEC.02 v0.6`, `179fa0f8…`, runtime_rule_version_id=1;
- Cycle `571381f8-bc3b-41fb-8e3a-d921923dd10f`, profile id=1,
  owner_user_id=3, organization_id=1;
- candidate hash и его независимый пересчёт равны
  `5754161d86d31192ce1eca6c0f20d7fd3eb6b0884730379953675d4f370f1fad`.

Evidence в `docs/evc/evidence/assessment-contour-2026-11-04/`:

- `source-provenance.json`: Case JSON, все source/QA checksums и minimal counts;
- `preflight.json`, `code-identity.json`, `run.json`: точная машина/код/owned run;
- `final-failure-receipt.json`: реальные стадии/provider usage, refusal, отсутствие AS/start;
- `preparation-blocker.png`: участник видит отказ и тот же operation ID;
- `runner-result.json`: exit 1, completed requests, результат и cleanup;
- `cleanup.json`: точный owner проверен, DROP без FORCE, database/state absent=true;
- `bootstrap-repeat-{run,cleanup}.json`: независимое повторное создание/удаление;
- `failure-a4a2157/failure.json`: прежняя собственная ошибка harness не скрыта.

После реальной диагностики код менялся только для более подробной выгрузки
`incomplete_checks`/прямого failure screenshot и явной `llm` annotation; это покрыто
адресными regression/syntax checks без новой платной генерации. Браузерные переходы,
seed и продуктовая подготовка относительно проверенного 4bab723 не менялись.

Фактически проверенная команда, cwd `/home/vadim_bogachev/worktrees/assessment-contour-final`:

```sh
/home/vadim_bogachev/projects/Agent4K-Test/.venv/bin/python \
  scripts/assessment_first_case.py \
  --env-file /home/vadim_bogachev/projects/Agent4K-Test/.env \
  --python /home/vadim_bogachev/projects/Agent4K-Test/.venv/bin/python \
  --directory /home/vadim_bogachev/evidence/assessment-contour-complete
```

Настройка предъявляется как реализованный диагностический контур, достоверно
зафиксировавший препятствие. Новый успешный LLM старт не заявляется. Уже полученные
исторические screenshots/PASS переиспользованы только в своём фактическом объёме.

## Продуктовый остаток для следующего пакета

- `PREP-DIAG-01`: обязательный functional tester возвращает INCOMPLETE для
  CASE.SPEC.02; точный operation, expected/actual и screenshot выше. Отдельный
  check_id в выгрузке 4bab723 отсутствует: collector тогда не включал
  `incomplete_checks`. Его export исправлен и проверен regression без новой LLM;
  утраченное содержимое удалённой БД не реконструируется. Корневая причина
  неполноты конкретной проверки остаётся задачей следующего пакета, а не
  доказанным дефектом алгоритма admission. Повторный платный прогон ради PASS не сделан.
  Машинная карточка `PREP-DIAG-01.json` фиксирует `root_cause=UNKNOWN`, null для
  конкретных check ID/status/reasons, фактический operation/candidate и no-start.
- Ранее CASE.SPEC.01 не прошёл independent admission после предусмотренного repair
  (`M5_FUNCTIONAL_AS_NOT_ADMITTED:FAIL`, 18 операций). Причина качества требует
  отдельного анализа; fail-closed поведение исправным runtime не опровергается.
- Product trace сохраняет usage успешного последнего JSON-envelope ответа, но
  не usage отвергнутого malformed envelope. Реальные completions считаются по
  безопасным server-log строкам, доступные tokens помечаются своим объёмом.
- Синтетический origin в assessment-контракте отражает test fixture, а не реальный
  human review. Для отдельного real-provider QA usage scope потребуется продуктовая
  постановка; текущая настройка эту policy не расширяет.

## Риски и откат

Конфигурация: постоянный protected env, allowlist, ephemeral пароли; секреты в
evidence не выгружаются. Схема: без изменений/миграций. Deployment: не выполнен.
Безопасность: cleanup только по точному state/owner marker, без FORCE.
Откат: вернуть адресные changes настройки либо revert её commits; сохранить
диагностические evidence. Общие БД/пользователи/методология не затрагиваются.

Ревью EVC: scope соответствует настройке; схема/runtime/публикации общих источников
не изменены; регрессии собственных ошибок есть; source и method admission различены;
секреты и state не включены в evidence. Полный CI и человеческое review до merge
остаются внешними gates. Блокеров передачи самой настройки нет.

Следующий шаг — приёмка настройки владельцем; PREP-DIAG-01 и PATH передаются в
последующий продуктовый пакет. Новых решений для исполнения текущей настройки не нужно.
