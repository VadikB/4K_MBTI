# P4K_M5_BANK_PUBLISH_01 v1.1

## Основание и границы

Запуск запрошен владельцем 19.11.2026. Постановка задаёт локальный кандидат
на свежем `main` и техническую приёмку AC-1–AC-3 на выделенном PostgreSQL
с синтетическими данными. База `fd6d4e0c24981246a939199de42672322d1999b5`,
Product 4K 2.1.34. Ветка `codex/p4k-m5-bank-publish-01`.

AUD-01 воспроизведён на базовом SHA штатными `--apply-import` и
`--publish-admitted-catalog`. Импорт сохраняет WORKING `@0.5`, публикация
завершается с `M5_PACKAGE_VERSION_CONTENT_CONFLICT`.

## Источники и решение

- [Registry](../../architecture/product-4k/registry.md),
  [Change 01](../../architecture/product-4k/1.0/updates/2026-10-01/README.md)
  (И-1, И-3, И-6) и [ADR-002](../../adr/002-cycle-as-dialogue-contracts.md)
  задают область PM-03 / LU-03.1, передачу точных версий Case → AS и сохранение
  исходного snapshot. Минимум проверки и выпуск сверены с [рабочим
  циклом](../agent-workflow.md), [матрицей](../verification-matrix.md) и
  [рецептом артефактов](../artifact-recipe.md).
- M5 Методология и Паспорт Case v1.1 сверены по SHA-256 из [SourceSet
  manifest](../../methodology/source-sets/2026-10-01/manifest.json).
  M0 v1.0 выбран в Registry, оригинал отсутствует в SourceSet. Технические
  ссылки используют существующий контракт хранилища и каталога.
- [ARCH30-ADD01](arch30-add01.md) фиксирует выбор `CASE.SPEC.01–09` и базовую
  роль `specialist_expert`. Выпуск сохраняет выбранный состав, авторские версии
  и IndicatorIDs. Основания и проверка области допуска следуют [контракту
  каталога](../../architecture/product-4k/m5-catalog-integrity-contract.md).

Команда публикации выпускает производный DB-пакет `0.5-admitted.1` и runtime
`1.2.1` со ссылками и checksum исходных материалов. Case получает техническую
версию с суффиксом `-admitted.1`. Manifest пересчитывает SHA-256 сохранённого
пакета, скомпилированных правил и runtime bindings. Каждый binding разрешается
в рамках импортированного пакета по CaseID, версии и checksum. Исторические
ссылки продолжают указывать на прежние DB-строки.

Для изолированной приёмки команда принимает `--usage-scope qa`. Выпуск QA
использует отдельные версии с суффиксом `-qa` и происхождение `synthetic_test`.
Обычный `assessment` сохраняет действующий допуск `human_review` и обязательное
основание решения. Scope, организация и точные DB-версии закрепляются в
неизменяемом каталоге. Публикация использует одну транзакцию.

## Проверки и откат

| Критерий | Проверка |
| --- | --- |
| AC-1 | Импорт, публикация и readback через CLI. Сверка девяти Case, manifest, runtime bindings, scope и организации. |
| AC-2 | Повтор обеих команд, конфликт изменённого package/rules под прежними ключами, отказ при пустом основании. |
| AC-3 | Чтение WORKING и прежнего AS по UUID, сверка checksum и execution payload, отказ для Case и runtime вне каталога, отдельный выпуск assessment. |

Регрессия находится в `tests/integration/test_m5_functional_package_db.py`.
Применимы backend, PostgreSQL integration и `git diff --check`. Точный SHA и
результаты фактических прогонов фиксируются в передаваемом отчёте STATE.

Откат кода выполняется через `git revert` коммита исправления. Для ранее
опубликованного контура выбирается прежняя подтверждённая
`assessment_configuration` со ссылкой на её каталог. Новые неизменяемые
записи сохраняются для аудита. Для нового выпуска поверх исторического каталога
указать свободные `--catalog-version` и `--idempotency-key`.
