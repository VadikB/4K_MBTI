# PATH-PILOT-PROGRAM-01 — проект выпуска программы и итогового PATH

Актуализация05.11.2026 после отдельного решения владельца:
**PUBLISHED_READBACK_VERIFIED**, `specialist_pilot@1.2`, id2/publisher4,
на неизменённом main/test e63eba6 /2.0.66. Free retirement SQL29 PASS,
fresh scoped schema/source preflight PASS, existing publisher1call/exit0,
exact receipt independent validation PASS. Backend908 PASS.
[Полный итог](../tasks/pilot-program-release-preparation.md) и
[первичный readback](../evidence/pilot-program-publication-execution/publication-result.json).
Подключений1.2 —0; activation/retirement/paid PATH нет. Free bootstrap именно нового
published receipt теперь **PASS_BOOTSTRAP_ONLY**, run5d4f68db…; exact sources/minimal
counts/cleanup/повторная offline summary PASS.110 unit PASS. Первая операционная
попытка без PYTHONPATH остановилась до БД и сохранена; исправлена только команда.
Следующее разрешение paid run остаётся отдельным; исполнение из чистого checkout
того же e63, не из deploy checkout с сохранёнными untracked assets/env-backup.
Ниже сохранён исторический проект3385145/f211e71; его прежние PENDING/BLOCKED
не являются текущим статусом публикации и не подменяют новый exact receipt.

05.11.2026. **OFFLINE_PROPOSAL_VALIDATED / EXECUTION_BLOCKED**.
Это подготовленный проект, не опубликованная ProgramDefinition, не активация
рабочей программы и не разрешение платного вызова.

Продолжение: пользователь отдельно разрешил бесплатный fix harness —
[PATH-PILOT-HARNESS-01](../tasks/pilot-program-harness.md). Ниже таблица §3 и
offline-verification относятся к исторической базе3385145/f211e71, на которой
дефект был воспроизведён. Текущее исправление и проверки передаются новой карточкой;
старый `VERIFY.py` предназначен для checkout f211e71, не для проверки изменённого
harness. Новая публикация/readback/paid PATH этим продолжением не разрешены.

## 1. База и уже принятые решения

