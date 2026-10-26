# STATE — Case / Cycle R00–R10

- Base: `b3bbdc9e78880879e1d4fc930ef8c9cc9f200524` (`origin/main`, приложение `2.0.28`).
- Ветка: `codex/case-cycle-r1`.
- Активная карточка: R10 — пилот C01/Sales завершён `AS_ADMISSION_FAIL`; зависимая
  серия остановлена по gate карточки.
- Завершённые commits: R00 — `aea9bf3`; R01 — `30fc6a0`; R02 — `420a315`;
  R03 — `e1d1dc0`; R04 — `2117b50`; R05 — `09b8944`; R06 — `bf3aeb7`;
  R07 — `dc781d9`; R08 — `b4070db`; R09 — `3506bd5`; R10 — evidence commit
  текущего head.
- Проверки R00 на рабочем дереве: `git diff --check` — PASS; ссылки/пути — PASS;
  YAML parse и release checker — PASS. Продуктовые тесты не применимы.
- Блокеры: `gh` отсутствует, поэтому PR остановленной ветки не подтверждён локально;
  R00 не блокирует.
- Проверки R01 на рабочем дереве: 30 unit/contract tests — PASS; package 0.5 build —
  PASS, 9 Case / 55 targets, checksum
  `4c127cbb8ed3573885cccdadfc9ae8199b6f266bd3f8077644b45a3d7c8e486c`.
- Ограничение R01: DB-сохранение композиции проверяется вместе с R02/R03 на
  изолированном PostgreSQL; real-provider — R10.
- Проверки R02: 31 unit/contract — PASS; 2 package/runtime PostgreSQL integration —
  PASS; 6 вариантов штатного product preparation/fencing — PASS. Runtime bindings
  `1.2.0` дают counts `1,0,3,3,2,6,0,6,2`; Case 02/07 остаются actorless.
- Решение R03 по identity: авторская пара `case_id/case_version` и её содержимое не
  переписываются; владение исполняемой записью задаёт
  `(package_id, case_id, case_version)`, runtime binding отдельно фиксирует checksum
  Case и source package version. Каталог и Cycle продолжают ссылаться на конкретный
  `case_version_id`; reader подготовки разрешает Case через frozen catalog membership.
- Inventory R03: доступен только изолированный synthetic PostgreSQL-контур; общая test
  БД и её неперсональные агрегаты не предоставлены, live migration не выполнялась.
  В изолированном контуре проверены установки `0.2 → 0.5` и `0.3 → 0.5`, по два
  пакета / 18 CaseVersion и раздельные реальные catalog relations.
- Проверки R03: 27 unit — PASS; 3 package/runtime PostgreSQL integration — PASS;
  16 product-path PostgreSQL integration — PASS; `git diff --check` — PASS.
  Повторный импорт идемпотентен, изменение содержимого существующего package version
  отклоняется, hashes старого пакета до/после импорта совпадают.
- Миграция/восстановление R03: перед применением на общей БД нужен адресный допуск и
  read-only inventory ссылок catalog/Cycle/AS/results. DDL только снимает две глобальные
  uniqueness и добавляет package-scoped unique index; откат приложения — вернуть
  предыдущий commit, не удаляя новые строки. Возврат глобальных constraints допустим
  лишь после retirement новых package memberships, без удаления истории и подмены hashes.
- R04, схема фаз: (1) короткая транзакция блокирует Cycle/AS, фиксирует неизменный
  assessee Turn, `m5_turn_operations.pending`, attempt token и state revision, закрывает
  collecting interval и открывает `blocking_system_wait`; (2) semantic/character provider
  вызываются без выданного runtime DB connection; (3) новая транзакция сверяет token,
  статус AS/Cycle и revision, закрывает wait и атомарно применяет decisions/materials/
  character turns/state, после чего сохраняет `applied`. Timeout фиксируется как `failed`
  и допускает fenced retry; смена состояния — `rejected_late`, без применения output.
- Восстановление R04: replay того же request возвращает сохранённый `applied`; `failed`
  получает новый attempt token/номер; зависший `pending` может быть перехвачен после
  двухминутного lease. Исторический participant Turn не удаляется. Откат приложения
  оставляет таблицу операций и интервалы аудита; незакрытый wait завершается штатным
  retry/операторским recovery, а не удалением Evidence.
