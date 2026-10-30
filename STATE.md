# STATE — ARCH30

## Текущий checkpoint ARCH30, 30.10.2026

- Worktree: `.codex/worktrees/arch30/4K`, ветка `codex/arch30`, base
  `e08c6f51acaf5a59b08b73cc98f05e9d03be0bd4`.
- Решения владельца по ProgramDefinition, полному purge и переносу зафиксированы
  в `docs/adr/003-arch30-program-and-deletion-lifecycle.md`.
- Реализованы ранее независимые ARCH30-02/03/05/06/07 и минимальный
  ProgramDefinition: immutable published/retired, история подключения, точные
  config/catalog/role refs, API/UI суперадминистратора, release-команда.
- Текущие проверки: стандартный backend 755 PASS / 186 deselected,
  frontend 102 PASS, объединённый ARCH30 DB 11 PASS; финальная пересборка,
  py_compile и diff PASS.
- Полный browser discovery: 71 PASS; 16 owned-backend сценариев NOT_RUN, потому
  что для destructive/real-stand контура явно не задан `STAND_ADMIN_URL`.
  Продуктовых browser FAIL в этом запуске нет.
- Dependency preview и изолированное доказательство purge организации/отдельного
  detached account завершены. External ledger + DB receipts + fail-closed startup
  + replay и product execution endpoints реализованы; production fail-closed
  ждёт provisioned эксплуатационный путь вне общего PostgreSQL backup.
- Preview помечает текущий и заданные конфигурацией аккаунты как сохраняемые;
  purge организации останавливается до изменения конфигурации, если такой
  аккаунт иначе пришлось бы удалить. Detached-account UI доступен и при нуле
  организаций; блокирующая причина показывается до ввода необратимого
  подтверждения.
- Исполнение purge строит план на своём DB-соединении, сверяет fingerprint и
  только после успешной сверки синхронно сохраняет внешний intent перед первым
  удалением. Устаревший preview не оставляет ложный intent для replay.
- После исправления execution endpoint повторён стандартный backend без
  integration/e2e/llm: 671 PASS / 273 deselected; предупреждение только
  Starlette deprecation.
- Финальный HTTP/e2e: 86 PASS / 858 deselected; JS lint `--quiet` PASS.
- `branch_push=true`, `pr=true` (`#131`), `version_bump=true` (`2.0.39`),
  `merge=false`, `deploy=false`, `artifact_publish=false`; реальное удаление не
  выполнялось.
- Локальная реализация и применимая матрица завершены. Следующий внешний gate:
  человеческий review и, только после разрешения владельца, commit/PR и exact-head CI.

## Историческое состояние UX-PATH29

## Текущий checkpoint после возобновления