Код: `main 3385145201d5d365e08e9e8a6a6fb7e12a0aa258`, приложение **2.0.65**.
[PR #170](https://github.com/VadikB/4K_MBTI/pull/170) принят человеком и слит;
[итог EVC](https://github.com/VadikB/4K_MBTI/pull/170#issuecomment-6658874775)
содержит CI и deploy/readback. Это последний подтверждённый выпуск, не новый
remote/deployment readback в этой подготовке. Готовые профиль и runner находятся
в этом main; их не нужно восстанавливать из старой ветки настройки.

Продуктовые P1–P3 и методологические M1–M4 уже приняты по exact v0.1:
payload `883c025cfa0ea43ad17922bc4818f05a0aaaa62bf02817690a3d07f171cfec06`,
[решение](../evidence/path-pilot-owner-decision-2026-11-05.json).
Реализация T1 выпущена отдельно. Новых решений о содержании здесь нет;
повторно утверждать неизменённый план не требуется.

M2 остаётся полным: **61 Indicator**. План пилота — **39**, вне плана — **22**;
55 исходных условий наблюдаемости, не 55 полученных наблюдений.
Маршрут: **02 → 03 → 04 → 07 → 05 → 01 → 06 → 08**.
SPEC.09 остаётся в каталоге, но не автоматическим резервом или заменой.
Время: **7200 учитываемых секунд / 259200 секунд календарного окна**.
Нет обещания пройти восемь Cases или фактически наблюдать все 39 целей.
План, реальная возможность, Evidence, IA и результат не отождествляются.

## 2. Конкретный кандидат, пока без публикации

Предлагается новая версия **`specialist_pilot@1.2`**. Номер предложен агентом,
а не утверждён владельцем; его свободность в рабочей БД сейчас UNKNOWN.
Версия приложения остаётся 2.0.65: это не новый выпуск runtime-кода.

Полный воспроизводимый рецепт —
[program-1.2.proposed.json](../evidence/pilot-program-release-plan/program-1.2.proposed.json).
Это документальный рецепт, **не вход нового runtime/import-формата**: существующий
builder разворачивает полный snapshot, существующий publisher сохраняет его в
`source_refs_json.pilot_plan_admission`. В документе нет присвоенного DB id,
унаследованного published_at или утверждения, что новая версия опубликована.

| Поле | Значение / основание |
| --- | --- |
| code / version | `specialist_pilot` / предлагается `1.2` |
| name / assignment_ref / mode | `Пилот 4К · 9 кейсов` / `specialist-pilot` / `dialogue`; без изменения согласованного baseline |
| configuration | `11`, `specialist_pilot_v1`, published; methodology version id2, scenario version id1 |
| catalog | id2, `specialist-pilot@1.0`, девять Cases |
| catalog checksum | `0008d020cbeb8b06ef5d38ad1eaf136fab8dc42728d98c2d5ec275476a6c25a0` |
| role | id2, `specialist_expert@1`, `c5c2234f9fdd237e14024ea6939e3bc5561fd27bf4fac416a52196dec79cbe8f` |
| prompt bundle | `9b572bee4b990052f03909822aa995666245e6155170a0eb04547381206a4688` |
| полный M2, исходный файл | `ac2914422dbce427616d489821db98572b702a8e491879b6758d9387eebc511c` |
| admission source | `assessment_definitions/planning/specialist_pilot_admission/v0.1/manifest.json`, draft offline source |
| admission snapshot | `daa715b153f16e9ebc4ea6744a1c8541c5e269e248bba4b5c37723571e6ccfce` |
| новая ProgramDefinition, после материализации | `b4e8270fd10436c417d7b40b8be8049dc2e9329f42a1ffa6d725877480d04718` |

Checksum ProgramDefinition посчитан существующим `definition_checksum` по полному
snapshot и всем полям кандидата. Он не обязан совпадать с hash snapshot или файла
рецепта. Изменение номера, имени или refs требует нового пересчёта и review.
Published `specialist_pilot@1.1` с checksum
`07576484b6c6467fd5fc7047cb1686a2f952532a893660375984373bab87f58c`
не переписывается. Все CaseVersions, их 27 исходных QA, M0–M8 и prompts неизменны.
Точные девять версий/Case checksums/QA JSON находятся в сохранённом
[source receipt](../../../tests/browser/fixtures/path-start-release.json).
Это исторический readback источников на `7221671`, не сегодняшнее чтение БД.
Новый human review этими проверками не заявляется.

## 3. Препятствия, обнаруженные до расхода tokens

| ID | Факт на базе 3385145 | Необходимое действие до итогового PATH |
| --- | --- | --- |
| SEED-01 | `seed_release()` вызывает `reserve_release_ids(..., 'assessment_program_definitions', ...)`, но allowlist этой функции не содержит таблицу. AssertionError воспроизведён до первого SQL на запретительном fake connection | Адресное исправление harness и позитивная регрессия program ID reservation; сохранить ownership, запрет чужих/занятых ID. Затем бесплатный owned bootstrap |
| SOURCE-01 | Runner читает фиксированный source receipt `1.1`; runtime разрешение новой версии автоматически туда не попадает | После разрешённой публикации сохранить/проверить exact-version source receipt. Не редактировать старый receipt, выдавая офлайн-кандидата за published readback |
| BROWSER-01 | `path29-participant.spec.mjs` дополнительно требует version=`1.1` | Сравнивать с точной версией/checksum проверенного source receipt, не с latest и не с одним наличием snapshot; добавить регрессии |
| AUTH-01 | Публикация новой версии, постоянное подключение и платный PATH не разрешены | Получить раздельные точные решения ниже после бесплатной готовности harness |

Первое — подтверждённый дефект тестового инструмента, второе — ожидаемый незавершённый
release input, третье — текущая привязка browser-проверки, требующая обновления для
новой версии. Они **не доказывают** сбой продукта/AS admission и не объясняют ни
исторический PREP-DIAG-01, ни прежний содержательный отказ AS. В этой design-only
подготовке исправления runtime/runner/fixtures не выполнялись; код не менялся.

## 4. Последовательность исполнения после решений владельца

### A. Бесплатная готовность инструмента

1. Исправить SEED-01/BROWSER-01 и обеспечить явный выбор нового проверенного receipt
   в существующем `published-pilot`, не создавая новый runtime. Прежний 1.1 receipt
   сохранить. Exact version/checksum источник не выбирается автоматически по latest.
2. Выполнить адресные регрессии, backend и применимые HTTP/integration/browser
   проверки EVC; реальные provider calls запрещены. БД — только новая owned test/pytest.
   Для bootstrap до постоянной публикации допустима явно помеченная **синтетическая
   модель будущей метаинформации программы**, но не новый human QA и не published receipt.
3. Довести изменение harness до штатного review/CI/выпуска отдельно. Если меняется
   выпускаемый продуктовый код, номер нового приложения требует решения владельца;
   текущая подготовка его не назначает. Зафиксировать точный SHA фактического runner.

### B. Отдельно разрешённая публикация новой версии на test

Рекомендуемая область следующего разрешения: только **новая ProgramDefinition 1.2**
в рабочей test-БД, указанной серверным
`/home/vadim_bogachev/projects/Agent4K-Test/.env`. Это постоянная запись и
появление версии в списке published программ; **не подключение существующих
организаций, не default-конфигурация и не разрешение оценивания реальных людей**.

Перед записью нужен свежий read-only preflight: точный runtime SHA/версия,
свободность `(code,version)`, отсутствие отличий baseline sources/config/catalog/
Case QA/roles и схемы, определённый полномочный publisher user id, сохранённый
PII-free readback исходного состояния и проверенная процедура остановки новых
подключений/retirement. Старый schema PASS переиспользуется только как baseline;
он не доказывает отсутствие последующего drift. Любое расхождение — STOP до записи.

Командный шаблон существующего publisher, **не выполнен**:

```sh
PYTHONPATH=. .venv/bin/python scripts/publish_assessment_program.py \
  --code specialist_pilot --version 1.2 \
  --name 'Пилот 4К · 9 кейсов' --assignment-ref specialist-pilot \
  --mode dialogue --configuration-code specialist_pilot_v1 \
  --role-code specialist_expert --publisher-user-id <AUTHORIZED_PUBLISHER_ID> \
  --pilot-plan-package assessment_definitions/planning/specialist_pilot_admission/v0.1 \
  --publish
```

Placeholder заменяется фактически проверенным числовым ID на сервере, не угадывается.
Без `--publish` этот скрипт всё равно подключается к БД и выполняет rollback;
это не offline dry-run. В подготовке запускался только `--help` с изолированным
окружением и `DB_POOL_MIN_SIZE=0`, не database validation.

После commit публикации: read-only export существующим
`tests.path_start_release_source --program-version 1.2`; независимый пересчёт
definition/snapshot/artifact checksums и полный source receipt. Published metadata
не восстанавливать из офлайн-рецепта. Нельзя использовать публичную UI-проекцию
`PUBLIC_REFS_NOT_EXECUTION_DEFINITION` для пересчёта полной ProgramDefinition.

### C. Отдельно разрешённый итоговый PATH

Рекомендуется **один** новый контролируемый платный run на свежей owned-БД,
а не на рабочей `agent4k_test`. Свежий опубликованный source receipt сначала
зеркалируется штатным seed, сохраняющим исходные Case QA без synthetic human_review.
Постоянная БД не является целью bootstrap, оценивания или cleanup.

Фактическая команда существующего runner после исправлений/проверки нового receipt:

```sh
PYTHONPATH=. .venv/bin/python scripts/assessment_first_case.py \
  --env-file /home/vadim_bogachev/projects/Agent4K-Test/.env \
  --python /home/vadim_bogachev/projects/Agent4K-Test/.venv/bin/python \
  --program-source published-pilot --db-admin-port 55432 \
  --directory /home/vadim_bogachev/evidence/path-pilot-1-2-first-case
```

Это шаблон будущего запуска, **сейчас не проверенная успешная команда для 1.2**.
Его нельзя запускать на текущем fixture1.1 и объявлять новым PATH. Перед платным
запуском — тот же профиль с `--preflight-only`, затем `--check-bootstrap` в другой
новой evidence directory, обе команды без LLM. Рабочие секреты читаются только
allowlist-механизмом существующего runner в память, не выводятся и не экспортируются.

Сценарий: минимальная загрузка (один суперадмин, ноль организаций/назначений/профилей/
Cycles) → отдельные browser contexts суперадмина/администратора/участника → создание
новой организации и подключение точной версии → контролируемая почта `@example.test`
→ анкета/назначение/знакомство/frozen profile → реальная подготовка → gate →
**явный первый start → серверный readback → первая та же AS → 0 оценочных ответов**.
Подключение программы и scoped timing в этом шаге происходят только в owned-БД.

Проверки: exact tenant/connection/assignment/profile/questionnaire/config/catalog/
Case/QA/role refs; полный M2 и binding плана; оба времени с собственным program scope;
generation, все необходимые tester/challenger и terminal repair links; конечный
кандидат → compiled Case → сохранённая AS → предъявленная AS. PASS или
PASS_WITH_WARNINGS допустимы только при `admitted_for_participant=true`.
INCOMPLETE/FAIL/false/неизвестный LIMITED блокируют успешный итог.
Плановая цель не превращается в фактическое наблюдение; оценочные ответы не отправляются.

Отказ: сохранить terminal diagnostic receipt, check IDs/statuses/safe reasons,
candidate/batch/operation/AS links и фактический незавершённый шаг; **остановиться
без повторного платного run, новых prompts, изменения repair или admission**.
20 provider operations / приблизительно 1.505 млн tokens прежнего run — только
исторический ориентир, не гарантированный потолок и не разрешение расхода.

## 5. Evidence, очистка и откат

До owned cleanup: `code-identity`, `run`, `source-provenance`, pre-start и final/failure
receipts, checks/lineage, start/runtime readback, DOM/screenshot, 0 answers,
completion/process-result/runner-result; общий write/fsync/readback. При незавершённой
операции или недоказанной выгрузке — `cleanup-deferred`, не DROP ради чистого PASS.
Штатный destroy проверяет точное имя/owner marker и удаляет только owned-БД/state.
После — cleanup readback и offline summary, не самовольная повторная генерация.

Сейчас DB-откат не нужен: подключений/записей/LLM0. Откат подготовки — убрать только
новые docs/evidence на этой ветке; исходные reviewed материалы и main не изменять.
Будущая published версия не удаляется и не редактируется. Если разрешат её выпуск,
до записи нужен проверенный порядок retirement/запрета новых подключений: trigger
разрешает `published→retired`, но готовый публичный retire endpoint/CLI в просмотренном
контуре не найден. Обещать исполнимый rollback одной несуществующей командой нельзя.
Рабочая активация существующей организации требует отдельного scope и плана возврата;
после v2 Cycles нельзя автоматически откатывать reader к2.0.64 или менять snapshots.

## 6. Решения для следующего этапа, без повторного утверждения P/M

1. Принять бесплатную техническую подготовку harness по SEED-01/BROWSER-01 и
   exact-version source selection. Её конкретный код проходит самостоятельные
   регрессии/review; нынешний runtime не меняется автоматически.
2. После её готовности: утвердить **программную версию 1.2**, публикацию только новой
   ProgramDefinition в server test-БД, полномочного publisher и проверенную процедуру
   retirement. Подключение существующих организаций остаётся запрещённым.
3. После exact published readback и бесплатного bootstrap: отдельно разрешить один
   оплачиваемый PATH по §4C с остановкой без повторов. Старое разрешение единственного
   run2.0.64 уже использовано и не покрывает новый запуск.

PREP-DIAG-01: историческая первопричина **UNKNOWN**, отдельный продуктовый остаток.
Расширение каталога и публикация CURRENT, новые нормы M6–M8 и результаты полной
оценки в этот проект не входят.

## 7. Фактическая проверка подготовки

[Offline audit](../evidence/pilot-program-release-plan/offline-verification.json):
snapshot/program checksum, существующий source validator и exact projection —
проверены; все sockets запрещены, DB/LLM0. Eligibility=True в offline projection —
явный технический вход, не новый human review или допуск конкретной AS.
[72 адресных Python-теста](../evidence/pilot-program-release-plan/addressed-python-tests.txt)
PASS на неизменённом коде базы3385145. Оба
[publisher --help](../evidence/pilot-program-release-plan/publisher-help.txt) и
[runner --help](../evidence/pilot-program-release-plan/runner-help.txt) — exit0.
SEED-01 воспроизведён без SQL; настоящий новый bootstrap и полный PATH NOT_RUN.
Полный runtime CI 2.0.65 переиспользован по PR170, новый CI для docs NOT_RUN:
push/PR/merge/deploy и artifact publication в этой подготовке не разрешены.
