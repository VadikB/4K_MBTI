# R10 C01/Sales — локализация первого real-provider pilot

## Сохранённое основание

- Полная синтетическая попытка: `r10-c01-sales-real-provider-attempt-raw-2026-10-26.json`.
- SHA-256 файла: `a9af0eee39a25813253ed18df9ac657cfc59243bae9a4aebd2f215c01c6c0530`.
- Внутри сохранены frozen inputs, provider request metadata, исходная и repair AS,
  deterministic validation, tester/challenger decisions, версии и checksums. HTTP
  Authorization и credential отсутствуют.
- Candidate до исправления: `0ead559a36346718f301f849590086e14f1005f0`.

## Разбор блокирующих находок

### Остаточные «Елена / рабочая сводка»

Фрагмент frozen author provenance:
`IndicatorTargetLayers.author.targets[K1.I01].Конкретное условие` — «интерес Елены к
рабочей сводке…». Фрагмент concrete adapted projection той же исходной generation:
`IndicatorTargetLayers.adapted.targets[K1.I01].Конкретное условие` — «интерес Артёма к
своевременному закрытию сделок…»; для K1.I14 adapted target также использует Артёма.

Контракт `m5-functional-indicator-two-layer` требует неизменяемый author-layer и прямо
говорит, что source-only имена и предметы являются закрытым provenance и не обязаны
буквально присутствовать в конкретной AS. Поэтому старое имя само по себе не является
дефектом адаптации. Находки `STALE_AUTHOR_NAME_IN_OBSERVABILITY` и
`PARTIAL_SUBSTITUTION_IN_OBSERVABILITY` ошибочно применили профессиональную проверку к
bound author-view. Классификация: **дефект передачи входа tester/challenger**, не дефект
исходной generation и не основание ослаблять tester.

Исправление: semantic consumers получают `candidate_as` как concrete adapted-view;
неизменяемые `author_indicator_layer` и `adapted_indicator_layer` передаются отдельно.
Deterministic проверка сохранности author checksum и состава target остаётся прежней.

### Потеря `material_refs/event_refs/character_refs/authority_refs/author_mapping`

В исходной generation adapted K1.I01 содержит `material_refs=[M01,M02]`,
`event_refs=[E01_DOCUMENT,E02_REPLY]`, `character_refs=[ARTEM]`, допустимые authority
refs и author mapping. После repair все четыре adapted targets этих полей не содержат,
и deterministic check `indicator_adaptation_references` корректно возвращает FAIL.

Контракт требует эти references для каждого adapted target и запрещает неизвестные
ссылки. Классификация: **дефект repair generation, вызванный неполным repair input**:
repair получил bound AS с author `IndicatorObservability`, но без явного двухслойного
контракта и списка обязательных полей. Это не дефект компилятора: компиляция не
запускалась после admission FAIL; binder корректно не восстанавливает отсутствующие
provider refs автоматически.

Исправление: repair получает concrete adapted-view, отдельные author/adapted layers,
versioned `indicator-adaptation-contract` и тот же обязательный список полей, что
первичная generation. Автоматического переноса refs или обхода validation нет.

### `TECHNICAL_ERROR` защищённых проверок

Эти статусы появились из правила adversarial review: заявленный PASS без заполненного
опровержения не принимается. Это корректное защитное поведение aggregation, а не
самостоятельный дефект Case или AS. Оно не менялось.

## Адресная проверка

- Сохранённый pilot доказывает различие author «Елена» и adapted «Артём» и проверяет
  concrete view.
- Repair regression проверяет передачу adapted targets, обязательных fields и
  успешную deterministic validation без серверного дополнения смысловых данных.
- `41 PASS`: functional package, snapshot composition, generation service,
  ARCH-A06 runner и acceptance matrix.
- `py_compile Api/m5_functional_generation_service.py` — PASS.
- `git diff --check` — PASS.

Следующий gate: commit исправления, затем ровно один повтор C01/Sales на его exact SHA.
Матрица 27/9/3 до успешного пилота не запускается.
