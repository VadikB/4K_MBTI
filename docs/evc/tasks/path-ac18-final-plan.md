# AC18 — план одного окончательного real-provider PATH

**AC18 NOT_RUN. Разрешения его запуска, merge/deploy/публикации нет.** Отдельно
разрешены bump/push/PR/CI/review harness 2.0.70, см.
[карточку выпуска](path-harness-release-2070.md). Это не разрешение AC18.
PREP-DIAG-01 — отдельный исторический UNKNOWN.

## Код и условия допуска запуска

База: `3f42bba992e1a556e1961ca4abdaa0954a367153`, выпущенная 2.0.69/PR174.
AUTH/R10 закрыт, повторная release-задача для него не создаётся.
Сохранённый исходный handoff — `2fa1ed667707c8f146951c844b673b79fecd9e08`,
`codex/path-ac06-ac10-proof`; его пакет/первичные результаты неизменны.
Отдельно согласованный владельцем кандидат инструмента 2.0.70 подготовлен в
`codex/path-harness-2070`; точный source и финальный PR head фиксируются в
отчёте выпуска/передаче review. От handoff изменены metadata/build, docs/evidence
и viewport collector с тремя DOM регрессиями; Api/runner/артефакты прежние.
Этот локальный source **не является окончательным deployed SHA для AC18**.

Порядок: отдельный прямой допуск release → штатный preflight/согласованный PATCH →
push/PR/mandatory CI актуального head/base → human review → отдельный merge/test
допуск → deploy + server/public/entry/assets readback → фиксация **фактического
окончательного main/deployed SHA** → отдельное разрешение **одного** платного run.
Локальный SHA не подставлять вместо ещё неизвестного squash/deployed SHA.
При изменении кода/источников заново проверить применимость доказательств.

Чистый detached checkout окончательного SHA, отдельно от грязного server dist.
Не копировать `.env` в checkout. Никакой активации/переподключения рабочей организации,
публикации или изменения постоянной БД; read-only source/schema preflight перед
запуском, cleanup только marker-owned `product4k_pytest_<run_id>` без FORCE.

## Точные программа и источники

`specialist_pilot@1.2`, ProgramDefinition id2, assignment_ref `specialist-pilot`,
published; configuration11 `specialist_pilot_v1`; catalog2 `specialist-pilot@1.0`,
assessment; role2 `specialist_expert@1`.

- Program checksum `b4e8270fd10436c417d7b40b8be8049dc2e9329f42a1ffa6d725877480d04718`.
- Catalog manifest checksum `0008d020cbeb8b06ef5d38ad1eaf136fab8dc42728d98c2d5ec275476a6c25a0`.
- Configuration prompt bundle `9b572bee4b990052f03909822aa995666245e6155170a0eb04547381206a4688`.
- Methodology2 checksum `e6c88944af318033fbd76b18cc1b8eecb27b6a379df5fcdcdc82b9fa66f54c2c`.
- Scenario1 checksum `07c9a47f17da3a2f58f9f2752297c9ce337ffd453ff005af0bfaab373378666e`.
- Role checksum `c5c2234f9fdd237e14024ea6939e3bc5561fd27bf4fac416a52196dec79cbe8f`.
- Package2 checksum `b9e2889b5a7b19dda6b88ebec30bffba87cf76afc3df4cb14df10de0036eb7b0`.
- Runtime rules1 checksum `85900c2b9955c4f85996f55679f5d67cbc79c252c3bf570166cdef444ea1f757`.
- Pilot admission `specialist_pilot_admission@0.1`, snapshot
  `daa715b153f16e9ebc4ea6744a1c8541c5e269e248bba4b5c37723571e6ccfce`.

Полный M2=61 сохраняется. Только принятый concrete pilot plan39/22 вне плана,
маршрут02→03→04→07→05→01→06→08;09 не автоматический резерв. Все AS имеют собственный
admission; LIMITED сам по себе не разрешает start. Два времени — штатный scoped
источник (прошлый run:7200/259200 seconds), не новые локальные значения.

Cases01 v0.5 /02 v0.6 /03 v0.4 /04 v0.5 /05 v0.5 /06–09 v0.4;
exact content checksums и27 исходных QA находятся в byte-pinned published receipt:
[сохранённые bytes](../evidence/pilot-1.2-path/server-evidence/run/6364c771-80c7-4013-bad0-6fd7cc2db545/published-release-source.json).
SHA256 bytes `09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b`.
Новый live preflight сверяет именно эти refs/QA, не latest. Никакой синтетической
human_review подстановки в published-pilot/full PATH. Источники M0–M8 не меняются.

## Среда и существующая команда (сейчас НЕ выполнять)

Сервер `vadim_bogachev@178.236.26.203`, отдельный clean checkout выпущенного SHA;
Python3.12, npm ci/Chromium и системные зависимости, localhost PostgreSQL с
CREATE/DROP owned DB, свободный18861, HTTPS DeepSeek. Точный выбранный checkout,
Python/Node/Chromium/PostgreSQL версии и установленное число provider keys (без
значений) сохранить в preflight. Порт55432 — прежний maintenance port; подтвердить
актуальность и isolation до запуска, не использовать рабочую DB_NAME.

Из корня этого clean checkout, с НОВЫМ уникальным каталогом evidence:

