# M5: исполняемое представление Case и подготовка Assessment Situation

Статус: технический проект T08.6 / 4.1, 01.10.2026. Это не нормативная редакция
M5, не публикация CURRENT и не допуск пяти WORKING Case.

## Исходная точка и область

Ветка анализа: `codex/architecture-change01-contracts`, базовый commit `0d000fd`.
Задание 4 уже определило schema/package v2, точные `indicator_targets`, независимые
format/Case/AS checks, immutable snapshots и C-34 admission. Проверка XLSX
зафиксирована в [отчёте](../evc/tasks/t08.6-m5-complex-cases-v0.1-validation.md):
исходные ID/ссылки валидны, исполнение и содержательный QA не проводились.

Этот документ дополняет результат исполняемой конструкцией: персонажи и знания,
материалы и видимость, события, условные ветви, модельная проверка, граница
CaseVersion→AS и уточнённый C-34. Общий автомат Cycle/Dialogue и оценивание M6
остаются за заданиями 5–7.

## Решения

1. XLSX — редактируемый authoring master. Перед verify/QA/import создаётся source
   snapshot. Runtime XLSX не читает.
2. CaseVersion — канонический неизменяемый артефакт сценарной конструкции.
   Одна строка `Кейсы` является индексом, а не полным Case.
3. AS — конкретная неизменяемая реализация CaseVersion для одного frozen
   ProfileSnapshot и одной BaseRole. План AS отделён от фактической Dialogue trace.
4. PM-04 получает AS по разрешимой ссылке с checksum и небольшим envelope C-34.
   Ссылка всегда указывает на точный snapshot, не на current package.
5. Сценарий представлен упорядоченными стадиями и ограниченным набором типизированных
   правил/событий. Универсальный исполнитель произвольных графов не вводится.
6. Семантическое условие не исполняется свободным продолжением LLM. Оно возвращает
   ограниченный decision code, confidence не используется как основание оценки,
   а решение сохраняет Turn refs и handler version.
7. Состав предметных правил находится в versioned artifacts. Python/JS содержит
   общий parser/evaluator, технические инварианты, транзакции и ошибки.

## Карта десяти листов XLSX

| Лист / Excel Table | Роль при преобразовании | Каноническое место | Runtime |
| --- | --- | --- | --- |
| `Кейсы` / `CaseCatalog` | Индекс пяти CaseVersion, роль, время, статус | `case_index` и контрольные агрегаты | Каталог M7 после admission; не полный Case |
| `Паспорта` / `CasePassports` | 22 нормативных поля | `passport` + нормализованные refs | Да, через CaseVersion/AS projection |
| `Участники` / `CaseParticipants` | Персонажи, публичная позиция, закрытая карточка | `characters` | Да; закрытая карточка не является предъявленным материалом |
| `Данные` / `CaseData` | Смешанные материалы, события, реакции, расчётные правила | После явного разбиения: `materials`, `event_rules`, `reaction_rules`, `model_checks` | Да, только по правилам доступности |
| `Сценарий` / `CaseScenario` | Стадии и текстовые правила | `stages` и ссылки на rules | Да |
| `Индикаторы` / `CaseIndicators` | Точные цели и проектная Observability | `indicator_targets` | В AS и C-34; скрыто от оцениваемого |
| `Applicability` / `CaseApplicability` | Skills/Components | `applicability` | Каталог M7; отдельно от целей |
| `CaseTypes` / `CaseTypeLinks` | CT и нейтральный порядок | `case_type_refs` | Каталог/QA; порядок не равен исполнению |
| `Варианты` / `FutureCaseIdeas` | Design backlog PROPOSAL | Отдельный непубликуемый design artifact | Нет |
| `Описание` / `ExportDescription` | Provenance, общие правила, source QA claims и словарь полей | Разделить на `source_provenance`, versioned `interaction_policy_ref`, claims | Правила — по ссылке; claims не admission evidence |

### Приоритет источника и дубли

