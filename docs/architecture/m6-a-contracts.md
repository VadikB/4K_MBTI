# Технический контракт M6-A v1

02.10.2026. Решение для реализации задачи 1 по поручению пользователя «делаем».
Это конкретизация [ADR-002](../adr/002-cycle-as-dialogue-contracts.md), не утверждение
всего ADR, не опубликованный API и не реализованный runtime.
Основания: M1 v1.4 M1.6–8; M6 v1.8 M6.1–5; Change 01 И-4/6.
Точные оригиналы — [SourceSet](../methodology/source-sets/2026-10-01/manifest.json).

## Граница и владение

M6 — самостоятельный модуль PM-05. PM-04 владеет Cycle/Session/AS/Dialogue,
их переходами и закрытием. PM-05 не создаёт второй Cycle и не меняет состояние AS.
LU-05.1 строит Fragment/BS; LU-05.2 — Evidence/EB; LU-05.6 предоставляет основания
в пределах прав. IA/C-54 относятся к следующему шагу LU-05.3; расчёты — LU-05.4.
Физическая реализация Evidence/EB закрепляется за M6-A, будущего IA — за тем же
модулем. Общая основа использует эти записи, не создаёт второй набор таблиц.
Перед началом записи проверить, не появились ли параллельные реализации после базового SHA.

## C-45 и нормализованный вход PM-05

Существующий C-45 schema_version=1 остаётся неизменным. PM-05 принимает handoff_id
через серверный адаптер `m5_c45_v1_to_m6_v1`; клиент не передаёт произвольный материал.
Внутренний envelope: contract_code=`M6.EvidenceInput`, contract_version=1,
message_id=handoff UUID, correlation_id=request UUID, source_set_ref,
payload_checksum, checksum_kind, payload. Это адаптация C-45, не новый отправитель.

| Поле payload | Источник и обязательная проверка |
| --- | --- |
| cycle_id, session_id | UUID из m5_cycles/m5_cycle_sessions по DB ID refs; проверить FK Session→Cycle и AS→Session/Cycle, checksum исходных refs |
| as_id | UUID AS из handoff; сопоставить со snapshot и записью AS |
| dialogue_id | Стабильная строка `as:<as_id>:dialogue:1`; отдельный namespaced ID, один Dialogue на AS; не генерируется при повторе |
| mode | interim → interim; final → final_as; другие значения отклоняются |
| material_revision | Объект boundary_sequence, material_sha256, checksum_kind; hash нормализованного материала до включённой границы |
| last_included_turn_id | Последний фактический Turn по sequence_no либо null при отсутствии Turns |
| as_snapshot_ref, execution_payload_ref, handoff_ref | Проверить разрешимость, версию и hash; сохранить исходные refs и вид канонизации |
| indicator_targets | Точное множество AS IndicatorID/M2Version, без расширения и потери целей |
| criteria | Полные M2 критерии каждой цели: функция, продукт, EP, RF, Boundaries, L0–L3, Component/Skill; source refs и hashes |
| initial_presentation | participant_payload снимка AS и событие/основание его предъявления; если факт доступности не восстановим, SOURCE_UNRESOLVED |
| turns, events | Фактические ID, авторство, порядок, содержание и связи; ничего за границей handoff |
| materials, observability | Frozen execution/AS, точные условия цели, факт и порядок доступности; скрытые материалы явно отделены от предъявленных |
| context | Разрешённая проекция роли, полномочий, задачи, условий; версия проекции; raw profile не копируется |
| closure | Для final_as — существующее событие закрытия, причина, граница; для interim — конец сценария и открытость на границе |
| usage_scope, admission | Серверные данные AS; qa не становится assessment от параметра клиента |

Состояние проверяется относительно сохранённой границы: исторический interim
можно разобрать как исторический материал, но нельзя применить к изменившейся AS
как актуальное решение. M6-A вообще не принимает решений о продолжении.
Final требует закрытого Dialogue; terminated не нормализуется в closed адаптером.
Прекращение исправляется владельцем PM-04 (F01). Новые Turns после scenario_end — F02.

M2 package version и версии отдельных паспортов не взаимозаменяемы. Resolver проверяет
точное соответствие target→criterion→Component→Skill и содержимое закреплённого пакета.
При отсутствии обязательного поля нет вызова LLM и fallback к legacy.
Начальный ввод и материалы не извлекаются из текущего Case поверх frozen refs.

## Контрольные суммы и проекция

