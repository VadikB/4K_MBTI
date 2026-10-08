# Контракт целостности каталога M5

Статус: реализация Task-10-11, версия контракта `1.0`.

## Граница и владение

Опубликованный `m5_catalogs` — неизменяемый технический снимок набора
`CaseVersion`, допущенных для конкретного `usage_scope`. Он принадлежит M5 и
связывается с опубликованной `assessment_configuration`. M7 читает только этот
снимок, сохраняет его ссылку в `m5_cycles.catalog_ref_json` и не пересобирает
каталог из глобального набора кейсов. Начатый цикл поэтому не меняется после
публикации следующей версии каталога.

Организационный `RoleProfileVersion` разрешается через `base_role_version_id`.
Сопоставление кейса выполняется со стабильным кодом базовой роли, а не с кодом
организационного профиля.

## Контракт допуска

Единый предикат `Api.m5_catalog_integrity.case_admission` используется при
планировании и непосредственной подготовке AS. Для каждого scope
`case_format`, `case_dialogue`, `assessment_situation` выбирается последняя
запись по монотонному DB `id`. Запись принимается только при одновременном
совпадении:

- `CaseVersion.id`, `version`, `content_checksum`;
- `base_role` и запрошенного `usage_scope`;
- `scope`, `result` и canonical checksum payload;
- разрешённого происхождения evidence.

Для `assessment` разрешён только `human_review`. `fixture` и `synthetic_test`
допустимы только в `qa`. Более новая `FAIL` не может быть перекрыта старой
`PASS`. Нормативные значения находятся во внешнем версионированном артефакте
`assessment_definitions/catalog_contracts/competencies_4k/1.0/catalog-integrity-policy.json`.

## Публикация и совместимость

Публикация состоит из dry-run плана и атомарной записи каталога. Запрос
идемпотентен по `(published_by, idempotency_key)` и конфликтует при ином
`request_hash`. Опубликованный manifest и membership защищены DB-триггерами от
UPDATE/DELETE. Пустой каталог разрешён: профиль сохраняется, а новый цикл
возвращает `NO_ROUTE`.

Существующие конфигурации с `catalog_version_id IS NULL` остаются читаемыми, но
новый assessment-цикл по ним получает `M5_CATALOG_REF_REQUIRED`. Узкая ветка
совместимости `legacy-unbound-test-catalog` применяется только к изолированным
старым contract-test схемам, где столбца `catalog_version_id` физически нет; в
production bootstrap столбец создаётся до внешнего ключа.

## Миграция и откат

Миграция аддитивна: новые таблицы, nullable-ссылка конфигурации и nullable
snapshot цикла. Существующие данные не переписываются. До включения новой
конфигурации ответственный за выпуск публикует каталог и новую draft-версию
конфигурации, затем публикует её обычным authoring-процессом.

Откат runtime выполняется возвратом к предыдущему commit и выбором ранее
опубликованной конфигурации. Созданные каталоги не удаляются и остаются
аудируемыми; новые nullable-колонки безопасно игнорируются старым кодом.

## Прослеживаемость

| Правило | Контракт/данные | Реализация | Проверка |
| --- | --- | --- | --- |
| точное evidence и latest-wins | policy + `m5_qa_evidence` | `case_admission` | `test_m5_catalog_integrity.py`, `test_m5_catalog_integrity_db.py` |
| каталог конфигурации | `assessment_configurations.catalog_version_id` | authoring service, planner | HTTP и PostgreSQL integration |
| frozen cycle | `m5_cycles.catalog_ref_json` | cycle runtime, planner | M7/M10 regression |
| стабильная BaseRole | `base_role_version_id` | `resolve_profile_base_role` | unit/integration contract |
| неизменяемая публикация | `m5_catalogs`, membership, triggers | `publish_catalog` | PostgreSQL integration |