Нормализованный лист является основным источником своей сущности: Indicators,
Applicability, CaseTypes, characters, data и stages. Паспорт остаётся нормативным
представлением 22 полей. Сборщик обязан доказать согласованность дублированных
проекций. Расхождение даёт `SOURCE_CONFLICT` с обеими координатами; ни одна копия
не перезаписывает другую.

Каждый элемент хранит `source_ref`: snapshot checksum, sheet/table, source row,
business key и при необходимости `FieldNo`. Служебные CharacterID/DataID/StepID
имеют область одной CaseVersion и не объявляются новой методологической онтологией.

## Каноническая CaseVersion

```text
CaseVersion
  identity
    case_id, case_version, canonical_checksum
    normative_m5_ref, package_schema_ref, source_snapshot_ref
    lifecycle_status: WORKING | REVIEW | FROZEN
  passport                         # все 22 поля, без потери текста
  case_type_refs[] + composition_logic
  applicable_base_roles[]
  applicability[]                  # SkillID + ComponentID
  indicator_targets[]              # exact IndicatorID + M2 ref + conditions
  participant_projection           # title + поля 8–13
  characters[]
    character_id, public_position, private_knowledge[]
    reaction_constraints[], initial_knowledge_refs[]
  materials[]
    material_id, kind, payload_ref
    known_by[], disclose_to[], availability_rule_ref
  stages[]
    stage_id, order, entry_rule_ref, allowed_rule_refs[], completion_rule_ref
  rules[]                          # ограниченные типизированные правила
  model_checks[]                   # только если предусмотрено Case
  personalization_contract
    allowed_slots[], invariants[], forbidden_changes[]
  scenario_completion
  clarification_boundary
  policy_refs
  source_refs[]
```

`lifecycle_status` источника не равен admission. WORKING Case можно исполнять в
изолированном QA scope, но нельзя выдавать пользователю основного прохождения.

## Видимость, знания и материалы

Метка `INTERNAL/PARTICIPANT` исходника недостаточна. AS builder формирует явные
проекции:

- `participant_initial_projection` — название и поля 8–13 после допустимой
  персонализации;
- `executor_private_context` — персонажи, закрытые знания, правила, цели и QA;
- `material_availability` — материал, знающие субъекты, получатель, момент и условие;
- `evaluator_context` — план и фактическая trace раздельно; наличие private context
  не доказывает предъявление или Evidence.

Для каждого knowledge/material:

```json
{
  "material_id": "...",
  "kind": "document|fact|system_update|reaction_rule|model_rule",
  "payload_ref": {"artifact": "...", "sha256": "..."},
  "known_by_initially": ["character:..."],
  "becomes_known_on": "event-rule-ref|null",
  "may_disclose_to": ["assessee", "character:..."],
  "disclosure_rule_ref": "rule-ref|null",
  "repeatability": "once|repeatable",
  "source_ref": {"sheet": "Данные", "row": 11}
}
```

Runtime запрещает персонажу использовать материал до `becomes_known_on`. Неизвестное
возвращается как неизвестное, а не заполняется LLM. Фактическое раскрытие создаёт
event с `material_id`, speaker/recipient, triggering Turn и timestamp.

## Минимальная модель правил и событий

Поддерживаются следующие типы rule, достаточные для пяти Case:

| Тип | Назначение |
| --- | --- |
| `state_predicate` | Текущая стадия, наличие/отсутствие события, число выполнений |
| `data_predicate` | Значение разрешённого поля AS или результат model check |
| `semantic_decision` | Один decision code из закрытого enum по конкретным Turn refs |
| `all` / `any` / `not` | Ограниченная композиция правил без произвольного кода |

Типы исполняемых событий:

- `character_response` — ответ конкретного персонажа в рамках его знаний;
- `material_disclosed` — раскрытие конкретного материала;
- `mandatory_update` — штатное обновление продолжающегося сценария;
- `conditional_branch_opened` / `conditional_branch_not_opened`;
- `model_check_requested` / `model_check_completed` / `model_check_indeterminate`;
- `scenario_completed`;
- `interaction_paused` и `interaction_terminated` как команды M7/PM-04, имеющие
  приоритет над очередным обязательным обновлением.

