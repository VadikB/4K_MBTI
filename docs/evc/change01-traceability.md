# Change 01: правило → контракт и данные → код → проверка

Код аудита: `d7b8313fdc7e076bd8fc3ae4827920d1e692ceef`, 01.10.2026.
Основания: [M1](../architecture/product-4k/m1/v1.4/README.md),
[Change 01](../architecture/product-4k/1.0/updates/2026-10-01/README.md),
[ADR-002](../adr/002-cycle-as-dialogue-contracts.md).

Состояния не взаимозаменяемы: источник подключён → спроектировано → реализовано →
проверено на точном commit. Для каждой строки текущий код — наблюдение, а критерий
T — план проверки. У всех новых T01–T12 результат **NOT_RUN**. Наличие старого теста
не доказывает новое требование. Документальный PR закрывает доступ к источнику и
проект контрактов, но не «учёт M1 в продукте».

| ID / правило | Контракт / данные | Фактический участок / состояние | Проверка готовности |
| --- | --- | --- | --- |
| T01 M1.4–5; И-2/3: фиксированный профиль | C-23/24/34, ProfileSnapshot и source refs | [assessment_service](../../Api/assessment_service.py), process_case_message читает active_profile_id; [context_builder](../../Api/assessment/interview/context_builder.py) использует профиль. Расхождение; новый путь спроектирован | После старта изменить активный профиль/роль: следующий Turn и новая AS того же Cycle используют исходный frozen profile; внешняя генерация не получает ФИО/контакты |
| T02 M1.5; И-3: точные цели Case | C-34, CaseVersion.indicator_targets → AS targets | [CaseDefinition/AssessmentSituation](../../Api/assessment_case_contracts.py): 21 поле, нет exact targets Case; проверки AS локальные. Расхождение | 1..N CT и Indicators; unknown ID/version, дубликат, неверная роль, добавление/потеря цели блокируют admission; fixtures двух ролей |
| T03 M1.5; И-3: сохранение полного состава | C-34, versioned mapping и атомарный freeze | [freeze_session_case_indicators](../../Api/assessment_service.py) проверяет count > 0; [старые тесты](../../tests/unit/test_assessment_indicator_snapshot.py) проверяют пустой scope/mapping, не exact equality. Частичная основа | Отсутствие одного mapping среди нескольких даёт TARGET_SET_MISMATCH и не сохраняет частично допущенную AS; rollback транзакции |
| T04 M1.5–6; И-3/6: неизменность условий | C-34/45, AS snapshot/checksum | [assessment_service](../../Api/assessment_service.py), _get_case_for_session_case и _get_case_methodical_context читают текущие таблицы; _get_personalized_case_context имеет сохранённый prompt и fallback. Расхождение | После начала изменить passport/text/limits: предъявленные условия и дальнейший Dialogue неизменны; битый checksum блокируется во всех читателях нового пути |
| T05 M1.6; И-2/4: конец сценария ≠ закрытие AS | C-45/54, scenario_completed, AS state, processing mode | [assessment_service](../../Api/assessment_service.py), turn.is_case_complete → _complete_case_and_continue → answered. Разделение не реализовано | Конец сценария оставляет AS открытой; interim не создаёт IA; final до закрытия отклоняется; после закрытия Turn отклоняется |
| T06 M1.6–8; И-4/6: материал и повторы | C-45, Turn IDs/order, materials/events, material_revision | [assessment_service](../../Api/assessment_service.py), session_case_messages сохраняет role/order; повтор по тексту в _insert_user_case_message_once не доказывает request-idempotency. Частичная основа | Доставка одного request дважды и crash после commit дают один Turn; одинаковый текст с разными request IDs сохраняет два хода; гонка Turn/close сериализуется |
| T07 M1.6–8; И-4: уточнение и отсутствие ответа | C-54 неопределённость → решение PM-04 → тот же Dialogue | [interview contracts](../../Api/assessment/interview/contracts.py) содержит is_case_complete; нового typed C-54 нет в рассмотренном пути. Спроектировано | Stale interim не применяется к новому материалу; уточнение не создаёт IA; отсутствие ответа — событие без синтетического user Turn; новое действие требует другой AS |
| T08 M1.7–8; И-4: IA по AS, пустой EB | C-45/54, EB, логический IA IndicatorID × AS | [IndicatorAssessmentOutput](../../Api/assessment_evaluator_contracts.py) требует evidence для observed; [repository](../../Api/assessment_indicator_repository.py) ключует результат по session+methodology+indicator. Расхождение нового контракта с shadow, не доказанный дефект официального результата | Пустой EB с реальным обоснованием допустим; L0/insufficient/no IA раздельны; две AS дают два IA; повтор final не новое наблюдение |
| T09 M1.1/8; И-6: версии AI и failure | C-45/54, trace и processing status | [runtime](../../Api/assessment_runtime.py) и [executor](../../Api/assessment_competency_executor.py) — точки интеграции; полнота проверки внешней конфигурации здесь не доказана | Подмена provider/model/prompt/schema обнаруживается; timeout/невалидный AI → технический failure, без L0/insufficient; replay сохраняет историю |
| T10 M1.9–10; И-2/5: Cycle и два времени | C-24/46, membership, frozen time budget/deadline | [runtime](../../Api/assessment_runtime.py) работает с user_sessions; полного соответствия Cycle/Session не доказано. Проектирование начато, реализация полного M7 отдельная | Принадлежность до ответов; новая Session не сбрасывает бюджет; штатное завершение закрывает Cycle при любом покрытии; поздний расчёт не возобновляет сбор |
| T11 M1.9–10; И-5: Results и покрытия | C-46/56, composition ref, calculation version | [legacy SkillEvaluationOutput](../../Api/assessment_evaluator_contracts.py) не равен новой модели. Новый стык спроектирован | Разный состав C-46/56 блокирует Results; пять покрытий; четыре исхода Skill; 0 ≠ null; пустой denominator ≠ 100%; закрытие без готового расчёта означает processing, не отсутствие результата |
| T12 M1.9; И-5/6: представление и права | C-67, Results/Report refs и разрешённое содержание | [report_growth_logic](../../Api/report_growth_logic.py), [pdf_report_service](../../Api/pdf_report_service.py) — legacy потребители, новый C-67 не внедрён | Report ссылается на точную расчётную версию; повтор/пересчёт не изменяет историю; нет Level из округления; права проверяются сервером; Recommendations вне первого пути |

