# Pilot plan / first start — технический контракт v1

05.11.2026. T1 принят владельцем: «принимаем идем дальше» после передачи
[принятого проекта](../evc/tasks/path-pilot-approved-design.md). Локальная реализация
разрешена; публикация/выпуск/платный PATH не разрешены. Это контракт программной
согласованности PM-04, не новая методология или разрешение любой LIMITED.

## Источник → контракт → потребитель

| Основание | Правило | Данные / код | Проверка |
| --- | --- | --- | --- |
| P1–P3/M1–M4 по exact PATH-PILOT-01 v0.1 | Полный M2 и утверждённый план различаются; условия/маршрут сохраняются | pilot_plan_admission; full/planned/outside/uncovered_planned в plan revision | unit snapshot mutations; SQL61/39/22 |
| M1.4–5, Change01 И-2/3, C-24/C-34 | Exact profile/assignment/Case/M2/AS admission | pilot_plan_binding, assessment_start_readiness | SQL scope/revocation; final candidate/stage negatives |
| ARCH-A05/PILOT-120, M7 | Два времени из собственного scoped источника; подготовка не старт | frozen parameter sources; first explicit start | SQL READ ONLY, same AS/0 answers, two concurrent starts |
| T1, ADR-002 snapshots/lifecycle | Нет новой схемы БД/мутации published; новый snapshot — только новой программе/плану | ProgramDefinition.source_refs_json; plan schema_version2 | program checksum / new version; unchanged old fixture |
| Техническая безопасность | Участник не получает скрытые условия/QA/человеческие записи | participant_plan projection | HTTP privacy / unit projection |

M1 v1.4 FROZEN/CURRENT=NO и выбранный Change01 комплект не переключаются.
Нормы M6/M8, prompts, repair и продуктовая агрегация AS не изменяются.

## Формат источника и активация

Версионный источник — assessment_definitions/planning/specialist_pilot_admission/v0.1/manifest.json.
Он `draft`, только для offline сборки; не default и не новый runtime.
`pilot_plan_admission.build_snapshot` проверяет исходные bytes/hash review и P/M
записи, exact payload checksum, состав, маршрут, условия и происхождение notice.
Снимок содержит `contract=m7_pilot_plan_admission/1`, `artifact_id/version`,
`source_manifest_sha256`, `source_files`, `owner_decision_ref`, `review`,
`owner_decision`, `participant_notice`, `snapshot_checksum`.

Полный исторический review envelope сохраняется, включая старый PENDING/NONE.
Последующая человеческая запись принимается отдельно по exact proposal checksum.
Её историческое `runtime_authorization=NONE` не меняется и не заменяется агентом.
Активация возможна только отдельной разрешённой публикацией **новой** ProgramDefinition
с этим snapshot в `source_refs_json.pilot_plan_admission`. Старый published1.1
не редактируется. Builder сам ничего не публикует и не подключается к БД.

Существующий publish_assessment_program получает явный --pilot-plan-package.
Без --publish он, как и прежде, лишь проверяет через БД и rollback; это НЕ безопасная
offline команда. В этой задаче CLI не запускается ни с --publish, ни без него.
Новый номер ProgramDefinition/app и org/actor IDs выпуска назначаются позднее.

При явном штатном подключении новой opt-in программы `assessment_programs.connect`
сохраняет оба принятых времени в existing program-scoped published revision для
точных organization/configuration. Это часть транзакции подключения, не fallback
при подготовке/старте. Повтор подключения не пересоздаёт revision и не сбрасывает
время. В этой задаче подключение выполнено только в owned synthetic SQL fixture.
Подключение использует уже подготовленную схему без вызова DDL; порядок блокировок
connection→timing согласован с first start. SQL-регрессия удерживает реальный
readiness transaction открытым во время подключения следующей synthetic программы.
В API выбора/подключения программы полный admission snapshot заменяется отдельным
`pilot_plan_ref`; `source_refs_projection=PUBLIC_REFS_NOT_EXECUTION_DEFINITION`
предупреждает, что это не полный объект для пересчёта definition_checksum.
Внутреннее хранение, server validation и контролируемый source export используют
исходный неизменённый snapshot; скрытые условия и записи P/M в UI не передаются.

## Снимок плана и lineage