- PR #124, опубликованный head `49e6693a903c06bcdb65d51ce936ecdabc41d972`,
  один кандидат 2.0.35. Владелец принял review этого head; запись в PR
  [6498103561](https://github.com/VadikB/4K_MBTI/pull/124#issuecomment-6498103561).
- Полный возобновлённый integration: **170 PASS / 2 explicit llm SKIP**, exit 0,
  917.48s. Unit 646 / HTTP 81 PASS относятся к тому же неизменённому backend.
- Полный browser: **80 PASS / 1 FAIL / 3 NOT_RUN**, exit 1, 12.3m. S10.4:
  PATCH Telegram вернул 200, повторный profile-summary очистил статус успеха.
  Доказана гонка старого helper: при задержке lazy bundle 350ms он открывает
  профиль трижды. Регрессия до исправления FAIL (3 GET вместо 1).
- Текущий адресный шаг меняет только browser helper/регрессию и отчёт: один клик,
  ожидание экрана без повторной команды; ни product profile, ни dist не меняются.
  Адресный повтор: **3 PASS / 1.5m**, exit 0; новый полный browser запущен.
  CI `40881550481` на 49e6693 — frontend/pytest PASS (pytest 12m39s), но
  локальный helper FAIL требует отдельной регрессии и нового head. Следующий head требует
  нового человеческого review и обязательного CI, даже если CI 49e6693 зелёный.
- Merge/deploy НЕ выполнены. Разрешение на squash merge/штатный deploy только test
  действует после gates; real-provider smoke **NOT_RUN**, каталог отдельно.
  Исторические checkpoints ниже не отменяют этот статус.

Возобновлено 29.10.2026 по следующей прямой команде владельца «продолжаем».
Старые тестовые процессы завершены; полные прогоны запускаются заново, не с места
прерывания. Сохранённые результаты остановки: integration exit 2 / 84 PASS до
KeyboardInterrupt; browser exit 130 / 73 PASS, 1 interrupted, 10 NOT_RUN.
Это не полные PASS. Новые логи: `/private/tmp/path29-resumed-integration.log`,
`/private/tmp/path29-resumed-browser.log`. Ниже — историческая запись паузы.

## Пауза по команде владельца 29.10.2026

Владелец: «останови тестирование, я закрываю крышку. возобновим по моей команде».
Локальные полные integration/browser прогоны прерваны; их частичные результаты
не являются PASS. Не возобновлять проверки, push, merge, deploy или LLM без новой
команды владельца. Все исходники и логи сохранены, destructive cleanup не нужен.

Исторический checkpoint паузы: worktree `/Users/vadim_bogachev/.codex/worktrees/ux-adm28-add01-v2/4K`,
ветка `codex/ux-path29-participant`; remote/PR #124 head `f0bac11`, кандидат 2.0.35.
CI run 40872272091 завершён FAIL (83 browser PASS / 1 FAIL); merge/deploy не было.
Uncommitted: 4 строки в `Api/m7_clarification.py`, конкурентная регрессия в
`tests/integration/test_m6_evidence_db.py`, ожидание POST/start + 6s fault injection
в `tests/browser/runtime.spec.mjs`, STATE/задача/verification report.

Доказано до паузы: новая regression до исправления FAIL/UniqueViolation, после
sequential/concurrent 2 PASS; unit 646 PASS; HTTP 81 PASS; delayed-start S10-A
3 PASS / 4.3m. После возобновления проверить фактическое состояние ресурсов и
повторить прерванные полные наборы, не переиспользовать их как завершённые.
Логи: `/private/tmp/path29-ci-fix-integration.log`, `/private/tmp/path29-ci-fix-browser.log`.
Затем отчёт/changed-paths, рабочий commit и push в тот же PR, новое review точного
head и обязательный CI. Разрешение test merge/deploy действует только после gates.
Real-provider smoke оставлен NOT_RUN по отдельному решению владельца; каталог
согласовать отдельно. Новых LLM-вызовов/публикаций не было.

## Состояние до паузы

- Base: свежий `origin/main` `a86775ff011a51831f9f86596be3dd776de79d11`, 2.0.34.
- Ветка `codex/ux-path29-participant`, изолированный worktree; пользовательская
  основная копия и её untracked не затронуты. Все четыре задания — один PR.
- Владелец 29.10 подтвердил один PATCH-кандидат 2.0.35. Bump выполнен один раз.
- С разрешения владельца read-only journal/БД test подтвердили шесть отказов
  28.10 22:40–22:46 МСК: `M4_PROFILE_NOT_READY`, нет выбранной роли/M4;
  confirmation/consent сохранены. Provider не вызывался на этом пути отказа.
  [Безопасное доказательство](docs/evc/tasks/artifacts/ux-path29/incident-2026-10-28.md).
- TASK01 локально: единый trusted origin, public-only deployment config без
  чтения/перезаписи secret dotenv, URL builders и rollback/smoke origin.
- TASK02–04 реализованы локально: явные scoped config/role refs, восстановление
  ответов/consent, canonical M4 без global/default; W01 chat; независимая durable
  подготовка и явный старт того же prepared Cycle. Frozen history не переписывается.
- Backend кандидата `89f4f26` (после него не менялся): 646 PASS, HTTP 81 PASS,
  integration 169 PASS / 2 explicit llm SKIP. Frontend 85 PASS, lint/build PASS.
  owned browser positive path 1 PASS (все 6 viewport/short/zoom200, две вкладки,
  failed PUT/reload, один UUID/M4/Cycle, нет раннего времени, первая AS в чате).
  Ранние два fixture FAIL исправлены и закрыты полным повтором 169 PASS.
  S10-A до saved Report/PDF PASS после исправления lazy-init первого сообщения.
  Возврат с dashboard исправлен через journey, начальная загрузка блокирует старые
  действия. Expanded U02 PASS / 48.1s: все reload точки и новая auth-сессия.
  Полный browser 84 PASS / 13.6m до последней review-mode правки.
  Следующий прогон прерван clamshell sleep 13:53:03–15:00:39 МСК;
  без правок повтор E01 3 PASS и полный auth 68 PASS / 1.0m.
  Последний сквозной review-mode PATH29 — 1 PASS / 51.9s: тот же M4/Cycle,
  started=1 после возврата; новый frontend повтор 85 PASS, lint PASS.
  Новый CI/deploy NOT_RUN.
- Единый [PR #124](https://github.com/VadikB/4K_MBTI/pull/124), head f0bac11.
  Владелец принял review этого head и разрешил squash merge/штатный test deploy
  только после зелёного CI. CI run 40872272091: frontend PASS; backend unit/HTTP/
  integration PASS; browser 83 PASS / 1 FAIL (S10-A, duplicate clarification Turn).
- Активный шаг: адресное устранение CI-гонки в M7.present (pre-lock read →
  повторное чтение delivery под Cycle → AS lock). Конкурентная регрессия:
  до исправления UniqueViolation FAIL, после sequential/concurrent 2 PASS.
  Отдельно доказан 5s timeout browser-helper на реальном start; helper теперь ждёт
  POST/start ack, synthetic задержка ответа 6s остаётся регрессией.
  Полные unit 646 PASS / HTTP 81 PASS; S10-A с delayed start — 3 PASS / 4.3m.
  Полные integration/browser были прерваны по команде владельца и после «продолжаем»
  запущены заново. В рабочем checkpoint они RUNNING; окончательные результаты и CI
  точного head фиксируются в PR #124, локальный частичный успех не равен допуску.
  Тот же PR/2.0.35;
  новое review окончательного head потребуется, f0bac11 approval не переносится.
- Read-only test preflight: единственный каталог e102-controlled/1.0 — technical
  synthetic fixture, scoped, 2 cases; configs 1/2 без catalog. Владелец решил
  продолжить deploy после gates, smoke оставить NOT_RUN, каталог согласовать отдельно.
  Новых LLM-вызовов/публикации артефактов нет; P0 генерации не объявлен закрытым.
  [Общий план и откат](docs/evc/tasks/ux-path29-participant.md).
- [Подробные команды, traceability, U01–U07 и ограничения](docs/evc/tasks/artifacts/ux-path29/verification.md).
- Исходный backend в `89f4f26`, UI/test/report в `f0bac11`; следующий рабочий
  checkpoint фиксирует узкое runtime-исправление M7 и регрессии.
  Передача — единый PR; его URL и окончательный head фиксируются в PR/сообщении.
  Новые review/CI gates обязательны; прежние PR122/123 reviews не применяются.
  Локальная готовность к review не равна приёмке или допуску deploy.

## Предыдущий результат — TEST-DEPLOY-28

- Base: `84467d12814196b3196e72f841d462de1a7f8223`, свежий origin/main, 2.0.33.
- Ветка: `codex/test-deploy-current-checkout`; отдельный инфраструктурный PR
  и один PATCH 2.0.34 явно разрешены владельцем 28.10.2026 после merge #122.
- Реализованы bootstrap по CI SHA в фактическом test checkout,
  отказы dirty/behind/divergent и rollback; кандидат 2.0.34 собран.
- Read-only inventory: User=vadim_bogachev, WorkingDirectory=
  `/home/vadim_bogachev/projects/Agent4K-Test`, чистый HEAD 0b44c26;
  прежние /home/user1 test-пути отсутствуют. HOST исправлен с разрешения;
  CI теперь проходит host key gate, но получает Permission denied (publickey).
- PASS: 615 backend unit, 25 адресных deploy/retention/release,
  lint/82 frontend/build/release consistency, shell/YAML/diff.
  Следующий шаг: PR и обязательный CI; CI user/key и новое человеческое review
  остаются внешними gates. Приватные ключи не читаются и не переносятся.
- План, границы, откат: [карточка](docs/evc/tasks/test-deploy-current-checkout.md).

## Предыдущий результат — UX-ADM28-ADD01 v2

- Base: `9d7c9eaacf101fd3c48d7059bd68a96cf7176d87` (`origin/main`, 2.0.32).
- Ветка: `codex/ux-adm28-add01-v2`; кандидат приложения 2.0.33.
- TASK01–03 реализованы. Код и локальные проверки: `c4d6debc916e861b11e53de6cdc3a95437bcb5d6`
  (предшествующий рабочий commit `d62166b`).
- Локально PASS: 599 unit, 81 HTTP, 167 PostgreSQL integration / 2 explicit llm SKIP,
  82 frontend, 63 browser; lint/build/reproducible dist/release/shell/YAML/diff.
- Единственный [PR #122](https://github.com/VadikB/4K_MBTI/pull/122).
  Обязательный CI проверяет актуальный head PR; результаты и ограничения —
  [в отчёте](docs/evc/tasks/ux-adm28-add01-v2.md).
- Следующий шаг: зелёный CI точного head и человеческое review, затем разрешённые
  merge и deploy только на test с повторной HTTPS-проверкой. Сообщение владельца
  «идем дальше» подтверждает продолжение работы, но не заявляет выполненное review.
- HTTPS до выпуска: 2.0.31, 71/71 asset совпадает с `0b44c26`; main deploy остановился
  на Configure SSH. После выпуска HTTPS, полная матрица платформ и визуальная
  приёмка владельца/маркетолога ещё не проверены. Pilot/production не затронуты.

## Предыдущая серия — Case / Cycle R00–R10

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
- CASE.SPEC.09 Sales/HR — admission PASS; C09/IT — INCOMPLETE. N01 исчерпан:
  26 сохранённых результатов (19 PASS, 5 FAIL, 2 INCOMPLETE) и C03/IT как отдельный
  `BLOCKED_PROVIDER_502`; `NOT_RUN=0`. Raw archive SHA-256 `59a286a9...1e39284`.
- Единый пакет кандидата, фактическая матрица, безопасные trace locations, rollback и
  точное следующее действие сохранены в
  `docs/evc/evidence/case-cycle-r1-2026-10-26.md`. Existing real-cycle pytest не принят
  как R10 proof: он вручную вставляет Turn и нарушает критерий штатного API пути.
- Следующий шаг: строить штатные API/runtime пути только для admission PASS AS;
  C03/IT не повторять без изменения доказанной причины HTTP 502. FAIL/INCOMPLETE AS
  не предъявлять. Merge/deploy/publish не выполнять.
- N02 предварительный owner-API pilot больше не использует ручной `INSERT Turn`:
  participant Turn и завершение Cycle выполнены через `/users/assessment/...`;
  real-provider Evidence и IA завершились `succeeded`, pipeline — `report_ready`,
  M8 — `C-67`, Reliability — `not_verified`. Тест: `1 passed` за 45.41 s.
  Это ограниченный PASS на `CASE-TDISC-01`, а не зачёт функциональной матрицы N02.
  Safe manifest и raw synthetic trace: `docs/evc/evidence/r10-api-m8-pilot-2026-10-26.*`;
  архив SHA-256 `5e4336c1...8cfcf`. Следующий шаг — тот же owner HTTP контур на
  сохранённой admission-PASS `CASE.SPEC.01` с проверкой точной profile/case identity.
- Попытка прямого reuse `A06.C01.SALES` остановлена до LLM: matrix-профиль N01
  (`460fbfa6...770a3`) не является воспроизводимым frozen M4 snapshot и штатно
  отклоняется `M4_CHECKSUM_MISMATCH`; перепривязка принятой AS к другому profile
  запрещена. Поэтому N02 запущен заново через owner `/cycles/prepare` с валидным
  `specialist_expert` M4 profile. M4 и M7 selection `CASE.SPEC.01` PASS; реальная
  generation/tester завершилась `M5_FUNCTIONAL_AS_NOT_ADMITTED:INCOMPLETE` за
  127.98 s. Runtime/M6/M8 — `NOT_RUN`; содержательный FAIL не присваивается.
- Test harness не экспортировал `failure_result` до удаления isolated schema, поэтому
  точные INCOMPLETE checks этой попытки утрачены. Runner исправлен: будущая ошибка
  сохраняется как `.preparation-failure.json` до assertion. Без изменения причины
  provider-повтор запрещён. Safe запись попытки:
  `docs/evc/evidence/r10-functional-api-c01-attempt-2026-10-26.json`.
- Независимая product-valid попытка `CASE.SPEC.02` с исправленным capture локализовала
  причину: generation deterministic PASS, repair не использован, provider transport
  PASS/`finish_reason=stop`, но один tester request вернул полноценный PASS только для
  13 из 33 checks; 20 обязательных protected checks остались без adversarial review и
  были корректно нормализованы в `TECHNICAL_ERROR`. Итог `INCOMPLETE`; AS не
  предъявлялась, runtime/M6/M8 `NOT_RUN`. Это дефект передачи tester workload одним
  запросом, а не содержательный FAIL AS и не ошибочное требование tester.
- Исправление делит точный required-check set tester/challenger на детерминированные
  партии максимум по 8, сохраняет trace каждой партии и агрегирует только после
  восстановления полного набора exact IDs. Admission не ослаблен. Адресные unit:
  `30 passed`; `py_compile` и `git diff --check` PASS. Evidence:
  `docs/evc/evidence/r10-functional-api-c02-attempt-2026-10-26.{json,tar.gz}`,
  archive SHA-256 `52433870...06d1c6`. Следующий gate — commit и один C02 retry на
  исправленном exact candidate; C01 без собственного trace не повторять.
- Exact candidate `bb2fb7f`: первый C02 retry после batching дошёл до admission PASS,
  но test harness остановился после `/cycles/start` на неверном ожидании внутреннего
  `assessment_situation_id` в participant projection; Turn ещё не отправлялся.
  Assertion переведён на `runtime.current_situation`, completed preparation теперь
  сохраняется до start. Единственный post-harness repeat завершил весь путь PASS:
  product M4 → owner HTTP prepare/start/Turn/completion → real Evidence `succeeded`
  → IA `succeeded` → pipeline `report_ready` → M8 `C-67`; `1 passed in 304.15s`.
  Reliability `not_verified`, methodology `NOT_RUN`. Candidate AS
  `dcccceed...72fd4`, profile `3a70f214...68ba3`, AS snapshot `4c7668c0...06f1a`.
  Evidence `docs/evc/evidence/r10-functional-api-c02-pass-2026-10-26.{json,tar.gz}`,
  archive SHA-256 `c538c19e...a9802`. N02: 1/9 functional paths PASS; C01 remains
  INCOMPLETE without reusable trace and не повторяется. Следующие captures включают
  полный persisted `functional_personalization_trace`.
- `CASE.SPEC.03` на candidate `3cfed3f` завершил полный product путь PASS без repair:
  PM-03 tester PASS (4 batches), challenger (4 batches), owner HTTP
  prepare/start/Turn/completion, Evidence и IA `succeeded`, pipeline `report_ready`,
  M8 `C-67`; `1 passed in 554.93s`. Candidate `ac7bf97c...2f32a`, AS snapshot
  `92765972...b1318`. Полный persisted PM-03 trace сохранён. Reliability
  `not_verified`, methodology `NOT_RUN`. Evidence:
  `docs/evc/evidence/r10-functional-api-c03-pass-2026-10-26.{json,tar.gz}`,
  archive SHA-256 `dd0b1c1b...641e39`. N02 functional: 2/9 PASS; C01 INCOMPLETE,
  C04–C09 NOT_RUN.
- `CASE.SPEC.04` на `3c6311b`: generation/compilation deterministic PASS, одна repair,
  final tester FAIL по трём blocking checks; runtime/M6/M8 `NOT_RUN`. Все три находки
  нарушают технический двухслойный контракт tester: требование заменить имя в
  immutable author provenance при уже корректной adapted «Марина»; требования
  поместить hidden facts `F01–F05` в `material_refs`, чей закрытый namespace допускает
  только `Материалы[].MaterialID`. Это ошибочные требования tester, не доказанный
  дефект AS. Полный raw trace:
  `docs/evc/evidence/r10-functional-api-c04-attempt-2026-10-26.tar.gz`, SHA-256
  `a76e9f37...02922a`; safe classification — одноимённый `.json`.
- Tester/challenger payload явно закрепил: author-only имена являются provenance и
  не изменяются; `material_refs`/`event_refs`/`character_refs` имеют закрытые
  namespaces; hidden facts проверяются семантически через conditions/events, а не
  как MaterialID. Admission не ослаблен. Адресные unit `30 PASS`, `py_compile` и
  `git diff --check` PASS. Следующий gate — commit и один C04 retry на exact SHA.
- Единственный C04 retry на candidate `e82802f` снова завершился admission FAIL после
  одной repair. Точный tester payload содержит «Марина» и в concrete
  `IndicatorObservability`, и в adapted layer; `IndicatorTargetLayers` отсутствует,
  а «Алексей» находится только в явно размеченном immutable author layer. Блокеры
  `common.professional_consistency` и `quality.clarity`, утверждающие обратное, —
  `ERRONEOUS_TESTER_REQUIREMENT`; дефекта generation/compiler/transfer не подтверждено.
  Runtime/M6/M8 — `NOT_RUN`; новых C04 retries без новой причины не выполнять.
  Evidence `docs/evc/evidence/r10-functional-api-c04-retry-2026-10-26.{json,tar.gz}`;
  archive SHA-256 `fd9a6fce...cb0ae0`. Следующий независимый путь — C05.
- `CASE.SPEC.05` на `413bada`: generation и deterministic validation PASS, repair не
  использован, transport tester завершён `finish_reason=stop`, но PASS защищённого
  `common.confidentiality` не содержал обязательный adversarial review. Валидатор
  корректно нормализовал его в `TECHNICAL_ERROR`, aggregation `INCOMPLETE`; это
  неполный protocol response tester, не содержательный FAIL AS. Runtime/M6/M8 —
  `NOT_RUN`; без изменения причины C05 не повторять. Evidence:
  `docs/evc/evidence/r10-functional-api-c05-attempt-2026-10-26.{json,tar.gz}`;
  archive SHA-256 `3bb88b44...97cd80`. N02: C02/C03 PASS; C01/C05 INCOMPLETE;
  C04 erroneous tester requirement; C06–C09 `NOT_RUN`.
- `CASE.SPEC.06` на `72fee15` остановлен техническим provider blocker через 447.17 s:
  при challenger retest после одной repair строгий JSON parser исчерпал один retry и
  получил `JSONDecodeError` (`position=6419`), итог
  `M5_FUNCTIONAL_PROVIDER_JSON_INVALID`. Частичный JSON не восстанавливался; это не
  содержательный FAIL AS. Из-за исключения до возврата `prepare` queue сохранила
  operation/error, но не phase trace; raw response после teardown недоступен — явное
  ограничение evidence. Admission не завершён, runtime/M6/M8 `NOT_RUN`; C06 не
  повторять. Evidence `docs/evc/evidence/r10-functional-api-c06-attempt-2026-10-26.{json,tar.gz}`;
  archive SHA-256 `85d38b5a...c4be0a`.
- `CASE.SPEC.07` на `94d3963` завершил полный product путь PASS за 270.42 s:
  product M4 → owner HTTP prepare/start/Turn/completion → real-provider Evidence и IA
  `succeeded` → pipeline/report `ready`. Candidate `06113b8c...96bb7`, AS snapshot
  `d4ad0ae3...425c8`. Reliability `not_verified`, methodology `NOT_RUN`. Evidence:
  `docs/evc/evidence/r10-functional-api-c07-pass-2026-10-26.{json,tar.gz}`;
  archive SHA-256 `1994a76b...abcec7`. N02 functional: C02/C03/C07 PASS (3/9);
  C01/C05 INCOMPLETE, C04 tester-contract FAIL, C06 provider blocker, C08/C09 NOT_RUN.
- `CASE.SPEC.08` на `1e2bd67` прошёл product M4, functional AS admission и owner HTTP
  prepare/start/Turn/completion, но M6 Evidence request завершился `failed`; IA не
  создана, M8 `NOT_RUN`. Runner не экспортировал attempt error/trace до teardown,
  поэтому точная причина недоступна и содержательный FAIL не присваивается; C08 без
  подтверждённой причины не повторять. Capture исправлен только для следующих строк:
  при отсутствии IA сохраняются status/error/trace последней M6 attempt. Адресная
  проверка: `py_compile` PASS, real-provider test без opt-in SKIP. Evidence:
  `docs/evc/evidence/r10-functional-api-c08-attempt-2026-10-26.{json,tar.gz}`;
  archive SHA-256 `766270d9...f1dd19`.
- `CASE.SPEC.09` на `b568c8c`: generation/deterministic PASS, repair не использован;
  tester вернул повторяющиеся protected check IDs `K4.I12` и `K4.I16`, хотя exact
  workload содержит каждый required ID один раз. Aggregator корректно нормализовал
  их в `TECHNICAL_ERROR`, итог `INCOMPLETE` без содержательного FAIL. Runtime/M6/M8
  `NOT_RUN`, C09 без новой причины не повторять. Evidence:
  `docs/evc/evidence/r10-functional-api-c09-attempt-2026-10-26.{json,tar.gz}`;
  archive SHA-256 `3dd36f5d...e23313`.
- N02 исчерпан: 3/9 full functional PASS (C02, C03, C07); C01, C05, C09 —
  `INCOMPLETE`; C04 — erroneous tester requirements; C06 — provider malformed JSON;
  C08 — M6 Evidence failed с утраченной точной причиной. `NOT_RUN=0`; случайные
  повторы запрещены. Methodology `NOT_RUN`, Reliability `not_verified`.
- N03 real-provider browser — `BLOCKED_INFRASTRUCTURE`: owned browser stand имеет
  только guarded `acceptance-v1` controlled gateway/catalog и не умеет импортировать
  admitted functional AS, выбирать Sales/HR/IT profiles и сохранять real-provider
  trace через UI lifecycle. Controlled результат не повышен до real-provider PASS.
  На exact head `6fea0a8` три полных controlled пути повторены: S10-A/T11-10 +
  clarification/Report/PDF, interruption + Additional Session, recovery + two tabs +
  owner boundaries — `3 passed in 2.1m`. Первый запуск без `BROWSER_PYTHON` остановился
  до создания stand и не является product result. Safe manifest:
  `docs/evc/evidence/r10-browser-boundary-2026-10-26.json`.
- Финальный локальный CI на содержимом кандидата после R10 remediation: release guard
  `2.0.29` PASS; backend `597 PASS`; HTTP `69 PASS`; PostgreSQL integration
  `167 PASS, 2 SKIP` только explicit real-provider (выполнен отдельно); frontend lint
  PASS, content `75 PASS`, build PASS. Полный browser: `62 PASS`, один REV-02 timeout
  при 200 responses и без server ERROR; единственный адресный повтор на чистой DB —
  PASS за 1.0m. Устаревший negative-matrix oracle исправлен: он теперь вычисляет
  ожидаемое число tester/challenger batches и проверяет лимит `1..8`; адресно 3 PASS.
- N04 real multi-case с тремя generated functional AS остаётся
  `BLOCKED_INFRASTRUCTURE`: существующий real runner создаёт один Case на одноразовый
  Cycle, а controlled multi-case нельзя повышать до real-provider. N05 подтверждает
  real-provider различия контекста на N01, но runtime глубина только для Sales и
  остаётся PARTIAL. N06 recovery полный только controlled; real positive результаты
  C02/C03/C07 сохранены отдельно. N07 live publish/deploy `NOT_RUN`: нет подключённого
  общего test stand/PR/remote CI; локальная PILOT-120 граница PASS. N08 PASS TECH;
  N09 PASS TECH, methodology `NOT_RUN`.
