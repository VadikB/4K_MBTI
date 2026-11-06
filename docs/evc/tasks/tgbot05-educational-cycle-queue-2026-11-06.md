# TGBOT-05: admission учебного назначения в очередь Cycle

## Результат

Повторный вызов `POST /integration/v1/educational-contexts/prepare` после human
admission находит active assignment, проверяет полный канонический
`acquaintance.preparation_scope` и ставит существующую
`product_cycle_preparation_queue`. Завершённая операция возвращает реальный
`cycle_id`; queued/running возвращает `preparing`.

## Границы и traceability

- M1 `1.4` / Change 01 И-2, И-3, И-6 → Cycle подготавливается, но не стартует;
  PM-03 остаётся владельцем подготовки, PM-04 не запускается.
- M3/M4/M5/M7 refs не синтезируются: published Program, confirmed questionnaire,
  active assignment/source binding и ready PersonalizedProfile проверяются
  действующим W02/M4 gate.
- Pending assignment интеграции не активируется автоматически. Runtime assignment
  создаётся существующим администраторским admission path.
- Не входит: human-действия публикации/подтверждения, запуск Cycle и выдача Case.

## Совместимость и ошибки

- Повтор до завершения читает ту же semantic/idempotent queue operation.
- Pending assignment не размножается; после admission выбирается active assignment.
- Terminal queue failure проецируется как
  `awaiting_admission/CYCLE_PREPARATION_FAILED`, без фиктивного Cycle.
- `external_cycle_id` записывается только для completed queue result.

## Проверки

- Адресный HTTP → 9 PASS; полный HTTP → 117 PASS, 12 deselected.
- PostgreSQL integration → 3 PASS.
- `py_compile` и `git diff --check` → PASS.
- LLM → NOT_RUN, стандартный набор его не включает.
- CI → NOT_RUN до push/PR.

## Действия выпуска

`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`.

## Откат

Вернуть endpoint к `awaiting_admission`: не вызывать queue и не менять active
assignment. Уже созданный prepared Cycle сохраняется как immutable runtime state.