- Проверки R04: 13 unit/HTTP — PASS; 3 runtime PostgreSQL integration — PASS. Отдельная
  trace через штатный `DeepSeekSemanticAdapter` с подставным transport подтвердила:
  во время вызова нет backend connection runtime-фазы в `pg_stat_activity`; timeout→retry
  даёт один Turn и attempt 2; concurrent pause даёт `rejected_late`; открытых blocking
  intervals после завершения нет. Real-provider не вызывался.
- R05, фазы потребителей:

  | Потребитель | DB до provider | Проверка при записи |
  |---|---|---|
  | M7 clarification | C54 payload/hash, boundary, AS/Cycle/time, mechanism input | тот же latest C54, payload hash, boundary и открытая AS |
  | M6 admission | точный C46 composition, final IA observations, material contexts, mechanism checksum | повторный `_inputs`, тот же composition и полный input hash |
  | M8 description | точный Results revision/payload, resolved evidence basis, два prompt packages | тот же immutable Results revision/payload checksum и request key |

- Routes и M10 orchestration используют detached entrypoints; прежние синхронные
  функции сохранены для совместимости внутренних/QA callers. Timeout clarification
  остаётся `WAIT_TECHNICAL`; admission processing failure и M8 descriptive failure не
  превращаются в содержательный результат или participant FAIL. Retry идемпотентен по
  ключу, новая попытка обработки использует новый recovery/regeneration key.
- Проверки R05: 35 unit — PASS; 35 исходных integration clarification/admission/M8 —
  PASS; 2 новых PostgreSQL phase traces — PASS; 7 HTTP — PASS; 16 product orchestration
  integration — PASS. Provider fixtures видели ноль активных DB contexts; M8 выполнил
  обе внешние фазы и сохранил точный `results_revision_id`. Real-provider не вызывался.
- Откат R05: detached entrypoints можно снять возвратом commit; созданные immutable
  C54/admission/Results/Report revisions сохраняются. Поздний output, не прошедший
  revision/composition fence, не публикуется и не требует удаления истории.
- R06, consumer map:

  | Consumer | Frozen dependency / resolution |
  |---|---|
  | functional generator/tester/repair | `m5_functional_package`, `m5_functional_protocol`, `m5_functional_repair` через Cycle manifest; refs/checksums входят в generation snapshot |
  | runtime event bindings | `m5_functional_runtime` через Cycle manifest и Case checksum/package-version binding |
  | M5 semantic/character/technical C45 | `m5_semantic_decision`, `m5_character_response`, `m5_technical_c45`, `provider_contract`; safe operation identity сохраняется в AS |
  | M7 planning/return/clarification | `m7_cycle_plan`, `m7_return_integration`, `m7_clarification`, `source_set`, `provider_contract` |
  | M6 Evidence/IA/admission/aggregation | `m6_evidence`, `m6_indicator_assessment`, `m6_substantive_admission`, `m6_cycle_aggregation`, `m2_methodology`, `source_set`, `provider_contract` |
  | M8 projection/description/validator/recommendations | `m8_report_projection`, `m8_descriptive_report`, `m8_recommendations`, frozen Results/evidence refs |

- Manifest schema 2 фиксирует новые prompt/runtime dependencies; default нового Cycle —
  functional package `0.5` и runtime `1.2.0`. Schema 1 читается через закрытую
  compatibility map только для четырёх ранее неименованных versioned prompt paths;
  произвольный fallback/current запрещён. Повреждение или отсутствие явно pinned path
  остаётся `CYCLE_DEPENDENCY_*` technical failure.
- Provider snapshot содержит requested provider/endpoint/model/thinking/response formats
  и checksum контракта, но не credential. Ротация ключа не меняет semantic identity.
  Reported provider model/revision сохраняется trace; веса за alias не объявляются
  воспроизводимыми.
- Проверки R06: 56 unit — PASS; 6 Cycle/runtime/package PostgreSQL tests — PASS;
  16 product-path integration — PASS. V1/V2 trace: старый Cycle после смены defaults
  создал следующую AS с semantic/character prompt `1.0.0` и runtime `1.1.0`; новый
  Cycle — prompt `v2`, package `0.5`, runtime `1.2.0`; provider checksum совпал,
  `api_key` в snapshots отсутствует.
