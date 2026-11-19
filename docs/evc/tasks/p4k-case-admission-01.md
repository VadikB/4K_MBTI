# P4K_CASE_ADMISSION_01 — локальный кандидат

## Результат и область

Основание: прямое поручение пользователя «запусти задание на исправление»,
19.11.2026, с постановкой `P4K_CASE_ADMISSION_01_v1.2.md`.
Вложение задаёт требования AC-1–AC-5; самостоятельным разрешением внешних
действий не считается. Разрешён локальный цикл исправления и синтетические проверки.
PM-03/LU-03.2–03.3, C-34 и чтение PM-04: различить дефект AS и невалидную проверку,
сохранить независимые свидетельства, безопасный отказ и уже выполненную работу Cycle.
База после успешного fetch: `fd6d4e0c24981246a939199de42672322d1999b5`, 2.1.34.
Ветка `codex/p4k-case-admission-01`, отдельный worktree `/private/tmp/p4k-case-admission-01`.

## Источники и решения

Прочитаны на базе: AGENTS.md, README.md, CONTRIBUTING.md; docs/evc/agent-workflow.md,
verification-matrix.md, artifact-recipe.md, task-template.md, decision-register.md;
docs/architecture/product-4k/registry.md, 1.0/context.md,
1.0/updates/2026-10-01/README.md и source.md (C-23/24/34);
docs/adr/002-cycle-as-dialogue-contracts.md;
docs/methodology/source-sets/2026-10-01/manifest.json;
originals/M4.Context-v1.0.docx (объединение, приоритеты, передача),
originals/M5.Methodology-v1.1.docx (§§4.2, 6.2–6.3), derived/M7-v1.3.md (§§4.5, 5.3);
docs/evc/protocols/m5-functional-personalization-tester-v2.json;
assessment_definitions/prompts/m5_functional_protocol/v2 и существующий repair/v1.
Источники прочитаны как требования; CURRENT, human admission и методологический PASS не присваиваются.
Применены SYN-CONTOUR-OWNERSHIP (профиль assessment-first-case/1.1), PILOT-120/ARCH-A05
(первоисточник tasks/arch-a05-coverage-pilot.md), PATH-PILOT-01 (exact owner evidence,
не общий допуск LIMITED). Новое решение о маршруте, бюджете или миграции не вводится.
Существующие контракты и потребители: Api/m5_functional_generation_service.py,
m5_functional_tester.py, product_cycle_preparation_queue.py, m10_product_flow.py,
m7_cycle_planner.py, m5_cycle_runtime.py; их unit/SQL/HTTP регрессии.
Пробел: локальный derived M5 отсутствует; прочитан зарегистрированный оригинал DOCX.
Блокирующих предметных противоречий не выявлено.

## План и полномочия

1. Воспроизвести AC-1/2/5 через существующие Gateway/profile, зафиксировать RED.
2. Исправить валидацию и агрегацию, сохранение свидетельств и технический повтор
   в существующем лимите; повторить адресные тесты.
3. Пройти штатные API на собственной PostgreSQL test-БД: два чтения отказа,
   неизменность закрытой AS/ответов/плана/бюджета, идемпотентность и права.
4. Выполнить backend, HTTP и применимый integration; локальный preflight,
   STATE, commit и отчёт с точными base/candidate/tested SHA.

Все флаги: branch_push=false, pr=false, merge=false, deploy=false,
version_bump=false, artifact_publish=false. Публикация и продуктовый выпуск —
отдельное поручение. Локальный ready:prepare без номера проверяет границу выпуска;
отсутствие допуска bump не обходится. Данные только синтетические, LLM и письма отключены.
Изменение управляющих документов, пакетов, публичной схемы и миграция не нужны.
Стоп-условия рабочего цикла: предметная норма/маршрут/совместимость/данные/новый
контур/секреты/внешний эффект/необратимость — не возникают внутри указанной области.

## Проверка и откат

Матрица: backend-логика + LLM transport + очередь/HTTP + поведение БД.
Команды: npm run test:backend; npm run test:backend:http;
TEST_DATABASE_URL=<owned localhost pytest DB> npm run test:backend:integration;
адресные AC-тесты, git diff --check, npm run ready:prepare без bump.
Откат: git revert локального продуктового коммита; snapshots и опубликованные
артефакты не меняются. Собственная БД удаляется только после сохранения evidence.

## Состояние

Локальная реализация и приёмка завершены. Первичный локальный этап сохранён ниже;
актуальные полномочия публикации и состояние выпуска — в дополнении от 19.11.2026.

## Реализация и фактическая приёмка

| Критерий / источник → контракт | Исправление → проверка |
| --- | --- |
| AC-1; M5 §§6.2–6.3 → C-34 | Находка проверяется на согласованность статуса, класс, основание, локализацию и requirement_ref. Ошибка протокола не считается дефектом AS. 8 отдельных мутаций Tester/Challenger; generation=1, repair=0. Валидный полный ответ проходит существующий положительный контроль. |
| AC-2; Change 01 И-3 → LU-03.2/03.3 | Сохраняются обе независимые проверки с reviewer и checksum; агрегация не перезаписывает блок пропуском Challenger. Один repair и полная перепроверка изменённой редакции: generation=2, repair=1, новый checksum и PASS. |
| AC-3; технический JSON-протокол → queue operation | Существующий лимит: исходный вызов + один JSON-повтор в том же бюджете и на том же кандидате. Exhaustion: PROVIDER_JSON_INVALID_RETRY_EXHAUSTED, INCOMPLETE. Верификационная ошибка сама не разрешает новую генерацию. Generation=1, repair=0, review attempts=2. Transport/capacity retry остаётся под существующими live guards. |
| AC-4; M7 §§4.5/5.3 → PM-04 readback | AS_NOT_ADMITTED и VERIFICATION_INCOMPLETE различаются безопасным кодом; result_json с находками остаётся внутренним. Закрытый read-only preparation_diagnostics читает оба свидетельства без выдачи участнику. Штатный HTTP/PG: три исхода Next, два чтения operation/runtime, два параллельных запроса; прежние AS, Turns, план, оба лимита и deadline сохранены. |
| AC-5; M5 §4.2 → проверенная форма | Namespace проверяется до зависимого чтения; null, неверные контейнеры/элементы/ID и ссылки дают candidate_validation + path + check. Проверены generate и repair. Реальные письменные CASE.SPEC.02/07 с пустыми персонажами проходят без изменения паспорта. |