В новой immutable plan revision schema_version2 сохраняется
`pilot_plan_binding={contract:m7_pilot_plan_binding/1, admission_snapshot, program_ref,
profile_ref, assignment_scope, timing_sources, binding_checksum}`.
Program ref содержит DB id/code/version/checksum и exact connection id. Scope —
tenant/recipient/assignment/binding/questionnaire revision и assigning/source actors;
profile ref — точный frozen профиль/его checksum. Значения берутся с сервера, не клиента.

Полный состав остаётся61; плановый39 задаётся утверждённым payload, не union по ходу
ответов. Новые outside_plan_target_ids и uncovered_planned_target_ids отдельны от
прежнего uncovered_target_ids (полный M2 минус проектный маршрут). Статус покрытия
сохраняется LIMITED. В AS сохраняется весь target set Case, не только новый вклад.
Case09 не становится автоматическим резервом/repair. Наблюдаемость условна.

Для создания opt-in проверяются published program/config, собственный checksum
ProgramDefinition, девять exact Case/checksums и исходные QA, M2/catalog/role,
активное назначение/анкета/профиль и собственная published program timing revision.
Исходный runtime planning algorithm не меняется; для принятого плана фиксируется
именно рассмотренный порядок, не динамический выбор удобного подмножества.

## Единый first-start readback

`assessment_start_readiness.read` возвращает `contract=m7_start_readiness/1`,
`can_start`, безопасные `reasons`, cycle/plan revision/checksum/AS/profile/operation
refs и при opt-in минимальный pilot_admission ref. Чтение не запускает schema/bootstrap,
провайдер или часы; проверено настоящей READ ONLY транзакцией.

READY не достаточен сам по себе; неподтверждённый LIMITED, NO_ROUTE, расхождение
источников, пробел внутри плана и неполный final AS admission дают false.
Для functional AS проверяются конечный кандидат/compiled Case, profile/Case/target
связи, generation, tester, challenger, terminal repair ref, check/batch/input/operation
связи и существующая aggregation. PASS_WITH_WARNINGS допускается с admitted=true;
FAIL/INCOMPLETE/false не допускаются. Качество заново не придумывается.

Participant onboarding/dashboard, admin и runner используют это решение. В start
transaction `require` повторяет проверку, удерживает assignment/program connection/
program/timing authority rows и проверяет снова после locks. Порядок Cycle→assignment
сохранён, обратных user/org locks не вводится. Центральный present проверяет тот же
first-start gate: legacy/admin точка входа не получает обход LIMITED.

Активные/paused оценки продолжаются по прежним снимкам и правилам возврата/времени.
Неактивный legacy prepared LIMITED не получает автоматического grandfather-допуска:
неизвестная пригодность остаётся блокером, snapshot не переписывается.

## Совместимость, границы и откат

Новых таблиц/колонок/миграции нет. Старые v1 readers в текущей реализации сохранены;
новая привязка не назначается старым Cycles. Новые additive HTTP-поля не заменяют
существующие; сервер решает, клиент отображает. Полный internal binding не выдаётся
участнику ни через start, ни через runtime/подготовленный план.

До активации откат — убрать код/черновик, БД не менялась. После будущей публикации
остановка новых opt-in запусков выполняется штатным отключением новой программы,
не удалением её/планов/AS. Новые active Cycles должны дочитываться совместимой
сборкой. Автоматический downgrade к2.0.64 после появления v2 Cycles **не заявляется**:
старый код не содержит новой privacy/admission projection. Release R1 обязан сохранить
совместимый reader и проверить recovery/continuation, а не обещать rollback потерей данных.

SQL/HTTP tests имитируют принятие плана и LLM-стадии как SYNTHETIC boundary fixtures;
не подтверждают реальную генерацию/GC, новый human review или итоговый PATH.
Старые component tests S10 и10.5/M4 явно подставляют upstream start permission, а отдельные
новые SQL tests восстанавливают реальный gate и проверяют start/refusal/конкуренцию.
10.5 сначала отдельно проверяет фактический отказ неизвестного LIMITED; подстановка
ограничена двумя стартами для проверки frozen M4/history, не отрицательными правами.
PREP-DIAG-01 сохраняет историческую причину UNKNOWN независимо от этих изменений.
