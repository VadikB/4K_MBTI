# STATE — Case / Cycle R00–R10

- Base: `b3bbdc9e78880879e1d4fc930ef8c9cc9f200524` (`origin/main`, приложение `2.0.28`).
- Ветка: `codex/case-cycle-r1`.
- Активная карточка: R06.
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
- Следующий шаг: R06 — полный Cycle execution manifest и замыкание зависимостей.