Rule содержит `rule_id`, type, inputs, allowed outcomes, effect refs, repeatability
и source refs. Для `semantic_decision` дополнительно: decision enum, prompt/schema
artifact refs, handler version и требуемые Turn refs. LLM не добавляет новый effect;
неизвестный outcome даёт `RULE_UNRESOLVED`.

`StepOrder` задаёт порядок стадий. Переход определяют rules, а не номер Turn.
Пауза сохраняет состояние и допускает продолжение. Окончательное прекращение
закрывает возможность будущего mandatory update; непроизошедшее событие остаётся
непроизошедшим и не дописывается в trace.

## Case №4: условное раскрытие Аси

### Неоднозначность источника

`D1` объединяет три разных материала и общее правило «раскрывать по запросу»:
черновик Нины, чек-лист Аси и историю Виктора. Но карточка Аси и S2 требуют более
узкого условия: ей дали безопасную возможность выразить конкретное несогласие и
содержательно рассмотрели вклад. Поэтому общий запрос о данных нельзя считать
разрешением показать весь D1.

Технически D1 должен быть разделён на три material records. Это предложение
структурирования, а не утверждённая правка содержания:

| Material | Initial knowledge | Предлагаемое условие раскрытия |
| --- | --- | --- |
| `D1.NINA_DRAFT` | Нина | Содержательный запрос о конкретном затруднении/полях |
| `D1.ASYA_CHECKLIST` | Ася | `asya_safe_invitation` AND `asya_contribution_considered` |
| `D1.VIKTOR_HISTORY` | Виктор | Запрос о порядке проверки, ответственности или причинах задержек |

Методологу требуется подтвердить формулировку для `D1.ASYA_CHECKLIST`:

> Ася раскрывает свою позицию и проверенный чек-лист, только если оцениваемый
> приглашает её описать конкретный опыт или ограничение без персонального обвинения
> и содержательно рассматривает сообщённый вклад. Общий запрос материалов,
> формальное подтверждение согласия или давление условие не выполняют.

### Положительный пример

Turn оцениваемого адресно приглашает Асю описать опыт без требования согласиться.
Semantic decision возвращает `SAFE_SPECIFIC_INVITATION`; следующий Turn показывает,
что её ограничение рассмотрено, decision `CONTRIBUTION_CONSIDERED`. Runtime создаёт
`conditional_branch_opened`, затем `material_disclosed(D1.ASYA_CHECKLIST)` и ответ
Аси. Trace хранит оба Turn refs и rule version.

### Отрицательный пример

Оцениваемый спрашивает: «Все согласны с решением?» или требует подтвердить позицию.
Decision — `FORMAL_OR_PRESSURING_INVITATION`. Ветка остаётся закрытой, чек-лист и
несогласие не предъявляются. S3 продолжается с Ниной, Виктором и Денисом; AS не
получает FAIL только из-за ненаступившей ветви.

## Case №3: воспроизводимый модельный тест

### Представление

`D1` преобразуется в шесть immutable input cards A–F. `D2` — versioned calculation
rule artifact. Предложенная оцениваемым схема сохраняется как `scheme_snapshot`:
route predicates, порядок действий и ответственный. Если route для карточки нельзя
однозначно получить, evaluator возвращает `INDETERMINATE_ROUTE` с missing rule,
не придумывая числа.

```text
ModelCheckRequest
  model_check_ref + checksum
  input_set_ref                         # A–F, позднее G отдельным событием
  scheme_snapshot
  initiated_by: assessee | character | system
  scheme_authored_by: assessee | source_prototype
  triggering_turn_refs[]

ModelCheckResult
  status: COMPLETED | INDETERMINATE
  per_input[]: route, start, finish, returns, unresolved_reason
  assumptions[]
  calculation_trace[]
  handler_version + checksum
```

Технический handler выполняет только детерминированные правила артефакта: проверка
полноты/категории 10 минут, полный каталог 20 минут, уникальная заявка 2 часа после
полного входа и 20 минут исполнения, окно 09:00–18:00 с переносом незавершённого.
Предметные числа не находятся в Python. Очередь и пропускная способность явно
`not_modelled`.