- Откат R06: вернуть resolver/schema/defaults предыдущего commit; schema-2 manifests и
  AS остаются immutable данными. Старое приложение их не должно исполнять без поддержки
  schema 2; удалять или переписывать созданные refs нельзя.
- R07, диагностика `M6_CONTEXT_REFERENCE`: приложенный архив не содержит raw M6
  input/output отказавшей попытки, поэтому историческая причина не приписана по одному
  error code. Текущий resolver сохраняет ID предъявленных C45 Turns, events и materials
  без преобразования и исключает непредъявленные materials; `initial_presentation`
  передаётся отдельно и не является namespace context ref. Validator корректно
  отклоняет чужой/несуществующий ID и ссылку в будущее.
- Подтверждённый дефект R07 был в recovery-контракте: retry после
  `M6_CONTEXT_REFERENCE` не сообщал закрытый список разрешённых `{kind,id}`. Feedback
  теперь перечисляет только фактические `turn/event/material` IDs входа и запрещает
  speaker/fragment/BS/evidence/initial-presentation IDs, не удаляет ошибочный ref и не
  подменяет его произвольным допустимым. Prompt package и предметные правила не менялись.
- Проверки R07: 29 unit M6 Evidence — PASS, включая Unicode span, корректную цепочку,
  чужую/несуществующую/будущую ссылку и точный retry allowlist; 3 PostgreSQL
  integration — PASS: непустой Evidence readback, пустой/недостаточный bundle и
  timeout→failed attempt→идемпотентный retry. Тесты используют штатные C45/enqueue,
  без ручного INSERT Turn. Product API Evidence/IA входит в общий R09 path;
  real-provider остаётся задачей R10 и не объявлен PASS.
- Откат R07: вернуть изменение retry feedback; строгая валидация и сохранённые
  Evidence/IA не меняются. Исправление не требует миграции или публикации prompt.
- R08: `revise_prepared_parameters` приведён к семантике `create_plan`: статус зависит
  от покрытия/наличия route, но не от суммы `planned_max_seconds`. Плановые суммы 60,
  120 и 189 минут не урезаются и при полном покрытии остаются `READY`; неполное
  покрытие остаётся `LIMITED`. Число 189 не введено в runtime как порог.
- Pilot-120 readback на изолированной БД: опубликованная идемпотентная program revision
  для назначенной configuration разрешается как `7200/259200`, её revision/checksum
  попадают в новый Cycle; последующая revision не меняет начатый snapshot. Method
  default `3600` сохранён. Общая organization/program revision не изменялась: конкретная
  live organization/configuration не дана, поэтому live publication — NOT_RUN, без
  влияния на локальную реализацию и synthetic deployment-independent readback.
- Проверки R08: 10 PostgreSQL integration — PASS (включая 7199/7200/7201 секунд,
  calendar expiry paused Cycle и blocking wait); 1 browser — PASS. На 7199 collection
  разрешён, на 7200/7201 `assert_collecting` закрывает Cycle с
  `M7_TIME_LIMIT_REACHED`; UI показывает frozen budget `120 мин.`, не planned sum
  `189 мин.`. Pause/blocking wait не продлевают calendar deadline.
- Откат R08: вернуть одну формулу plan status и тесты; DB schema/данные не меняются.
  Уже начатые Cycle сохраняют свои frozen parameter snapshots.
- R09: единый application candidate `2.0.29`; version targets и hashed web assets
  синхронизированы. Предметные версии независимы: functional package `0.5`, compiler
  `0.5.0`, runtime bindings `1.2.0`, Cycle manifest schema `2`, M6 Evidence prompt
  `1.0.1`, SourceSet `2026-10-01`. SHA-256 manifest files соответственно:
  `fddb7bbbb036b2054126f65fd034656b52b0178dd33ae6e0615c904607746722`,
  `8e2077bf27a87748102951cb6a1a444139134f6aba5901f339b7169ea60d4d56`,
  `a0bb42457fe372abfcf0ff4c3c00a39e6ed78b969ccab70f3193b20667f3bb31`,
  `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8`.
