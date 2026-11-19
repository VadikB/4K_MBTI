# P4K_M5_CASETYPE_01 v1.1

## Результат и границы

Импорт и выпуск банка M5 проверяют `case_type_ids` Case v2/v3 по выбранному
ресурсу CaseType. Ошибка указывает ID, JSON Pointer поля, Case и версию источника.
Manifest нового выпуска закрепляет ссылку на источник. Чтение ранее опубликованного
каталога использует сохранённые manifest, checksum и membership. Основания
сценарного QA, допуска и выбора `IndicatorID` действуют по своим контрактам.

Архитектурный адрес — PM-03 / LU-03.1. PM-04 исполняет закреплённую AS.
Действующие контракты C-34 и опубликованные записи сохраняются. Достаточны
существующие M5 package/manifest, загрузчик XLSX и JSON manifest публикации.
Миграция БД и новый формат Case не требуются.

## Источники и полномочия

- Постановка P4K_M5_CASETYPE_01 v1.1 и прямое поручение запустить задачу с XLSX
  в роли ресурса. Результат этапа — локальный кандидат от свежего `main`.
- [Registry](../../architecture/product-4k/registry.md),
  [Architecture v1.0 и Change 01](../../architecture/product-4k/1.0/updates/2026-10-01/README.md),
  [SourceSet](../../methodology/source-sets/2026-10-01/manifest.json), M5.Methodology
  v1.1 §§2–3 и M5.CasePassport v1.1 поля 3–4. SHA-256 оригиналов DOCX закреплены
  в SourceSet. M0 v1.0 unavailable в SourceSet. Нормы CaseType и цели Case заданы M5.
- [CaseType v1.0 FROZEN](../../../assessment_definitions/catalog_contracts/competencies_4k/case-types/1.0/manifest.json),
  оригинальная книга XLSX, лист `CaseType Catalog` и столбец `CaseTypeID`.
  SHA-256 `d748e390933a45eabca44f305027f757c7568a6c4ef343ee5bc7f104c210b7c0`.
  M5 v1.1 §2 → членство в источнике → `validate_package_cases` /
  `publication_plan` → проверки банка и выпуска.
- README, AGENTS, CONTRIBUTING, [рабочий цикл](../agent-workflow.md),
  [рецепт артефактов](../artifact-recipe.md), [матрица проверок](../verification-matrix.md),
  [реестр решений](../decision-register.md), ADR-002 и
  [контракт целостности M5](../../architecture/product-4k/m5-catalog-integrity-contract.md).

По стоп-условиям рабочего цикла: новое предметное решение, разрыв публичного
контракта или границы PM/LU, миграция, противоречие источников, новый контур
артефактов, изменение прав или развёртывания, отсутствие отката и выход за
согласованную область — нет. Использованы выбранный ресурс и существующие
контракты с добавочной ссылкой в новом manifest.

`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`. Проверки публикации выполняются
с синтетическими данными в изолированной локальной БД. Эти флаги относятся
к завершённому этапу локального кандидата.

Для выпуска владелец 19.11.2026 поручил открыть PR и слить его в `main` после
успешного CI. По CONTRIBUTING-MERGE-AUTH-01 разрешены `branch_push=true`,
`pr=true`, `version_bump=true` для следующего PATCH, `merge=true` после
обязательных проверок и штатный `deploy=test` после слияния.
`artifact_publish=false`. XLSX входит в поставку приложения как неизменяемый
файл для проверки членства. База выпуска — `b99ff3e8898e1f37dae914672701d81056ea6177`
(2.1.36), кандидат приложения — 2.1.37.

## Проверки и откат

- AC-1. Изменённый только по CaseTypeID Case v2/v3 проходит проверку формы.
  Файловая проверка и вход импорта отклоняют `CT99` до записи.
- AC-2. `--verify-only` для стандартных v2 и v3. Проверки PostgreSQL для импорта,
  действующих девяти Case, сохранения 55 целей и исполнения с имитацией LLM.
- AC-3. Проверки публикации в PostgreSQL для отсутствующего и подменённого
  XLSX, существующего Case с неизвестным ID, повторной публикации и чтения
  ранее опубликованного каталога по его checksum и membership.
  Изолированный стенд восстанавливает исходный manifest из проверенной
  квитанции выпуска. Проверка сверяет локальные ссылки Case, M2 и runtime.
- Локальный минимум — backend, HTTP, PostgreSQL integration и `git diff --check`.
  Фактические результаты и SHA фиксируются в передаваемом `STATE.md`.
- Откат — `git revert <candidate-sha>`. Опубликованные каталоги и AS
  продолжают ссылаться на свои сохранённые зависимости.
