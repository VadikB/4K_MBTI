# STATE — Case / Cycle R00–R10

- Base: `b3bbdc9e78880879e1d4fc930ef8c9cc9f200524` (`origin/main`, приложение `2.0.28`).
- Ветка: `codex/case-cycle-r1`.
- Активная карточка: R07.
- Завершённые commits: R00 — `aea9bf3`; R01 — `30fc6a0`; R02 — `420a315`;
  R03 — текущий commit совместимости.
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
- Следующий шаг: R08 pilot time.