- R09 выявил concurrent regression в detached M7 clarification: новая C54 могла
  выиграть fence во время provider-фазы; late output отклонялся, но orchestration
  повторно выбирала старую revision и аварийно прекращала drain. Теперь выбирается
  только newest interim C54; `M7_STALE_C54`/`M7_CLARIFICATION_STATE_CHANGED` остаются
  отказом публикации late output и запускают следующий orchestration pass. S10-A
  Report/PDF после исправления PASS; отдельный unit подтверждает recovery.
- Полный локальный CI-контур R09 на содержимом кандидата: release guard — PASS;
  backend unit `592 PASS`; HTTP `69 PASS`; PostgreSQL integration `167 PASS`,
  `1 SKIP` только explicit real-provider; frontend lint — PASS; frontend content
  `75 PASS`; build — PASS; browser `63 PASS` за ~10 минут. Controlled 27-row runner
  собирает все Case/function строки package `0.5`; package/runtime, actorless 02/07,
  reaction counts 04/05/06/08/09, hidden materials, time expiry, pause/resume,
  additional Session, late worker/replay и полный synthetic Evidence→IA→M8 покрыты
  адресными/общими наборами. Controlled LLM не является методологической приёмкой.
- R09 внешние gates: PR не создан и CI URL отсутствует, поскольку `gh` недоступен и
  ветка не отправлялась; merge/deploy не выполнялись. Поэтому обязательные remote CI
  exact-head и human review остаются `NOT_RUN`, несмотря на локальный PASS. Live
  program revision/publish также `NOT_RUN`. Откат кандидата: revert R09 commit и
  вернуть приложение `2.0.28`; immutable snapshots/package history не удалять.
- R10 readiness после подключения credential: `DeepSeekGateway.enabled=true`;
  общая `.env` содержит legacy model `deepseek-chat`, поэтому запуск явно закрепил
  опубликованную identity `deepseek/deepseek-flash`, contract `1.0.0`
  (`a9b20456...951c8c`). Ключ не читался и не выводился.
- Real-provider pilot `A06.C01.SALES` на candidate `0ead559a...` выполнил generation,
  tester, challenger и одну предусмотренную repair-фазу; transport всех четырёх
  операций PASS. Итог `AS_ADMISSION_FAIL`: repair-кандидат потерял обязательные refs
  adapted indicator layer, а tester сохранил blocking-находки по остаточным имени и
  предмету авторского примера в Sales observability. Дефектная AS не предъявлялась;
  runtime, Evidence/IA, substantive admission и M8 — `NOT_RUN`.
- По R10 gate зависимые 27 preparations / 9 API paths / 3 browser paths остановлены:
  не выполнялись дополнительные regeneration, ослабление tester или подмена AS.
  Safe trace: `docs/evc/evidence/r10-c01-sales-real-provider-2026-10-26.json`; полный
  синтетический raw trace сохранён вне Git в `/tmp/p4k-r10-0ead559a-pilot/`.
- R10 remediation локализовала две разные причины. Исходная generation имела
  корректный Sales adapted-layer с Артёмом и полными refs; «Елена» находилась только
  в обязательном immutable author provenance. Tester/challenger ошибочно оценивали
  bound author-view как concrete AS — дефект передачи входа. Repair затем получил
  тот же bound view без полного двухслойного контракта и действительно потерял refs —
  дефект repair input/generation; compiler не запускался. Semantic consumers теперь
  получают concrete adapted-view и отдельные author/adapted layers; repair также
  получает versioned contract и обязательные поля. Admission не ослаблен.
- Сохранён полный synthetic raw trace (без credential) в
  `docs/evc/evidence/r10-c01-sales-real-provider-attempt-raw-2026-10-26.json`, SHA-256
  `a9af0eee...c0530`; классификация с фрагментами — в
  `docs/evc/evidence/r10-c01-sales-blocker-analysis-2026-10-26.md`.
- Адресные проверки remediation: 41 functional/package/ARCH-A06 unit PASS;
  `py_compile` PASS; `git diff --check` PASS. Следующий gate — commit исправления и
  один повтор C01/Sales на exact SHA; 27/9/3 до успеха не запускать.
