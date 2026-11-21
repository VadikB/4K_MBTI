# Банк функциональных кейсов M5

Пакет `0.6` включает девять паспортов `CASE.SPEC.01–09` для `specialist_expert`.
`passport-index.json` связывает CaseID и версию с проверяемым паспортом.
CaseVersion schema 4 хранит проектные условия, состав CT, применимость и точные
цели M2. Контракт результата AS и prompts версионируются отдельно в
`assessment_definitions/prompts/m5_functional_passport/v1`.

Сборка, проверка и просмотр плана импорта:

```bash
.venv/bin/python scripts/build_m5_functional_package.py \
  assessment_definitions/cases/competencies_4k/functional-personalization/0.6
.venv/bin/python scripts/build_m5_functional_package.py --verify-only
.venv/bin/python scripts/plan_specialist_program_release.py
```

На вход можно подать корзину паспортов с `passport-index.json` либо исходный
`Package_index_v0.2.json` вместе с файлами `Case`. Сборщик проверяет исходные SHA-256
и переносит в банк поля паспорта, необходимые подготовке. При нескольких
`ApplicableBaseRoles` индекс указывает код применимой ветви для данной CaseVersion.

Архивные пакеты `0.2–0.5` сохраняют исходный состав. Для повторной проверки
`0.5` укажите `--historical-0.5 --verify-only`. Новые ситуации по старому
закреплённому CaseVersion тоже используют его паспорт; предъявленные ситуации
читаются из своих снимков.

Порядок включения, диагностики и отката описан в [карточке M5-01](../../../../docs/evc/tasks/m5-01-bank-without-author-as/STATE.md).
