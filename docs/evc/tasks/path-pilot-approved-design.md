# PATH-PILOT-01 — принятие проекта v0.1 и техническая передача

Дата: 05.11.2026. Статус: PRODUCT_AND_METHODOLOGY_ACCEPTED / T1_PROPOSED.
Это запись решений и проект технического продолжения, **не runtime admission**.

## Результат, источник и решения

Владелец в текущем чате ответил «все подтверждаю» на раздельный вопрос о продуктовых
P1–P3 и методологических M1–M4, включая вопрос, принимает ли он методологическую
часть сам. Обе части приняты пользователем — владельцем задачи. Повторно спрашивать
то же согласование не требуется. Подтверждение не распространяется на T1/R1,
реализацию нового контракта или ранее запрещённые действия выпуска/прогона.

Принятый объект — [проект v0.1](../reports/path-pilot-admission-proposal.md) в commit
`8c900f9727bae75c5dd78aedc4201a2dbd0bffbe`, payload checksum
`883c025cfa0ea43ad17922bc4818f05a0aaaa62bf02817690a3d07f171cfec06`.
Побайтовые refs и раздельные решения — [первичная запись](../evidence/path-pilot-owner-decision-2026-11-05.json).
При изменении целей, условий или маршрута потребуется новая редакция и оценка влияния;
это принятие не распространяется на произвольный LIMITED.

Исходные draft JSON, матрица и отчёт в переданном пакете остаются побайтово прежними.
Их PENDING — исторический статус на момент передачи, не текущее отсутствие решения.
Новая запись не делает review JSON исполняемым артефактом и не заменяет AS admission.

Принято: полный M2=61; плановые39 и22 вне покрытия; 55 исходных условий/рисков;
маршрут02→03→04→07→05→01→06→08, SPEC.09 без автоматической подстановки.
7200 секунд учитываемого времени /259200 календарного окна без обещания пройти весь
маршрут. Плановая возможность не равна фактической, Evidence или IA; условную ветвь
нельзя форсировать ради покрытия. Ограниченное обещание/четыре исхода M6–M8 из проекта
приняты без новых формул, порогов, Reliability или уменьшения полного M2.

Program `specialist_pilot@1.1`, configuration11, catalog `specialist-pilot@1.0` и все
Case/M2/source checksums — ровно §2 и payload проекта. Это baseline источников,
не разрешение менять published1.1. IDs новой организации/назначения/профиля/акторов
ещё не созданы; их проверка остаётся условием отдельно разрешённой настройки.

## Прочитано и применимость

В этой фиксации прочитаны README.md, CONTRIBUTING.md, AGENTS.md, EVC workflow,
verification-matrix, artifact-recipe, task-template/review-checklist; архитектурные
context/Registry, M1 v1.4 README, Change01 README и task manifest. Адресно сверены
ADR-002 C-24/C-34/C-46 и совместимость, assessment-runtime lifecycle/snapshots,
m7-cycle-planning-contract v1 и §6/7 проекта v0.1. Повторно использованы неизменённые
выбранные разделы M1/M6/M7/M8 и source/QA evidence из принятого пакета8c900f9.
M1 FROZEN/CURRENT=NO; CURRENT, методология и published definitions не меняются.

Текущий код сверён в Api/m7_cycle_planner.py, Api/m10_product_flow.py,
web/js/onboarding-flow.js и tests/browser/fixtures/preparation-receipt.mjs.
Планировщик различает READY/LIMITED/NO_ROUTE по полному набору; runner требует READY,
UI считает готовностью непустой маршрут с временем. Это основание технической
работы, не доказательство отказа start в историческом run: явный start там NOT_RUN.

## T1 — предлагаемое техническое решение до реализации

Владелец архитектурного решения — человек, назначенный владельцем задачи;
агент подготовил вариант, но не назначает себя принимающей стороной.

1. Использовать существующие PM-04 plan/revisions, PM-03 AS admission и lifecycle
   определений, а не отдельный runtime ради пилота. Смысл/состав плана хранить вне
   исходного кода. Для versioned pilot admission/binding пока нет подтверждённого
   подходящего runtime-формата: сначала утвердить расширение, validation, loader,
   publication, snapshot и совместимость. Этот sidecar — только evidence, не формат
   runtime-контракта. Не добавлять ad-hoc ref в published source_refs_json.
2. Binding должен однозначно адресовать plan/version/checksum и обе человеческие
   записи принятия; точные program/config/catalog/Case/M2/role/profile/assignment
   refs, timing revision и scope. Разделить нормативный61, утверждённый плановый39,
   22 вне плана и реальные пробелы внутри плана. Существующие поля сохраняют смысл;
   wire shape/contract version и необходимость expand-миграции требуют T1 review.
3. Сервер PM-04 выдаёт единый authoritative start readiness и безопасные причины.
   Его читают participant UI, admin projection и runner; при start POST тот же
   доменный контроль повторяется в транзакции. Клиентский флаг не источник права.
   LIMITED допускается только при exact approved binding и остальных выполненных
   условиях; неизвестный LIMITED, NO_ROUTE и несовпадение refs не разрешаются.
