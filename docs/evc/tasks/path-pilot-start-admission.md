# PATH-PILOT-02 — реализация принятого T1

05.11.2026. Основание: после P1–P3/M1–M4 владелец ответил «принимаем идем дальше»
на передачу T1 и запрос разрешения реализации. T1 принят, локальная реализация и
бесплатные проверки разрешены. Публикации, постоянная БД, новый paid PATH,
push/PR/merge/deploy/version bump по-прежнему не разрешены.

Ветка codex/path-pilot-start-admission; неизменяемая база
2a9ef94f6d306a036dc123930b4d2dbefa7d1507. Исходная диагностическая ветка сохранена.
Предметное согласование: PATH-PILOT-01 v0.1 / payload
883c025cfa0ea43ad17922bc4818f05a0aaaa62bf02817690a3d07f171cfec06 и отдельная P/M запись.
PREP-DIAG-01 остаётся отдельно UNKNOWN.

## R1 — выпуск приложения2.0.65 разрешён

05.11.2026 владелец явно ответил «Да, 2.0.65: PR/CI → review → main/test»
на вопрос о PATCH-выпуске с отдельной границей: публикация/активация программы
и новый paid PATH не входят. Текущие разрешения: branch_push=true, pr=true,
version_bump=true (только2.0.65 PATCH), merge=true/deploy=true **после** успешных
обязательных CI актуального head/base и человеческого review. artifact_publish=false,
program_activation=false, paid_llm_run=false. Прежние false ниже — история до R1.

План R1: штатный `npm run ready:prepare -- --candidate 2.0.65` со fresh main →
локальные применимые release-проверки и snapshot/recovery review → commit/push/PR →
frontend/pytest/full-verification → человеческое review → squash merge/test deploy →
readback версии/SHA/assets. Нет прямого push main или ручной загрузки runtime файлов.
Источник runtime38dd551/tested199e7c3 и schema preflightd8ae403 сохранены; payload,
prompts/admission/repair и published1.1 не меняются. При изменении head/base CI
повторяется. Слепой downgrade после будущих v2 Cycles не допускается; в этом выпуске
новая программа не публикуется/не активируется, source receipt остаётся1.1.
Human review нового PR пока NOT_DONE, CI NOT_RUN. Эти условия не заменяются
самоотчётом агента. Полный ранее проверенный runtime не переделывается ради выпуска.

R1 preflight PASS: fresh origin/main2dc98c6, подготовлен ровно2.0.65; совпадают
pyproject/uv.lock/config/index и пересобранный web/dist. Адресные Python111 PASS
(release/config + snapshot/start/collector/summary), frontend140 PASS, Node47 PASS,
lint/diff-check PASS. Api/scripts/tests/assessment_definitions/database не менялись
после d8ae403; backend835/HTTP108/integration217/browser98 на199e7c3 применимы к
предметной логике. Release/front-end версия дополнительно проверена; обязательный
CI нового commit всё равно выполняется полностью. Paid LLM0, БД не используются.