Файлы: sha256_bytes — SHA-256 исходных байтов.
M5 JSON: m5_canonical_json_lf_v1 — UTF-8 JSON, ensure_ascii=False, sort_keys=True,
separators=(',', ':'), один завершающий LF; существующий m5_case_runtime.checksum.
Новый envelope/snapshot M6: definition_json_v1 — те же параметры JSON без LF,
существующий assessment_configuration.definition_checksum. Значения предварительно
валидируются как JSON-типы; даты/UUID преобразуются в строки до hash, NaN запрещён.
Тип hash хранится рядом со ссылкой; один digest не пересчитывается другим алгоритмом.
Входной snapshot включает разрешённый материал и критерии, а не только ссылки на
изменяемые таблицы. Повтор читает сохранённый snapshot.

Проекция context_v1 допускает только предметные поля: base_role, role_description,
responsibilities, authority, task_context, constraints. Названия полей исходного M4
отображаются явным адаптером после проверки его схемы; неизвестные поля не копируются.
Имена, email, телефоны, внешние user/organization identifiers не входят в AI payload.
Свободный текст также проверяется на идентифицирующие сведения; при невозможности
получить безопасную проекцию — отказ передачи, а не очистка только ключей JSON.
Обезличивание Dialogue должно сохранять адресацию: если нужна замена текста, хранить
обратимое серверное отображение spans, не считать координаты изменённой строки исходными.
Первый provider smoke использует только синтетические данные.

## Выход EvidenceAnalysis v1

Каждый объект имеет ID, действующий внутри immutable analysis revision.
Fragment: id, turn_id, start, end, quote. Координаты — Unicode code points,
нулевой start, end exclusive; quote == original_turn_text[start:end]. Без нормализации
пробелов/Unicode перед проверкой. Только пользовательские Turns одной AS.
BS: id, fragment_id (ровно один), observation, form_description,
context_refs с объяснением значения реальных Turns/materials/events. BS не имеет уровня.
Evidence: id, indicator_id, m2_ref, type=Simple|Composite, interpretation,
bs_ids, fragment_ids, attribution (function/product/EP/Boundaries), context_refs,
limitations. Composite содержит обоснование единого вывода и значимый порядок, если нужен.
Evidence имеет фактическое непустое основание; оно не создаётся для заполнения пустого EB.

Bundle revision: stable bundle_id, as_id, indicator_id, analysis_revision_id,
evidence_ids (0..N), opportunity основания/ограничения, contradictions и dialogue ref.
Для каждой цели входа сохраняется запись разбора/EB; пустота не является IE/L0.
Неясная связь/нерелевантность сохраняются отдельными attribution_notes с фактическими
refs и конкретной причиной; они не получают фиктивное Evidence.
Общий материал сохраняет общие ID; повторная формулировка не является независимым основанием.
Нельзя терять ранние слабые/противоречащие проявления. Semantic correctness проверяется GC,
а не только наличием полей. Поля IA/level/score/confidence_number в этой версии запрещены.

## Данные, ключи и атомарность

| Таблица, проект | Ключи и назначение |
| --- | --- |
| m6_processing_requests | UUID PK; AS FK; handoff FK; mode; input/mechanism snapshots и hashes; status; unique(AS,idempotency_key); unique(AS,mode,input_hash,mechanism_hash); lease_token/expires_at |
| m6_processing_attempts | UUID PK; request FK; unique(request,attempt_no); lease token; intended/sent/provider/response trace; технический статус и безопасная ошибка |
| m6_analysis_revisions | UUID PK; unique(request_id); AS FK; input/mechanism refs; immutable validated JSON Fragment/BS/Evidence/notes; output checksum; accepted_attempt FK |
| m6_evidence_bundles | UUID PK; AS FK; indicator_id; unique(AS,indicator_id); нормативная идентичность проверяется frozen AS |
| m6_bundle_revisions | bundle FK + analysis_revision FK, составной PK; evidence_ids и основания; принадлежность одной AS проверяется составными FK/транзакцией |

JSON не отменяет проверки ссылок и авторства. Внешний потребитель получает revision+object ID.
Новая обработка добавляет revision, но не вторую логическую пару EB. Старые revisions immutable.
Для повторов сравнивается полный canonical payload, не только строковый request key.
Другой payload под тем же ключом — IDEMPOTENCY_CONFLICT. Другой ключ для того же входа/
механизма возвращает существующий request. После failure повтор создаёт attempt того же request.
Новая версия механизма или входа создаёт новый request и историю.

Короткая транзакция создаёт/захватывает request и attempt; соединение освобождается до AI.
Вторая транзакция проверяет lease token, валидирует результат и атомарно сохраняет analysis,
bundle revisions и succeeded. Просроченная попытка не может победить новую через поздний ответ.
После crash до commit повтор безопасен; после commit чтение возвращает тот же результат.
Повтор внешнего вызова возможен, дублирование принятого эффекта — нет.
Statuses: queued/running/succeeded/failed; детали retry хранятся технически, без IA.