4. Сохранить tenant/owner/active assignment/frozen profile/operation→Cycle→Session→AS
   и plan revision; весь target set Case, обязательные generation/tester/challenger,
   конечный кандидат→compiled Case→saved AS→предъявленная AS. PASS/PASS_WITH_WARNINGS
   только вместе с admitted_for_participant=true; FAIL/INCOMPLETE/false блокируют.
   Prompts, repair, лимиты и продуктовый admission этим проектом не меняются.
5. Scoped timing7200/259200 должен разрешаться из версии настройки и читаться с
   сервера до первого start. method_default3600 и7200 другой организации не подходят.
   Подготовка не запускает время; explicit start запускает его штатно. Старые
   prepared/active Cycles и snapshots не переписываются. Для legacy сохраняется
   прежний snapshot reader; отсутствие нового допуска не даёт новый LIMITED bypass.
6. Внедрение — отдельный независимо принимаемый результат: draft контракта и карта
   потребителей/данных → человеческое T1 → разрешённая реализация и бесплатные
   регрессии → отдельное R1 на выпуск/публикацию и затем на оплачиваемый PATH.
   Если нужна миграция, до кода записи согласуются expand/совместимость/восстановление.

Это уточнение §6 принятого проекта, а не внедрённое поведение. Финальные имена полей,
HTTP schema и migration SQL здесь намеренно не выдаются за утверждённый контракт.

## Проверки следующей реализации и критерии

- Позитивы: exact approved LIMITED; READY со всеми обычными условиями;
  PASS_WITH_WARNINGS с admitted=true. На success — explicit start, server readback,
  первая именно сохранённая/допущенная AS, ответов0.
- Негативы: нет одной из P/M записей; другой plan checksum/version/scope; unknown
  LIMITED/NO_ROUTE; пробел внутри39; stale/revoked assignment, другой tenant/profile,
  operation/Session/AS/revision mismatch; нет обязательной стадии/финального допуска;
  FAIL/INCOMPLETE/unadmitted; неправильное время/источник или исчерпание времени.
- Гонки/повтор: две вкладки, устаревший readback, повтор start и rollback ошибки;
  старый snapshot не перенастраивается и не получает новый допуск задним числом.
- Server/UI/admin/runner согласованы по одному решению; причины/check IDs/lineage
  сохраняются до owned cleanup. Отказ не становится PASS из-за наличия receipt.
- EVC: backend + HTTP; integration на новой isolated test/pytest DB при изменении
  данных; frontend lint/tests/build при UI; обязательный CI точного кандидата до merge.
  Содержательные проверки — с явными synthetic fixtures, не новым human review.

## Границы, стоп-условия и выпуск

P/M по exact v0.1 закрыты. Стопы2/5 остаются для нового публичного/данного контракта
и формата до T1; стоп8 — для реализации/выпуска вне разрешённой design-only области.
Миграции/постоянная БД не разрешены. Работа здесь docs/evidence-only, безопасный откат —
отмена только новых документационных изменений, не переписывание принятого пакета.
Остальные риски конфиг/схема/deploy/безопасность в этой фиксации не реализуются.

`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`, `version_bump=false`,
`artifact_publish=false`, `paid_llm_run=false`, `permanent_database_write=false`.
PREP-DIAG-01 отдельно: root_cause=UNKNOWN. Новый coverage gate не объявляется его причиной.

## Проверка и передача

Для этого шага применима docs-строка матрицы: diff, ссылки, checksum и содержательное
review. Проверяются неизменность трёх reviewed files, точный checksum payload,
раздельные P/M решения, отсутствие R1 и runtime-изменений. Первоначальный verifier
проверяет frozen draft и исторические runs; его поле pilot_approval=PENDING относится
к draft внутри8c900f9, не читает отдельную последующую запись принятия.
Новый manifest фиксирует состояние передачи с отдельным sidecar; старый ZIP/checksum
и manifest90ed3f47… остаются доступны в commit8c900f9 и не переписываются.

Backend773/HTTP108/SQL43/Python48/Node38 — прежние результаты unchanged1bc9d36,
не новые запуски и не проверка будущего gate. Для docs нет оснований повторять DB/LLM.
Новый CI NOT_RUN; main и origin/main по локальным refs2dc98c6/2.0.64; remote сейчас
не опрашивался. Test — последний readback2dc98c6/2.0.64, не новая проверка deployment.

Фактические проверки этого шага: `git diff --check` PASS; stdlib JSON/hash audit
трёх reviewed files и canonical payload PASS; все P1–P3/M1–M4 присутствуют, все
release/run flags false. Offline source/matrix replay и10 negative mutations
переиспользуют неизменённый draft; перед коммитом повторяются вместе с manifest audit.
Локальные Markdown-ссылки новой карточки и отсутствие Api/web/tests изменений
проверяются отдельно. Никаких новых DB/LLM операций эти команды не выполняют.

Рабочая ветка codex/path-plan-diagnostics от reviewed8c900f9. Точный SHA новой записи
фиксируется коммитом передачи; runtime code и тестовый инструмент неизменны.
Следующий минимальный шаг: техническому владельцу принять/скорректировать T1 и отдельно
разрешить реализацию. Нового P/M вопроса по неизменённому v0.1 нет. Финальный PATH —
только после технической готовности и отдельного разрешения прогона.