- Remediation commit `9f6d958174645754f4744842ca3eb184d1f5b7a7`. Повтор
  `A06.C01.SALES` real-provider: generation/tester/challenger/admission PASS без repair;
  input `f828a55e...b0467db`, candidate `f103d1e7...b9f1a`.
- Checkpoint 27 preparations продолжен: 8 результатов сохранены; 6 admission PASS
  (C01 Sales/HR/IT, C02 Sales/HR, C03 Sales), C02/IT — подтверждённый AS FAIL после
  одной repair (несогласованное преимущество A и неполная IT-подстановка), C03/HR —
  `INCOMPLETE` из-за 23 protected checks без adversarial review, C03/IT — дважды
  `LlmGatewayError`. После повторного технического blocker оставшиеся 18 не запускались.
- Raw checkpoint сохранён в `docs/evc/evidence/r10-matrix-9f6d958-checkpoint-2026-10-26.tar.gz`,
  SHA-256 `585f397b...18a84`; safe manifest — одноимённый `.json`. Full API и browser
  paths пока `NOT_RUN`; методологический PASS/Reliability не присвоены.
- Runner исправлен отдельно от admission: outcome теперь сохраняет точный aggregation
  status (`INCOMPLETE` не маскируется как `FAIL`). Следующий независимый шаг — создать
  и проверить штатный API/runtime runner на уже принятых AS; зависимый preparation
  checkpoint ожидает локализации повторного provider failure C03/IT.
- Safe provider diagnostics commit `8eccc60`: адресный C03/IT retry доказал HTTP 502
  на `generation_repair` после 162943.7 ms; request messages checksum
  `7a72d5dd...a5f29`, credential/prompt body не сохранялись. Строка остаётся
  `BLOCKED_PROVIDER_502`, последующие повторы без изменения причины запрещены.
- Независимый checkpoint продолжен: C04 Sales/HR/IT — admission FAIL, C05/Sales —
  admission PASS. Итого 12 завершённых preparations: 7 PASS, 4 FAIL, 1 INCOMPLETE;
  C03/IT — отдельный technical blocker; 14 строк NOT_RUN. C05/HR был прерван до
  результата и не считается завершённой попыткой. Обновлённый raw archive SHA-256:
  `cb462afc...e77634`.
- Следующий checkpoint: C05/HR, C05/IT, C06/HR и C06/IT — admission PASS;
  C06/Sales — admission FAIL. Итого 17 завершённых preparations: 11 PASS, 5 FAIL,
  1 INCOMPLETE; C03/IT отдельно `BLOCKED_PROVIDER_502`; C07–C09 (9 строк) NOT_RUN.
  Начавшийся C07/Sales прерван до результата и не учитывается. Raw archive SHA-256
  `ac53c953...5bb85b`.
- CASE.SPEC.07 Sales/HR/IT — admission PASS. Итого 20 завершённых preparations:
  14 PASS, 5 FAIL, 1 INCOMPLETE; C03/IT отдельно `BLOCKED_PROVIDER_502`; C08–C09
  (6 строк) NOT_RUN. Начавшийся C08/Sales прерван до результата и не учитывается.
  Raw archive SHA-256 `2bb01332...21480`.
- CASE.SPEC.08 Sales/HR/IT — admission PASS. Итого 23 завершённых preparations:
  17 PASS, 5 FAIL, 1 INCOMPLETE; C03/IT отдельно `BLOCKED_PROVIDER_502`; только C09
  (3 строки) NOT_RUN. Raw archive SHA-256 `c25fdd0c...e70dee`.
- Единый пакет кандидата, фактическая матрица, безопасные trace locations, rollback и
  точное следующее действие сохранены в
  `docs/evc/evidence/case-cycle-r1-2026-10-26.md`. Existing real-cycle pytest не принят
  как R10 proof: он вручную вставляет Turn и нарушает критерий штатного API пути.
- Следующий шаг: продолжить checkpoint только C09; C03/IT не повторять без
  изменения доказанной причины HTTP 502. После preparation inventory строить штатные
  API/runtime пути только для admission PASS AS. Merge/deploy/publish не выполнять.
