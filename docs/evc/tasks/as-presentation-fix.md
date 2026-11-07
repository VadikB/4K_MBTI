# AS-PRESENTATION-DIAG-01 — публичная проекция конкретной AS

## Результат и допуск

Владелец ответил «делаем» на предложение узкой бесплатной правки представления AS
с регрессиями. Исправляется дефект, найденный визуальным review AC18 на
e9639edef400e2c36425f0d1c3ca98b646fdb0c2 /2.0.70. Сам runner получил PASS,
admission PASS/10 operations/748766 tokens, start201/0 assessment answers;
это не безусловная визуальная приёмка AC18. Исторический PREP-DIAG-01 — UNKNOWN.

Base/fresh origin-main e9639ed; отдельные branch `codex/as-presentation-fix` и
worktree `worktrees/as-presentation-fix`. Root TG identity branch/коммиты и3 чужих
untracked документа сохранены. Merge/bump/PR/push/deploy/publication/LLM=false.

## Источники и границы

Прочитаны AGENTS, README, CONTRIBUTING, EVC workflow/matrix/recipe/task-template,
architecture context/Registry/Change01 И-1/3/6/7 и task SourceSet manifest,
M1v1.4 §M1.5 (FROZEN/CURRENT=NO), ADR002 C-34, m5-case-execution SLS02,
профиль assessment-first-case/1.1 и предыдущий AC18 REPORT/diagnostic.
Код: build_m5_sales_package._participant_presentation, m5_case_runtime,
m5_functional_generation_service.build_persistence_trace, m5_storage,
interview renderer и tests unit/HTTP/SQL/browser. Старые неизменные нормы
переиспользованы; опубликованные версии не редактируются.

Конкретный содержательный источник: functional-personalization/0.5,
Generation_contract_v0.2 этапы3/4/7 и G06/G09/G11; Generator_instruction_v0.2 п.5;
05_participant/Participant_SPEC_02_v0.2.txt и прочие8, author AS P00/start materials.
Эти participant outputs содержат конкретные P00 и материалы, **не** общий
авторский паспорт. Старый SLS02 Sales projection и functional projection различны.
Это не новый допуск источника, human review или изменение содержания AS.

Ожидание → факт → причина: участнику нужны конкретные условия допущенной AS →
видны Python list/dict и «определяются в AS» → compiler перенёс общий passport8–13
в legacy participant_presentation, материализатор отдал их вместе с P00/материалами.
Одной замены str на prettier text недостаточно: авторская конструкция всё ещё
утекала бы в participant view. Не удалять ограничения из самой AS ради вида.

Выбранная совместимая реализация: при создании **новой функциональной AS** выбирать
публичные P00/title/start materials из уже скомпилированной конкретной AS. Режим
определяет existing frozen `functional_personalization.source_snapshot.refs.package.
compiler.source_schema_profile`, не latest config/профессия/строковая эвристика.
Новый runtime/формат/параметр публичного API не вводится. Legacy без этого точного
источника сохраняет прежнюю проекцию. Полные паспорт, accepted AS, private facts,
Indicator layers и provenance остаются в закрытом snapshot/trace. Все прежние
проверки источников/admission/repair и контракт CaseVersionV3 остаются прежними.
Чтение сохранённых AS не пересобирает participant payload: миграции нет.

Адрес: PM03/LU03.3–03.4 → C-34 → PM04 materialization/participant UI.
Предметные определения/пороги/prompts не меняются; новый artifact debt не вводится.

## Стоп-условия

Все8 — нет: методология/основание допуска/кардинальности не меняются; публичные
routes/response models и БД прежние; удаления сохранённых данных нет; применимый
public source есть; нового формата/контура нет; права/секреты не расширяются;
откат — revert task commit только для будущих AS; область совпадает с допуском.
Если обнаружится требование нового содержательного поля AS, не выдумывать его.

## План и проверки

1. Red-regressions exact public/closed boundary на9 Cases и legacy compatibility.
2. Узкая materialization-правка; source hashes/Case contract/admission неизменны.
3. Unit/backend/HTTP, actual isolated PostgreSQL persisted readback и viewport
  1440/320/390/768 на существующем entry/dist. Только controlled source fixtures,
  не real LLM/full PATH или новая методологическая приёмка. Без fake Connection в
  SQL/HTTP persistence proof. Явно отделить synthetic provider/источники от БД.
4. Собственный review, evidence, точный рабочий commit/SHA и передача.

Дополнительный подтверждённый presentation defect: каждый poll1200ms пересоздавал
даже неизменный DOM AS и запускал автопрокрутку. Простое ожидание после trial не
устранило stable offscreen: это продуктовый rerender, не основание ослабить collector.
Узкая правка UI сохраняет DOM при тех же AS/payload/trace/clarification; identity
первого узла защищает от legacy/return replacement. Время/статус/доступность кнопок
обновляются по-прежнему; новое содержание пересоздаётся. Collector/CSS не менялись.

Проверка: исходные9 FAIL/2 PASS → адресные58 PASS; итоговый backend937 PASS,
HTTP108 PASS, actual PG/HTTP6 PASS (5 readback до cleanup,1 close-during-provider),
frontend145 PASS, lint/build PASS. Browser12 PASS на4 ширинах; расширенный120 PASS
(retry0/skip0), включая доступность последнего материала после2 polls. Первый119
PASS/1 FAIL AC05 (UNKNOWN, не новый установленный дефект) сохранён; в повторе не
воспроизведён.
Test-only followup: actual-viewport вместо fullPage для кадра конца inner scroller,
2 browser PASS, post-capture geometry PASS. Product bytes и прочие tests unchanged
от рабочего36ef230a; их результаты переиспользуются. Точный handoff SHA в пакете.
Один дополнительный unit ошибочно предполагал разрешённый organization slot в
functional fixture: отказ правильный, тест исправлен на запрет undeclared slot.

Owned container/schema удалены после export, permanent DB untouched.22 исходных
файла/контракта unchanged от base,9 Case refs сохранены в source-identity.json.
Текущий шаг: локальная реализация/проверка завершены; рабочий commit и передача
не запускают выпуск. [Отчёт](../reports/as-presentation-fix.md)
и [evidence](../evidence/as-presentation-fix/README.md) разделяют scopes и историю.
AC18 на окончательном новом released SHA остаётся NOT_RUN до отдельного допуска.
Правка не переписывает старый PASS/визуальный BLOCKED и не разрешает выпуск.
