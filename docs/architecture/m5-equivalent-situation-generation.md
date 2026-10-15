# M5 Equivalent Situation Generation v1

Дата: 15.10.2026. Статус: draft runtime foundation. Основание: UX-P02 rev 1.0,
UX-P01 rev 2.0, M1 v1.4 §§5–6, M5 v1.1/CasePassport v1.1, Change 01.

## Граница

PM-03 создаёт candidate AS той же `CaseID`/версии и сохранённого M4 profile.
Генератор не меняет маршрут, позицию, таймер, цели M2 и не предъявляет candidate.
P01 атомарно переключает уже сохранённую допущенную candidate AS через
`GeneratedCandidateReplacementProvider`. P03 отдельно определяет момент активации.

Обычный provider по умолчанию отсутствует. Единственный пакет в репозитории —
`qa_equivalent_generation/v1`, `draft`, `qa_only`; он доказывает механизм, но не
допускает ни один продуктовый Case к генерации в assessment.

## Артефакт и проверки

Variability contract лежит в существующем M5 Case-контуре и фиксирует Case/version,
allowed/immutable JSON paths, связанные значения и критерий содержательного отличия.
Schema: `assessment_definitions/schemas/m5-variability-contract-v1.schema.json`.
Изменение вне `allowed_paths`, цели/роль/полномочия, противоречащие связанные поля,
недостаточное отличие или неприменимый scope дают явный недопуск. Структурный PASS
не заменяет `content_admission`; assessment требует `published` + `approved`.

## Операция и данные

`m5_equivalent_generation_operations` хранит idempotency key, полный обезличенный
input, provider config ref, input/output checksums, lease/attempt, validation,
ошибку и candidate AS ref. M4 identity, email, контакты, ответы, IA и предполагаемый
уровень не входят в input. Старое содержание входит только как anti-repeat basis.

Фазы разделены:

1. `begin_generation` фиксирует snapshot и request identity в короткой транзакции.
2. `claim_generation` выдаёт единственный lease.
3. `run_provider` не принимает DB connection; LLM/сетевой вызов не держит транзакцию.
4. `complete_generation` заново блокирует Cycle/position/old AS, проверяет срок и
   terminal state, независимо валидирует output и сохраняет новую immutable AS.

Поздний output сохраняется как `rejected_late` и не создаёт AS. Повтор успешного key
читает сохранённую operation/candidate. Конкурирующие workers не получают два lease.

## Совместимость и откат

Изменение аддитивно. Существующие Case/AS не переписываются. Откат отключает endpoint
и provider, сохраняя operation snapshots и candidate AS; незавершённые операции
остаются проверяемым аудитом. Публикация content contract выполняется новой версией,
а не изменением draft на месте.
