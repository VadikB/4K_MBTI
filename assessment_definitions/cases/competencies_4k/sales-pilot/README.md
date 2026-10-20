# Sales pilot M5 package

`0.1` — воспроизводимый draft-пакет девяти `CASE.SPEC.01–09` и выбранных Sales AS
для базовой роли `specialist_expert`. Источник — handoff revision `2026-10-19/2`.
HR и mini cases не входят. Пакет не опубликован и имеет `runtime_enabled=false`.

Сборка из переданного каталога `sources/`:

```bash
.venv/bin/python scripts/build_m5_sales_package.py /path/to/handoff/sources --dry-run
.venv/bin/python scripts/build_m5_sales_package.py /path/to/handoff/sources
.venv/bin/python scripts/build_m5_sales_package.py --verify-only
.venv/bin/python scripts/import_m5_case_package.py --package-dir assessment_definitions/cases/competencies_4k/sales-pilot/0.1
```

Последняя команда без `--apply` не подключается к БД. Для транзакционного импорта и
read-back добавить `--apply` только с настроенной изолированной БД. Публикация в
каталог и пользовательское предъявление требуют отдельных QA/admission решений.

Артефакты:

- `case-package.json` — канонический schema v3 package с точными author snapshots;
- `sources/` — 18 исходных JSON и manifest выбора с исходными bytes/SHA-256;
- `mapping-report.json` — проверяемая связь Case ↔ Sales AS ↔ IndicatorID;
- `participant-preview.json` — только явно доступная при старте проекция;
- `verification-report.json` — границы выполненной статической проверки.

Case 06 сохраняет provenance из source selection manifest: полученный отдельно JSON
text, без утверждения о принадлежности исходному ZIP. Schema v2 и исторический пакет
пяти `CASE-TDISC` не изменены и продолжают проверяться прежним builder/test набором.

После SLS02 каждый Case v3 содержит `participant_presentation` с точной ссылкой на
выбранную Sales AS, раздельными открытыми полями и allow-list стартовых материалов.
P00 материализуется как вводная, поэтому не дублируется в `initial_materials`.
Допустимая подстановка `organization_name` объявляется source-backed target-ами;
она не разрешает менять задачу, сложность, цели, ресурсы или полномочия. Сценарные
правила последующих раскрытий остаются SLS03, поэтому `runtime_enabled=false`.