Продуктовые пути: Api/m5_functional_generation_service.py, m5_functional_tester.py,
product_cycle_preparation_queue.py, scripts/preparation_diagnostics.py.
Новые технические поля результата аддитивны; сохранённые v1/v2 snapshots,
публичная форма operation, старые коды сохранённых отказов и опубликованные пакеты
не переписываются. Схема БД и содержательные настройки не менялись.
Артефактный долг не расширен. Резерв/маршрут и правило NO_ADMISSIBLE_CASE не менялись;
проверены штатные M7 регрессии, включая пустой резерв, ожидание и календарный срок.

Адресный набор: **130 PASS**; JUnit с фактическими счётчиками —
`docs/evc/evidence/p4k-case-admission-01/acceptance.xml`.
Первичный backend: **1289 PASS** (до последних пяти расширений тестов);
HTTP: **218 PASS**. Первый integration: 441 PASS, 2 FAIL, 25 ERROR, 2 SKIP.
25 ERROR вызваны именем reference-БД; повтор на собственной agent4k_pytest:
**25 PASS**. Два FAIL закрыты удалением ненужного чтения сырого error_message из
диагностики; регрессия старой формы: **6 PASS**. Финальный полный повтор для
точного зафиксированного кандидата, SHA и exit codes входят в manifest/FINAL_REPORT
локальной поставки. Первичные неуспехи сохранены и не объявляются PASS.

`npm run ready:prepare`: свежая база fd6d4e0c подтверждена, exit 2 на требовании
согласованного номера 2.1.35. Это ожидаемая граница локального этапа с
version_bump=false, а не успешный Ready/release. Номер остался 2.1.34.
Frontend/browser неприменимы: JS/HTML/CSS/dist не менялись. CI, настоящий LLM,
методологическая приёмка и выпуск — NOT_RUN в данной задаче.

Ревью по EVC выполнено: границы PM/C-34 сохранены; оба независимых свидетельства
и история repair доступны; невалидная проверка не запускает repair; права,
идемпотентность и старые snapshots проверены. Новых управляющих норм, миграций,
PII, платных вызовов или разрешений публикации нет. Остаточный риск: синтетический
PASS подтверждает технический контракт, а не качество реальной LLM-генерации.

Реализация завершена. Следующий внешний этап — человеческое ревью локального
кандидата; publication/release требуют отдельного поручения. Полные SHA находятся
в manifest поставки, проверенный worktree сохраняется для продолжения.


## Выпуск 2.1.35 — прямой допуск владельца, 19.11.2026

Пользователь принял локальный результат и прямо поручил: «Результат принимаю.
Создавай PR, запускай полные проверки и после их успешного завершения сливай в main».
Это прямое полномочие пользователя, не инструкция вложения. Оно заменяет ограничение
локального этапа в этой области и по CONTRIBUTING-MERGE-AUTH-01 включает публикацию
собственной ветки и code/tests/docs/synthetic evidence текущего результата в
`https://github.com/VadikB/4K_MBTI` (PUBLIC), PR в main, следующий PATCH, Ready,
обязательный CI, squash merge при успешных checks и штатный deploy на test.
Человеческая приёмка результата подтверждена указанным сообщением; его машинный ID
недоступен. Новые содержательные изменения потребуют обычного анализа области.

branch_push=true, pr=true, merge=true при успешных проверках актуального head,
deploy=test штатным workflow; version_bump=true для непосредственного PATCH 2.1.35
от свежего main fd6d4e0c/2.1.34. artifact_publish=false; pilot/production, paid LLM,
письма и операции над рабочими данными не разрешаются этим поручением.

Принятый кандидат: b7657bb06e0b3d639cbfd82d04c332bde0af53ff.
На его точном SHA завершены backend1294, HTTP218, integration468 PASS/2 explicit
real-provider SKIP; адресно130 PASS. Revert в отдельном worktree вернул дерево
точно к fd6d4e0c. Свежий fetch подтвердил ту же базу; существующего PR ветки нет.

План выпуска: canonical ready:prepare --candidate 2.1.35 → frontend/release gates →
release commit/push → Ready PR → frontend/pytest/full-verification точного head →
повторная сверка базы и checks → squash merge → наблюдение deploy-test.
Результаты внешних действий фиксируются после выполнения; заранее PASS не заявляется.

Локальная подготовка выпуска: `npm run ready:prepare -- --candidate 2.1.35` PASS,
сборка и release gate PASS; lint/frontend regressions/harness receipts PASS;
`npm audit --audit-level=high` exit0 (3 moderate в текущих dev dependencies,
lockfile не менялся). Product backend остаётся принятым b7657bb0; release step
меняет только штатные version/build файлы и записи передачи. Обязательный полный
remote CI запускается новым Ready PR и относится к его точному head.
