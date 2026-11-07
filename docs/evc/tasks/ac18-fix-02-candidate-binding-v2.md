# AC18-FIX-02 / P2-AC01 — версия протокола с привязкой review к кандидату

## Результат и область

По решению владельца в этом чате после запроса «делаем следующую задачу» подготовлен
отдельный draft `m5_functional_protocol` 2.0.0 в
`assessment_definitions/prompts/m5_functional_protocol/v2`. Новые Cycle получают
его через `DEFAULT_DEPENDENCIES`; старые frozen Cycle по-прежнему разрешают свой
`v1` и не меняют сохранённый execution manifest. Эта ветка зависит от
`codex/ac18-fix02-tester-correlation` (`5dbcf219`, draft PR #188).

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
  manifest и SHA-256 каждого файла. Владелец разрешил подготовить новую версию
  ответом «да» в этом чате. Отдельного допуска на publication/Ready/merge нет.
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
- Схема/миграция/публичный API/права/персональные данные — без изменений.
  Риск: реальный provider может не соблюдать новый ответный формат; в этом
  случае система fail-closed, а не допускает AS. Для подтверждения provider
  остаётся отдельный ограниченный план после итогового SHA и разрешения.
- Откат: вернуть default dependency и `PROTOCOL_PACKAGE` на `v1`, не удаляя
  `v2`, чтобы уже созданные snapshot продолжали разрешаться; для кода — revert
  локального коммита до merge. Существующие snapshots не переписывать.

## Состояние

Активная ветка `codex/ac18-fix02-tester-candidate-binding`, база `5dbcf219`.
Push, PR, Ready, merge, deploy, version bump и real-provider run не выполнялись.
Следующий шаг — завершить review/diff/checksum, сделать локальный commit, затем
отдельно согласовать публикацию draft PR на базе #188. По плану владельца все
PR готовятся до финального последовательного merge.
