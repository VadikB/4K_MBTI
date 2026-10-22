# Functional personalization M5 package

`0.2` — воспроизводимый draft-пакет девяти `CASE.SPEC.01–09` для
`specialist_expert`. Паспорта и примеры AS остаются `WORKING` / `TEST_DRAFT`,
`CURRENT=false`; `runtime_enabled=false` не допускает их к оценке людей.

Сборка и проверка:

```bash
.venv/bin/python scripts/build_m5_functional_package.py /path/to/P4K_All9_Functional_v0.2
.venv/bin/python scripts/build_m5_functional_package.py --verify-only
.venv/bin/python scripts/import_m5_case_package.py \
  --package-dir assessment_definitions/cases/competencies_4k/functional-personalization/0.2
```

Последняя команда без `--apply` не подключается к БД. Импорт с `--apply`
допустим только в изолированной test/pytest-БД.

## Миграция и откат

Новый package/version и Case/version добавляются, а не переписывают старые строки.
Начатая AS хранит Case/profile/AS snapshot и checksum, поэтому обновление каталога её
не меняет. Включение для новых запусков возможно только новой публикацией
каталога после QA/admission. Откат — вернуть выбор новых Cycle на прежнюю
опубликованную конфигурацию; запущенные AS продолжаются по своим snapshots.