## AI и артефакт

Пакет: assessment_definitions/prompts/m6_evidence/v1/, prompt.md и manifest.json.
Manifest v1: id=m6_evidence, version=1.0.0, status=draft, scope=m6_evidence_qa,
owner=PM-05 (роль, не имя принимающего), source refs M6/M2, artifacts(name,sha256),
input_contract=M6.EvidenceInput/1, output_contract=M6.EvidenceAnalysis/1.
Новый loader проверяет этот ограниченный формат; существующий M5 manifest не переопределяется.
QA activation выбирает явный ref и копирует в mechanism snapshot точный текст/manifest,
schema, handler, provider/model/parameters/limits. Draft не становится published assessment.
Пользовательская публикация — следующий отдельный допуск по платформенному lifecycle.

Использовать существующий gateway/trace; выделить только технический executor для
проверенного snapshot prompt, если текущий helper не принимает текст. Не читать текущий
v1 файл при replay и не создавать универсальный framework. Недоступный механизм,
schema mismatch, timeout и неверные ссылки — технический failure. Старый evaluator не fallback.
Controlled adapter — только тестовая зависимость, не пользовательский переключатель.

## HTTP и C-54

Проект маршрутов: POST /admin/m6-evidence/requests (handoff_id, mechanism_ref,
idempotency_key), GET /admin/m6-evidence/requests/{request_id},
GET /admin/m6-evidence/analyses/{revision_id}. Создание возвращает 202 и status ref;
повтор — тот же request. Только серверная проверка superadmin QA полномочий и usage_scope=qa.
Прямой доступ пользователя к Dialogue/trace не вводится; read endpoints повторяют проверки.
В обычном response нет raw AI trace; диагностическое чтение требует тех же QA прав
и явного разрешённого набора полей. Ошибки без содержимого Dialogue и секретов.

Полный C-54/1 следующего этапа: echo AS/dialogue/material revision/mode; для interim
Indicator/M2/EB revision, подтверждённые основания, неопределённость, недостающий признак,
need=clarification|new_action и ограничения; для final_as IA refs и причины отсутствия.
Это не готовый вопрос пользователю. Применение stale interim запрещено.
M6-A возвращает служебный статус, не C-54 и не technical_received под новым именем.

## Совместимость и проверки

Expand migration только добавляет M6 таблицы/индексы; M5 и legacy записи не удаляются.
Не импортировать shadow evidence как M6. Старые readers продолжают работать;
новые маршруты доступны только с совместимой schema и explicit QA activation.
Откат останавливает новые requests, завершает/останавливает worker управляемо и сохраняет
новые данные и reader. Downgrade с удалением таблиц/снимков не применяется.

Приёмка T-A1–A8 и файлы тестов — в [карточке PR](../evc/tasks/m6-a-implementation.md).
F01/F02 блокируют только свои ветви; полный M7/M8 и основной маршрут не блокируют QA
валидного handoff. Отсутствие обязательного frozen входа блокирует именно его обработку.

## Фактическое исполнение M6-A

Реализовано в рабочем diff от 02.10.2026. Нормализованный payload хранится целиком
в request.input_json с input_hash; transport identity — handoff_id, request UUID,
mode и SourceSet refs нормативных критериев. Отдельная копия envelope с тем же
payload не хранится. M5 envelope сохраняется по исходному handoff_ref.
Для нескольких транспортных ключей одного эффекта введена m6_request_keys;
request.input_hash и mechanism_hash защищены от изменения DB trigger.
Analysis/bundle revisions и bundle identity также защищены от UPDATE/DELETE.

HTTP prefix существующего router — /users: фактические пути
/users/admin/m6-evidence/requests и /users/admin/m6-evidence/analyses/{revision_id}.
POST требует synthetic_material_confirmed=true; подтверждение хранится с created_by.
До отдельной реализации обезличивания произвольных текстов разрешён только
подтверждённый синтетический QA-материал. Allowlist профиля ограничен base_role;
полномочия/условия берутся из frozen participant_payload. Raw profile не передаётся.
Это ограниченный QA допуск, не обещание автоматического обнаружения всех PII.

Первый запуск идёт BackgroundTasks, queued/expired requests подбираются worker при
старте приложения и каждые 2 секунды. Failed request повторяется явным POST с тем
же ключом; новая attempt сохраняет прежнюю ошибку. Worker не читает текущий prompt
или M2 после enqueue. Runtime модель/параметры фиксируются в mechanism snapshot;
технические параметры вызова/лимита/lease находятся в manifest пакета.
Реальный transport smoke и экспертные GC пока NOT_RUN.