## Как закрывать строку

Указать версию контракта/схемы и данных, commit, конкретные функции/миграции и
точные тесты с командой, результатом и CI-ссылкой. Обозначить legacy/новый путь,
непроверенное и приёмку человеком. Успешный unit не заменяет integration/HTTP для
сохранения, закрытия, очередей и прав. Технический PASS не означает пригодность
Case или Reliability. Эти доказательства ведутся отдельно в содержательной приёмке.

Статическая проба AS в предыдущем аудите: валидатор принимал неразрешённые refs,
произвольную роль и несогласованные Skill/Component/Indicator при qa_result=PASS.
Это свидетельство недостатка валидатора, не выполненный новый T02 и не доказательство
допуска такой AS в production. Данные сред и полные пользовательские диалоги не читались.

## Адресное дополнение на dd3d2ca от 02.10.2026

Исходная таблица выше — исторический аудит d7b8313, не состояние всего текущего main.
На dd3d2cadd90a31e3b7b3141ed6a0984afbd11ef6 `m5_cycle_runtime.py` и
`m5_storage.py` реализуют Cycle/Session refs, проверку membership и часть границ
сбора; `m5_scenario_runtime.py` — snapshots, Dialogue и технический C-45.
Это частичная новая основа T01/T04/T05/T06/T09/T10, не закрытие всех критериев.
Основной assessment_service не объявляется переключённым на новый путь.
Тесты `test_cycle_session_membership_freeze_and_collection_boundary` и
`test_as_rejects_foreign_session_and_changed_profile` существуют в
`tests/integration/test_m5_cycle_runtime_db.py`; в задаче 1 повторно NOT_RUN.
Заявленные ранее PASS в cycle-session.md остаются результатом того отчёта.
T07/T08/T11/T12 новым источником или наличием таблиц не закрываются.