```sh
PYTHONPATH=. /home/vadim_bogachev/projects/Agent4K-Test/.venv/bin/python \
  scripts/assessment_first_case.py \
  --env-file /home/vadim_bogachev/projects/Agent4K-Test/.env \
  --python /home/vadim_bogachev/projects/Agent4K-Test/.venv/bin/python \
  --program-source published-pilot --db-admin-port 55432 \
  --program-receipt /home/vadim_bogachev/evidence/pilot-program-1.2-wryr3q10/published-release-source.json \
  --program-receipt-sha256 09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b \
  --program-version 1.2 \
  --directory /home/vadim_bogachev/evidence/AC18_NEW_UNIQUE_RUN_DIRECTORY
```

Последний путь — именуемый перед разрешением новый owned output, не существующий
старый run. `--preflight-only` той же команды бесплатен; здесь не выполнялся на
сервере. Сам runner/selector уже использовался в принятом run2ff983f1… на e63eba6,
но это не доказательство нового final-SHA PATH. Проверенная локальная бесплатная
команда нового harness и результаты находятся в отчёте AC06/07/09/10.

## Действующие лимиты, без изменения правил

- Один runner invocation, Playwright workers1/retries0, реальный профиль9 Cases,
  одна подготовка/первый явный start, **0 оценочных ответов**. Никаких ручных повторов.
- Playwright real-provider timeout900000ms; terminal preparation wait600000ms;
  bootstrap/input subprocess180s. Это timeouts, не денежный потолок.
- DeepSeek `deepseek-flash`, endpoint и thinking из pinned provider contract v1.0.0.
  Functional generation/repair max_tokens32768 (temperature0.2/0.1);
  tester/challenger16384 (temperature0), каждый вызов timeout300s, batch_size8.
- Один штатный repair при предусмотренных blocking/deterministic failures и полный
  повтор обязательных tester/challenger для конечного кандидата. INCOMPLETE/FAIL/
  admitted=false запрещают успешный PATH. PASS_WITH_WARNINGS допустим только со всеми
  текущими связями/stages/admitted=true; правила не меняются ради успеха.
- Внутренний strict JSON допускает одну повторную попытку (всего2); transport может
  пройти configured key chain при сетевой/HTTP ошибке. Это существующие внутренние
  повторы, не разрешение нового полного run; отражать actual transport attempts.
- Provider concurrency default10/queue wait30s; фактический allowlisted override
  записать без секрета. Product queue lease10min с heartbeat; attempts/fencing
  readback сохранить, не переисполнять вручную при сбое.
- Прежний successful1.2 run:20 provider operations,1,523,716 total tokens;
  для CASE02 было33 tester checks/5 batches и32 protected/4 batches на candidate.
  Это ориентир, **не гарантированный верхний предел**. Общего USD/token cap у
  нынешнего runner нет; новый жёсткий бюджет требует отдельного решения/реализации.

## Evidence и экраны в ОДНОМ run

1. До LLM: exact code/branch/main/dirty refs, API/entry/assets/deploy, source hashes,
   receipt bytes, minimal counts users1/остальные0, runtime settings/limits (без
   keys), отдельные super/admin/participant contexts, controlled test mail.
2. Superadmin → organization/program; admin → questionnaire/confirmed revision →
   member/assignment; participant → consent/3 W02 answers → immutable profile →
   operation/plan. Потеря ответа/reload/readback и точные scope/time refs.
3. Mandatory generation/tester/challenger + если был repair: конечный кандидат,
   checks/status/reasons, unique operations/usage/model/prompt/input/checksum refs.
   Candidate→saved AS→presented AS, checksums только однотипных объектов.
4. Admission/readiness перед start; explicit start201, серверные timestamps,
   sameAS/profile/plan, participant DOM/payload checksum, assessment_answers=0.
   Read-only viewport capture и повтор назначения не добавляют Cycle/AS/ответов.
5. `preflight.json`, `code-identity.json`, `source-provenance.json`, exact source
   receipt, `run.json`, `source-to-runtime-receipt.json`, `first-case-receipt.json`
   либо failure/terminal receipt, completion/process/runner-result, safe server log,
   API/PG readback, screenshots/viewport metrics, cleanup receipt и независимый
   database-absent readback. Экспорт **до** cleanup, без state/cookies/passwords.
6. При содержательном/техническом отказе сохранить точный шаг/expect/actual/check IDs
   и причины; unknown обозначить UNKNOWN. При отсутствии terminal receipt cleanup
   отложить согласно существующей защите. Никакого force/start/admission обхода.

На 1440/320/390/768 тот же текущий backend/AS: superadmin program controls,
admin questionnaire (длинные сведения/пояснения), assignment с длинными именем и
должностью, participant ready notice/start и первая AS/input/pause/finish/submit.
Ничего не отправлять как оценочный ответ при screenshot. W02 questions уже имеют
действующие6-width/short-zoom200 checks; сохранить их в том же run, не генерировать
AS для каждой ширины. Доступность controls проверяется прокруткой и trial-action,
disabled состояние не подменяется. PNG подлежат визуальному review, не только
численным assertions.

AUTH/R10 release evidence129 browser/145 frontend на tree23f065… можно переиспользовать
для неизменённых auth/admin экранов и отрицательных feedback guards; это synthetic
HTTP presentation proof, не PostgreSQL/real provider. Новые AC06/07/09/10 закрывают
точные серверные/PG пробелы. Component viewport PASS проверяет новый сборщик, но не
качество AS/пилотный допуск. Исторический paid PASS e63eba6 подтверждает механизм,
не заменяет целый повтор на окончательном deployed SHA. Полного AC18 PASS пока нет.