Исходный прототип может быть проверен по инициативе Сергея. В таком результате
`initiated_by=character:SERGEY`, `scheme_authored_by=source_prototype`; это не
приписывается оцениваемому. Предложенная участником схема получает его Turn refs.

После первого result или перед штатным закрытием событие вводит G. G не входит
задним числом в первый input set. Новый самостоятельный прогон после
`scenario_completed` запрещён; оценочное уточнение может только прояснить уже
сказанное.

## CaseVersion → AssessmentSituation

AS builder получает CaseVersion ref и ProfileSnapshot T08.5. Он:

1. Проверяет BaseRole и разрешённые profile fields.
2. Применяет только `allowed_slots`; числовые и логические ограничения меняются
   лишь при явном разрешении Case.
3. Материализует participant projection, персонажей, private knowledge, materials,
   stages, rules и model checks.
4. Сохраняет точную копию IndicatorID/M2 refs и конкретизированные conditions.
5. Проверяет по каждой цели роль/мандат, условие, материал, событие/ветвь и доступную
   форму самостоятельного действия.
6. Создаёт новый AS snapshot; изменение персонализации создаёт другой snapshot.

Case QA относится к CaseVersion+role. Ошибка одной персонализации даёт AS QA FAIL
этому snapshot и не отзывает Case QA. Если ошибка обнаруживает невозможность,
присущую всем разрешённым реализациям Case, создаётся дефект Case QA для решения
методолога.

Плановый сценарий находится в AS. Фактические Turns/events в него не записываются:
PM-04 создаёт отдельную append-only trace, ссылающуюся на `as_snapshot_id`.

## C-34 PM-03 → PM-04

Envelope передаётся непосредственно:

```json
{
  "contract": "C-34",
  "version": 2,
  "as_snapshot_ref": {"id": "...", "version": 1, "sha256": "..."},
  "case_ref": {"case_id": "...", "case_version": "...", "sha256": "..."},
  "profile_ref": {"id": "...", "version": "...", "sha256": "..."},
  "base_role": "...",
  "indicator_target_refs": [{"indicator_id": "...", "m2_ref": "..."}],
  "admission_ref": {"policy_ref": "...", "decision_id": "..."},
  "execution_payload_ref": {"artifact": "...", "sha256": "..."}
}
```

`execution_payload_ref` разрешается до первого предъявления и содержит:

- initial participant projection;
- characters/public positions/private knowledge and reaction constraints;
- materials and availability/disclosure rules;
- stages, rules, effects and model checks;
- target-specific Observability conditions;
- personalization substitutions/provenance;
- scenario completion и clarification boundary.

PM-04 проверяет checksums и admission scope. Битая/неразрешимая ссылка блокирует
старт с `SOURCE_UNRESOLVED`/`CHECKSUM_MISMATCH`. Отсутствующий применимый admission
даёт `AS_NOT_ADMITTED`. Storage/AI failure сохраняет собственный код и не становится
`AS_NOT_ADMITTED`, L0 или недостаточностью Evidence.

## Требования к будущей trace C-45

Для каждого факта исполнения нужны:

- event/Turn ID, sequence и timestamp;
- actor/speaker, recipients и origin (`assessee`, `character`, `system`);
- AS/stage/rule/material/model-check refs;
- triggering Turn/event refs и decision basis;
- предъявленный payload ref/hash, а не весь private context как Evidence;
- initiated_by и scheme_authored_by для model checks;
- pause/termination/scenario completion reason;
- произошедшие и не произошедшие условные ветви без синтетических Turns.

M6 получает план и фактическую trace раздельно. Только фактически доступный материал
может участвовать в анализе Evidence; private knowledge само по себе Evidence не даёт.

## Каталог M7 и ограничения набора

M7 получает для допущенных CaseVersion: BaseRole, exact targets/M2 refs,
Applicability, planned range, conditional opportunities, проверенный QA scope и
admission status. `IndicatorCount` — число проектных целей, не покрытие.

Для пяти WORKING Case зафиксированы ограничения:

