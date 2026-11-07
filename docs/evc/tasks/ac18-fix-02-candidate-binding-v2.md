# AC18-FIX-02 / P2-AC01 — версия протокола с привязкой review к кандидату

## Результат и область

После слияния #188 PR #189 обновлён от
`origin/main@a4f825d7970da9d62467e7e84ed1b11543941986` (2.0.80),
кандидат приложения 2.0.81. По решению владельца подготовлен отдельный draft
`m5_functional_protocol` 2.0.0 в
`assessment_definitions/prompts/m5_functional_protocol/v2`. Новые Cycle получают
его через `DEFAULT_DEPENDENCIES`; старые frozen Cycle по-прежнему разрешают свой
`v1` и не меняют сохранённый execution manifest. #188 уже слит в `main`.

Tester и challenger v2 возвращают `candidate_checksum` рядом с `checks`.
Сервер рассчитывает checksum фактического concrete candidate, передаёт его в
каждый batch и отклоняет отсутствующую или несовпадающую декларацию как
`TECHNICAL_ERROR` по точным `check_id`; admission становится `INCOMPLETE`.
Старый v1 принимает прежний формат `checks` без нового поля. Различаются
отсутствующий и неполный `adversarial_review`.

Это техническая корреляция ответа с переданным кандидатом. Echo checksum не
доказывает, что модель *содержательно* проверила именно этот AS, и не является
новой методологической нормой или подтверждением качества реального провайдера.

## Источники и прослеживаемость

- Процесс: `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`,
  `docs/evc/review-checklist.md`; Product Architecture/Registry, Change 01 и
  task manifest прочитаны ранее в этом чате. Дополнительный адресный источник:
  `assessment_definitions/prompts/m5_functional_protocol/v1/{manifest.json,tester-addendum.md,challenger.md,json-retry.md}`.
- v1 addendum запрещает новый верхнеуровневый ключ. Поэтому v1 оставлен
  неизменным; новый несовместимый формат живёт только в `v2` с собственным
  manifest и SHA-256 каждого файла. Владелец подтвердил последовательный
  Ready/merge PR #185–191 и deploy-test. Отдельная публикация предметного
  артефакта не разрешена и не выполняется.
- Правило: `P2-AC01` в переданном пакете → versioned output contract →
  `Api/m5_functional_generation_service.py` и `Api/m5_functional_tester.py` →
  unit/HTTP-PG fixtures. Владение: PM-03; PM-04 и данные участника не меняются.
- Старый запуск `64344f28-e9de-4bcc-9173-27376a33ea0b` не имеет доступного
  первичного provider trace. Исправление его причины не заявляется;
  `PREP-DIAG-01` остаётся отдельным UNKNOWN.

## Совместимость, проверки и риски

- `Api/cycle_execution_manifest.py` меняет default только для будущих Cycle;
  сохранённые manifests указывают точный путь и checksum старого пакета.
- `build_input_snapshot` проверяет manifest и SHA-256 protocol files; ref версии
  попадает в frozen snapshot. Для прежнего snapshot без этого ref применяется
  формат v1, привязанный к уже зафиксированным путям.
- Отсутствующий checksum, чужой checksum tester/challenger, отсутствие/неполнота
  protected review и корректный fixture проверены адресными тестами. Старый
  v1 fixture подтверждает обратную совместимость. Невалидный JSON уже покрыт
  `test_malformed_provider_json_is_retried_once_without_salvaging_fragments`.
- Адресные unit: 51 PASS; backend: 966 PASS, 356 deselected, 1 существующий
  Starlette deprecation warning. Изолированная PostgreSQL 16: product-path
  HTTP/PG 8 PASS, F05 runtime matrix 1 PASS. Реальный LLM — NOT_RUN, CI/Ready —
  NOT_RUN, browser — NOT_RUN (UI не изменён).
- После обновления от #188: `npm run ready:prepare -- --candidate 2.0.81`,
  `npm run lint:js`, frontend 150/150, backend 974 passed / 357 deselected,
  HTTP e2e 108 passed / 12 deselected — PASS. Три SHA-256 v2 совпадают с
  manifest. Полный CI обновлённого head — PENDING; он обязателен перед merge.
- Схема/миграция/публичный API/права/персональные данные — без изменений.
  Риск: реальный provider может не соблюдать новый ответный формат; в этом
  случае система fail-closed, а не допускает AS. Для подтверждения provider
  остаётся отдельный ограниченный план после итогового SHA и разрешения.
- Откат: вернуть default dependency и `PROTOCOL_PACKAGE` на `v1`, не удаляя
  `v2`, чтобы уже созданные snapshot продолжали разрешаться; для кода — revert
  локального коммита до merge. Существующие snapshots не переписывать.

## Состояние

Активная ветка `codex/ac18-fix02-tester-candidate-binding`, PR #189. Следующий
шаг — commit/push кандидата, base `main`, Ready, полный CI точного head,
проверка свежего `main`, затем squash-merge. `artifact_publish=false`,
`llm=false`; deploy-test следует только из разрешённого merge приложения.