M6 источник зарегистрирован; [контракт M6-A](../architecture/m6-a-contracts.md)
и [приёмка T-A1–A8](tasks/m6-a-implementation.md) спроектированы.
Реализация/проверка M6 пока NOT_RUN. F01/F02 и общий runtime остаются у прежнего
владельца; Evidence/EB получает одну реализацию M6-A, IA — её продолжение.

## Рабочая реализация M6-B

На ветке `codex/m6-task04-indicator-assessment`, поверх immutable commit M6-A
`01411ebc77b0b8b154f7a83c576a91b3c231ee41`, реализовано продолжение T07–T09:
interim без IA, final IA по AS × Indicator, отдельные IE/no-assessment/technical
failure, C-54 и защищённый QA readback. [Контракт](../architecture/m6-b-contracts.md),
[отчёт и проверки](tasks/m6-task04-implementation.md). Это техническое доказательство
draft QA; GC, provider smoke, semantic acceptance и пользовательский выпуск не выполнены.

## Рабочая реализация M7 Task 05

На ветке `codex/m7-task05-cycle-plan` реализован ограниченный QA-путь T10 и части
T05/T07: фиксированный план до старта, один профиль, два времени, исполняемый выбор
и назначение следующей AS с историей решений. [Контракт](../architecture/m7-cycle-planning-contract.md),
[отчёт](tasks/m7-task05-implementation.md). Полное управление Additional Session,
закрытием и C-46 остаётся задачей 7; M6 aggregation — задачей 8.

## Рабочая реализация M7 Task 06

M1.6, M6.6–6.9, M7.5–7 и Change 01 И-6 → semantic interim C-54 → неизменяемое
решение PM-04 → assessment/assessee Turns того же Dialogue → новая interim C-45 →
повторный M6. Реализация: `Api/m7_clarification*.py`, draft prompt
`m7_assessment_clarification/1.0.0`, superadmin routes и PostgreSQL integration.
Полный контракт: [M7 Assessment Clarification v1](../architecture/m7-clarification-contract.md).

## Рабочая реализация M7 Task 07

M1.6, M7.5.3–5.6/M7.7–8 и Change 01 И-4/И-5 → единый terminal transition →
final C-45/outbox → закрытый состав Cycle → versioned C-46. Реализация:
`Api/m7_completion*.py`, product-owned routes, expiry worker и PostgreSQL integration.
[Контракт](../architecture/m7-completion-contract.md) сохраняет Task 08/09 и
разрешённый PM-05 product consumer открытыми зависимостями.

## Рабочая реализация M6 Task 08

M6.7.1–7.4/M6.8.2–8.3, M7.7.5 и Change 01 И-4/И-5 → final IA точного состава
Cycle → явный допуск → Indicator/Component/Skill Scores → четыре исхода и пять
покрытий → immutable C-56 → composition-checked reconciliation C-46. Реализация:
`Api/m6_cycle_aggregation*.py`, draft package `m6_cycle_aggregation/1.0.0`,
superadmin QA endpoints и PostgreSQL integration. [Контракт](../architecture/product-4k/m6-cycle-aggregation-contract.md),
[отчёт](tasks/m6-task08-implementation.md). Task 09, утверждённые GC/Reliability и
product UI остаются открытыми зависимостями.

## Рабочая реализация M6-A

На ветке codex/m6-task01-contracts после базы dd3d2ca реализована часть PM-05:
C-45 → Fragment/BS/Evidence/EB → immutable revisions и QA read-back.
[Отчёт и команды](tasks/m6-a-implementation.md). Это частичное доказательство
T08/T09, не закрытие требований итогового IA, C-54 и C-56. Provider/GC NOT_RUN.