- 31 уникальный Indicator из 61;
- K1.2 отсутствует;
- K3 представлен только `CASE-TDISC-03`;
- операционный сотрудник и студент присутствуют только в PROPOSAL;
- два Case менеджера проекта дают 55–75 минут до уточнений;
- время и достижимость условий эмпирически NOT_RUN.

M5 не расширяет цели и не сжимает Case под бюджет. Решение набора и покрытия — M7.

## Проверка технического проекта

Повторная проверка исходных ID не требуется при checksum
`06f528d9c9e34c4748979e4d787ce0e069990e9f4051953e395ecb3f454e53fa`.
Следующий offline verification должен доказать именно преобразование:

1. Пять Case собираются полностью; 10 PROPOSAL исключены.
2. Каждый импортированный элемент имеет source ref.
3. Дубли паспорта/листов совпадают; mutation вызывает `SOURCE_CONFLICT`.
4. Participant projection не содержит private cards, targets, QA или закрытые
   model results.
5. Case №4 проходит положительный и отрицательный branch examples.
6. Case №3 детерминирован на одинаковом input/scheme; недоопределённая схема даёт
   `INDETERMINATE`, а инициатор сохраняется.
7. Будущий факт не доступен до event; mandatory update не дописывается после
   termination.
8. AS personalization сохраняет цели/мандат/ресурсные и информационные условия.
9. Конец сценария запрещает новое самостоятельное действие под видом clarification.
10. Format PASS не изменяет WORKING/NOT_RUN и не создаёт IA/admission.

Фактические диалоговые прогоны остаются NOT_RUN до появления совместимого
исполнителя. План прогонов задаёт для каждого Case: содержательное продвижение,
преждевременное решение, отказ/эскалацию, отдельные pause/resume и termination.
Для №3 добавляются новая схема и неопределённый маршрут; для №4 — раскрытая и
нераскрытая ветвь Аси. Сочинённый transcript не считается выполнением.

## Адресные изменения реализации

| Место | Изменение | Зависимость | Приёмка |
| --- | --- | --- | --- |
| `assessment_definitions/.../schema-2` | Schemas/policies для CaseVersion, rules, AS и C-34 | Этот проект, M2/M3 refs | Offline examples №3/4 проходят schema |
| `scripts/build_m5_case_package.py` | XLSX adapter, source refs, duplicate comparison, data classification | Нормативный CT catalog для полного resolve | Детерминированная сборка 5 Case, 10 PROPOSAL исключены |
| `Api/assessment_case_contracts.py` | Технические модели schema v2 без предметных значений | JSON Schemas | Mutation/rejection tests |
| Новый bounded rule evaluator PM-04 | State/data/semantic rules и typed effects | Задание 5 runtime | Branch/update/termination tests |
| Новый deterministic model-check adapter | Исполнение versioned calculation rules | Case №3 rule artifact | Same input=same result; indeterminate без вымысла |
| AS builder около `Api/assessment_service.py` | Materialize AS и target-specific validation | T08.5 ProfileSnapshot | Exact targets; lost condition blocks AS |
| C-34 handoff | Envelope + immutable payload ref/checksums | Storage schema | Read-back exact snapshot |
| Prompt Lab | Изолированное исполнение WORKING candidates | Rule evaluator/AS builder | Видимые refs/events без user admission |

Новые физические таблицы не являются обязательным следствием слова «pool».
Сначала сопоставить модель с уже выбранным storage задания 4; расширять схему только
для отсутствующих immutable refs, materials/rules/evidence, с expand/rollback plan.

## Открытые адресные решения

1. Методолог: подтвердить точное условие раскрытия чек-листа/позиции Аси и разбиение
   D1 №4 на три материала.
2. Владелец источника: предоставить нормативный CT01–CT20 v1.0 для полного resolve.
3. Технический владелец задания 5: принять enum rules/effects и способ bounded
   semantic decision; не вводить универсальный graph engine.
4. Владелец артефакта: определить revision следующего XLSX и CaseVersion при
   содержательных исправлениях. Валидатор версии не назначает.
