# STATE — Case / Cycle R00–R10

- Base: `b3bbdc9e78880879e1d4fc930ef8c9cc9f200524` (`origin/main`, приложение `2.0.28`).
- Ветка: `codex/case-cycle-r1`.
- Активная карточка: R04.
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
- Следующий шаг: R04 — вынести provider-вызовы из DB-транзакции с fencing/idempotency.