R1 PR создан: [#170](https://github.com/VadikB/4K_MBTI/pull/170), первый headb75d155,
base2dc98c6. Quick frontend/pytest и full integration PASS; browser fast/runtime
FAIL на старых неподтверждённых LIMITED component-входах. Воспроизведено локально.
Ни merge, ни deploy не выполнялись. Harness-only исправление: явная узкая
synthetic upstream plan-policy граница для прежних downstream component-сценариев
и отдельный настоящий assessment UI/HTTP negative gate без подстановки.
Никакого допуска новой программы, нового runtime fallback или изменения admission.
[Первичные CI refs и границы](../evidence/path-pilot-release-2065/README.md).
После нового head обязательный полный CI повторяется; человеческое review ожидается.
Локальный итог исправления harness: backend862 PASS, HTTP108 PASS применим,
guards/seed-order/stages57 PASS; legacy PATH29 component1 PASS; runtime13PASS/2FAIL
сохранён, после исправления порядка коротких time inputs C1/C2 отдельно2PASS.
Цельный локальный runtime15PASS не заявляется; финальный commit получает полный CI.
Лимиты задаются до подготовки AS через существующий create_plan, AS revision/time
проверки не ослаблены. Owned-БД и только task-owned контейнер удалены после evidence.

## После передачи38dd551 — читающая сверка рабочей схемы

После объяснения границ владелец ответил «ок спасибо идем дальше»: выполняется
ранее разрешённая финальная сверка схемы серверного Agent4K-Test/.env с кодом38dd551.
Только metadata public-таблиц затронутого пути: columns/types/defaults, constraints,
indexes/triggers и hashes их функций. Ответы/аккаунты/программы/ключи не выгружаются.
Прямое psycopg подключение с default_transaction_read_only=on, без импорта приложения,
bootstrap/ensure на сервере. Ошибки обезличены. Публикация/активация/LLM/merge/deploy
не разрешены. Для независимого эталона применяется существующий empty bootstrap
на новой собственной локальной pytest-БД без seed/аккаунтов/LLM, не старая удалённая
test-БД и не копия рабочих данных. После сохранения metadata эталон штатно удаляется.
Первичный пакет38dd551 не переписывается; результат передаётся отдельным sidecar.

Сверка завершена05.11: EXACT_SCOPED_SCHEMA_MATCH,32 таблицы/353 колонки/
191 constraint/84 index/16 trigger, дельты0. Metadata checksum одинаковый:
c18922b95d6223262d23cc6edf1c060ac66b9f84243feee076d32baae586a065.
Читающая регрессия:1 позитив/11 negative schema mutations/4 invalid records PASS.
Рабочих данных не читали/не меняли, транзакция READ ONLY/rollback; эталонная
owned-БД/контейнер удалены после сохранения metadata. Remote main и server checkout
свежим чтением2dc98c6. [Первичные доказательства](../evidence/path-pilot-schema-readback/README.md).
Для этого изменения миграция схемы не нужна; R1/CI/публикация остаются отдельно.

Уточнение владельца о БД: целевой контур — серверный
`/home/vadim_bogachev/projects/Agent4K-Test/.env`; разрешена только проверка
соответствия схемы, без активации программы. По последнему указанию эта проверка
перенесена на конец задания после стабилизации всех изменений, перед возможным
слиянием в main. Сейчас рабочая БД не используется; публикация/merge/deploy этим
уточнением не разрешены. Изолированные автотесты продолжаются отдельно.

## Источники и конкретизация контракта

Повторно используются прочитанные на2a9ef94 README/CONTRIBUTING/AGENTS, EVC
workflow/matrix/recipe, context/Registry, M1/Change01/SourceSet и ADR-002.
Прочитаны текущие m7_cycle_planner/planning_repository/planning_package,
assessment_programs, participant_profile, assessment_assignment_sources,
acquaintance.preparation_scope/prepared_plan, m10_product_flow,
cycle_execution_manifest, publish_assessment_program, parameter_resolution,
UI preparationView, admin stage и harness receipt/tests.

Конкретизация принятого T1: без новой таблицы/миграции, additive JSON-контракт
`m7_pilot_plan_admission/1` в source_refs_json **новой** draft ProgramDefinition.
Он сохраняет полный принятый proposal envelope и раздельную запись P/M с hashes,
не переименовывая исторический PENDING. File manifest — draft источник сборки;
сборка не публикует и не активирует программу. Runtime читает только immutable
snapshot опубликованной ProgramDefinition, закреплённый в новом plan revision.
Никакого fallback на файл/latest/current либо изменение published1.1.

При новой записи проверяются exact baseline program/config/catalog/Case/M2/role,
полный61/плановый39/22 вне, route и условия исходного принятого payload.
Новая версия программы допускает только техническое добавление снимка, не замену
исходных источников. Версии/hashes разных объектов не приравниваются.
Существующий плановый JSON расширяется, старые immutable revisions не меняются.
Неизвестный LIMITED не получает право старта, равно как READY без остальных условий.

## План и критерии

1. Версионный draft источник, validator/loader/snapshot и регрессии.
2. Привязка при создании нового плана; отдельные полнота/плановые пробелы; общий
   server start readiness с exact lineage/AS/time, повтор в start transaction.
3. Participant/admin/UI/runner читают одно решение; evidence сохраняет refs/отказы.
4. Адресные unit/Node, backend/HTTP, применимые isolated integration, frontend
   lint/tests/build; self-review, локальный коммит и передача с точным SHA.

Шаги1–3 реализованы локально. Контракт и совместимость:
[pilot-plan-start-admission-contract](../../architecture/pilot-plan-start-admission-contract.md).
Шаг4 завершён локально: tested implementation199e7c351a2d985c0173f845574c4de5dc80775a,
backend835/HTTP108/integration217/browser98 PASS, frontend140/receipt46/persistence1
и lint/build/dist PASS. Evidence сохранено, owned контейнер штатно удалён, рабочая
БД не затронута. [Итоговый отчёт](../reports/path-pilot-start-admission.md).
Все новые предметные значения только в артефакте, не Python/JS.
AS generation/tester/challenger, PASS_WITH_WARNINGS+admitted, repair и prompts
сохраняют существующие правила. Синтетические fixtures — не human review/реальный PATH.

## Безопасность, выпуск, откат

Новых колонок/миграций не планируется. Integration — только собственная test/pytest
БД, провайдер отключён. Нельзя запускать configure/import/publish на постоянной БД,
даже с dry-run, если команда подключается/ensure_schema. Имена/секреты/ответы не входят
в evidence. Исторический ZIP и примеры отрицательных runs не переклассифицируются.
Все release flags=false; paid_llm_run/permanent_database_write=false.
Откат к base прекращает создание новых binding snapshots, не удаляет данные;
до будущей публикации отдельно проверяются readback и завершение созданных snapshots.
Старые форматы сохраняют readers; новый LIMITED opt-in не применяется задним числом.
При обнаружении необходимой несовместимой схемы/потерь — остановить зависимую работу
и представить точный migration/restore plan, не обходить гейт.

Новый CI NOT_RUN. Local main/origin-main2dc98c6/2.0.64, deployment по последнему
readback тот же; это не новое наблюдение remote. Следующий release/run R1 отдельно.

Промежуточные факты: pure snapshot/start/stage mutations PASS; backend828 и HTTP108
PASS на промежуточном рабочем diff; frontend140/lint/build PASS. Owned PostgreSQL16
контейнер33e6f86… / database product4k_pytest_pilot_t1_8ac4c319: прежние адресные SQL62
PASS; новые SQL/HTTP6 PASS (реальный gate, READ ONLY readback, same AS/0 answers,
revocation и две concurrent first-start). Полный итог повторяется после стабилизации
кода; эти числа не подменяют final exact-SHA проверку. LLM0, постоянная БД не читалась.
Старые S10 component fixtures явно подставляют upstream start permission; новая
SQL suite восстанавливает реальный predicate и отдельно проверяет legacy bypass denial.

Ревью679cc2f: полный integration215PASS/1FAIL — старый10.5/M4 fixture ожидает
start неподтверждённого LIMITED. Теперь отдельно проверяет реальный409, а только
два старта для M4/history получают явную SYNTHETIC upstream подстановку, не admission.
Независимая SQL-регрессия воспроизвела lock timeout на DROP TRIGGER при подключении
следующей программы с открытым readiness transaction. В normal connect устранён
schema bootstrap, сохранён existing lifecycle; порядок connection→timing согласован
с start. Старые callers save_revision по умолчанию не изменены. Новый кандидат
повторно проходит полный применимый набор; первичный FAIL сохраняется в evidence.
