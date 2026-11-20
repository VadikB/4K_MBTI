# ADM-FIX-03 — точное назначение обращения

## Итог текущего этапа

Локальная реализация и обязательный минимум завершены. Runtime-код зафиксирован
в 03dc1e3f4a14ea9af9ffbcc8813a8e421523052a; последующий commit содержит только
итоговый отчёт/STATE, описание будущего PR и дополнительные asserts исходного
текста/даты в уже прошедшем live browser тесте. База при финальном fetch осталась
3cc4934c59584ed06fa8ad17f83d85fb2db6c8f9. Версия 2.1.43 не менялась.

Устаревшая новая отправка А после Б получает 409 без записи под Б; принятая
команда А читается/повторяется со своей квитанцией после Б и после ответа админа.
Отдельная отправка того же текста в Б имеет своё обращение. Подмены пары/ключа/
текста и доступ чужого участника/tenant отклоняются. Ответ в новой сессии имеет
сохранённого автора, время и отдельный исходный текст обращения.

Открыто: человеческое review, визуальная приёмка владельцем; публикация ветки/PR,
CI и выпуск не входили в допуск этого этапа. Они NOT_RUN, не PASS. Технических
блокеров реализации нет. Полномочия branch_push/pr/version_bump/merge/deploy/
artifact_publish=false. Управляющие документы и runtime-артефакты не менялись.

## Разведка и границы

ТЗ прочитано целиком: /Users/vadim_bogachev/Downloads/P4K_ADM_FIX_03_Appeal_Binding_2026-11-20.md.
База origin/main: 3cc4934c59584ed06fa8ad17f83d85fb2db6c8f9, версия 2.1.43.
Ветка codex/adm-fix-03-appeal-binding, отдельный worktree; чужой dirty root сохранён.
Прочитаны точки acquaintance.report_issue, routes POST/GET issues, appeals list/claim/reply,
ensure_appeals_schema, onboarding отправка/draft/readback, dashboard атрибуция,
test_admin_appeals_db и browser admin appeals. POST не принимает показанную пару;
readback сравнивает текст без редакции/ключа, UI не показывает имя автора — дефекты
сохраняются после ADM-FIX-02. SQL/HTTP воспроизведение ещё не выполнено.

Источники процесса: AGENTS, README, CONTRIBUTING, agent-workflow,
verification-matrix, artifact-recipe; context v1.0, Registry, Change 01 README,
task manifest; отчёт Admin 03. M1 v1.4 FROZEN/CURRENT=NO; оценивание и runtime
артефакты не меняются. Контекст прошлых ADM-FIX переиспользован только там,
где документы не менялись. Полные реквизиты и фактические проверки дополняются.

## Исходный план совместимости (допуск получен ниже)

1. Адресная регрессия HTTP/PG на изолированной новой БД: старый экран А после Б.
2. Команда получает UUID operation_id и точную пару assignment_id / questionnaire_revision_id.
   Managed POST без пары или с устаревшей парой — 409, новая запись не создаётся.
   Ранее принятый operation_id сначала читает квитанцию владельца и сверяет исходный
   запрос; текущее назначение не подставляется. GET отдельной операции также owner-only.
3. Новая append-only таблица команд обращения: PK(user_id, operation_id), исходная
   пара/запрос и квитанция со ссылкой на сохранённое обращение. Сохранение атомарно
   с обращением, concurrent same-key сериализован. Существующие таблицы сообщений,
   scope/message unique и ответы сохраняются без переписи и backfill. Исторические
   строки не получают выдуманный ключ/связь. Старый код игнорирует таблицу команд;
   rollback приложения сохраняет всю новую историю (поведенческий старый дефект вернётся).
4. UI фиксирует пару при открытии формы, сохраняет ключ вместе с draft до отправки,
   восстанавливает по квитанции/точной паре, не угадывает по тексту. Ошибка сохраняет ввод.
5. Ответ участнику: разрешённое full_name пользователя по сохранённому author_user_id,
   без email/прочих полей; если автора/имени подтвердить нельзя — роль и время.
   Ответ, исходное сообщение и сохранённый автор/время остаются раздельными.

## Полномочия и стоп-условия

Локальная реализация/проверки разрешены запросом пользователя. branch_push/pr,
version_bump/merge/deploy/artifact_publish=false: текст ТЗ не является отдельным
разрешением на публикацию. Первоначально расширение схемы/API и публичного реквизита автора ожидало
конкретного допуска по AGENTS и agent-workflow; решение владельца зафиксировано ниже.
Остальные стоп-условия: предметные нормы/границы PM/артефакты/production доступ не меняются;
удаление/миграция старых записей не требуется; откат выше, проверка совместимости обязательна.

## Проверки и передача

Адресные SQL/HTTP, конкурентный повтор, tenant/owner изоляция, старые строки и code-only
rollback; browser формы с lost response и сменой назначения, dashboard новой сессии;
backend, HTTP, полный integration на test/pytest DB; frontend regression, lint/build,
diff и review-checklist. Реальные LLM и внешняя почта отключены. Визуальную приёмку
проводит владелец. Ни одна проверка пока не заявлена PASS. Активный шаг — регрессия
и согласование расширения; далее реализация, полный минимум, отчёт/коммит.

## Фактическая регрессия до исправления

SHA256 ТЗ: 2220403e0d8400a16b6671ad240a65a9c02d859af7839b95485869c549205290.
20.11.2026: новая PostgreSQL 15, UTF8, localhost:55484,
/private/tmp/adm-fix-03-pg-utf8.l52jAK/data; database agent4k_pytest и disposable
marker-owned child DB. Команда:
PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 STAND_ADMIN_URL=postgresql://adm_fix_pytest@127.0.0.1:55484/postgres /Users/vadim_bogachev/Developer/4K/.venv/bin/python -m pytest tests/integration/test_path_admin_contract_owned_stand.py --run-integration -q
— ожидаемый FAIL / exit 1: child 24 PASS / 1 FAIL. Реальные cookie sessions,
назначения/отмена/источники/early readiness. Экран А=23, новое Б=24, POST с исходной
парой А и UUID вернул 201, в БД assignment_id=24, questionnaire_revision_id=25.
Журнал /private/tmp/adm-fix-03-repro-utf8.log. Child БД штатно удалена.
Первый инфраструктурный запуск не дошёл до продукта: initdb --no-locale создал
SQL_ASCII, marker вернулся bytes и ownership guard отказал. Этот кластер остановлен;
повтор создан с явным --encoding=UTF8, проверка владения не ослаблялась.
Новая UTF8 PostgreSQL остановлена после регрессии; данные только синтетические.
Зависимая реализация не начата: ожидает ответ на конкретный допуск схемы/API/имени.
npm ci --offline PASS. Полный локальный минимум до исправления не выполнялся.

## Решение владельца

20.11.2026 владелец ответил «Разрешаю совместимое расширение» на конкретный
план append-only квитанций, API operation_id/точной пары, 409 managed POST без
корректной пары и full_name по сохранённому author_user_id с fallback роли.
Допуск действует для реализации в ветке и изолированных проверок; выпуск не входит.
Открытый стоп расширения закрыт.

## Реализация и трассировка

| Правило | Данные / код | Проверка |
| --- | --- | --- |
| Сообщение относится к показанной паре | AcquaintanceIssueRequest, report_issue: exact pair из readiness; FOR SHARE назначения против cancel/bind | owned HTTP/PG: старый экран 409, неправильная редакция/ID 409, после refresh Б принимает тот же текст |
| Повтор возвращает исход отправки А | participant_data_issue_operations PK(user_id,operation_id), request_json/receipt_json; advisory transaction lock, атомарная запись | lost reply/replay А после Б; concurrent same-key одна запись; поздний SQL failure откатывает сообщение |
| Квитанцию нельзя подменить | owner-only POST/GET operations + exact pair/request validation; неизменяемый trigger | 403/404 для другого участника/tenant, 409 для другой пары/текста, UPDATE/DELETE запрещены |
| UI не угадывает исход | пара фиксируется при открытии, ключ и запрос сохраняются до POST вместе с draft; recovery GET по ключу и исходной паре | browser: смена active после записи А, подставная квитанция, reload/retry и изоляция draft Б |
| Ответ/автор/время отдельно от исходного обращения | существующая replies, JOIN только по сохранённому author_user_id, наружу display full_name или null, без ID/email | реальные HTTP/PG и новая browser-сессия; legacy без full_name даёт null/fallback роли |
| M4.4: фиксированный контекст не меняется обращением | ни профили, ни source bindings, ни оценка не обновляются | owned HTTP/PG snapshots и общие ADM-FIX-02 проверки сохраняются |

Ключ операции — ограниченная строка (1..200), обычно UUID из createOperationId;
поддерживается существующий opaque fallback helper для старых браузеров. Это технический
формат ключа, предметная норма не меняется. GET неизвестного ключа — 404; новый managed
POST без корректной пары/ключа — 409. Legacy действительно без пары сохраняет прежний
путь, исторические строки читаются по своим сохранённым полям без подстановки active.
Participant GET вместо внутреннего reply_author_user_id возвращает только разрешённый
reply_author_display_name. Имя читается из существующего users.full_name по сохранённому
ID автора; исторический снимок имени не выдумывается, отсутствие имени даёт null.

Изменены Api/acquaintance.py, appeals.py, database.py, routes.py, schemas.py;
web/js/screens/onboarding.js, dashboard.js, onboarding-flow.js, acquaintance-errors.js;
соответствующий web/dist; SQL/HTTP suites, browser W02 и live Admin03 fixtures.
Предметные артефакты, конфигурация оценивания и управляющие документы не менялись.

## Проверки рабочего кандидата (полный набор выполняется)

- Адресные test_admin_appeals_db + test_w02_acquaintance_db + owned wrapper:
  10 PASS / exit 0, 17.75 s; child включает 25 реальных cookie/HTTP/PG проверок.
- Backend npm run test:backend: 1305 PASS, 713 deselected / exit 0, 130.34 s.
- Frontend node --test tests/frontend/*.test.mjs: 476 PASS / exit 0, 8.02 s.
- npm run lint:js и npm run build:web: PASS / exit 0; версия остаётся 2.1.43.
- Browser w02-acquaintance.spec.mjs + admin-appeals.spec.mjs: 8 PASS / exit 0,
  19.9 s после сборки. Первый запуск 7 PASS/1 FAIL использовал bundle main до
  пересборки; новая проверка показала отсутствие пары, поэтому старый прогон не
  засчитан. После сборки все проверки проходят, assertions не ослаблялись.
- Live Admin03 UI→HTTP→PG: PASS, создание/claim/reply; новая сессия читает ответ и
  full_name автора, другой участник получает 403. Этот harness подставляет early
  readiness; настоящая readiness/контроль пары отдельно проверены owned suite.
- Первый адресный повтор после правок fixture: 7 PASS/1 FAIL из-за имени переменной
  теста W02; fixture исправлена, финальный адресный повтор выше PASS.
- HTTP и полный integration: RUNNING; полнота локального минимума пока не заявлена.
- Журналы /private/tmp/adm-fix-03-{targeted2,backend,frontend,lint,build,browser-built,live,http,integration}.log.

## Совместимость и откат

Expand применяется ensure_appeals_schema существующим bootstrap, повторный вызов
проверен. Старые reports/replies не переписываются, backfill нет. Прежний INSERT
ON CONFLICT(user_id,organization_id,scope_key,message) работает с новой таблицей
квитанций, их содержимое остаётся прежним. Down migration/удаление квитанций не нужны.
Code-only rollback на 2.1.43 сохраняет таблицу и сообщения/ответы; старый API не знает
новый recovery и возвращает прежний дефект привязки — это предел отката, не потеря данных.
Новые API читаются только после expand; перед возможным выпуском обязательны
Ready/release gate/full CI, человеческое review и отдельный допуск выпуска.
Штатный account/org purge обнаруживает FK граф динамически и управляет USER triggers
в своей транзакции; его контур не менялся (проверен scripts/purge_test_organization.py).

## Реквизиты источников и review

Прочитаны M4.Context v1.0 §M4.4–4.5, зеркало
assessment_definitions/contexts/competencies_4k/1.1/m4_context_source.md,
SHA256 9af86011c1ea1bef12058700bdd345c5cee335bbc6ec4d392fcfc4f3e5709fd1;
Change01 §И-1/И-6/И-7, source.pdf SHA256
 dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081;
ADR-002: C-23/24 и раздел хранения/повторов/совместимости — технический контекст,
обращение не становится Dialogue Turn или оценочным Evidence. Применён инвариант
M4.4 сохранения контекста предыдущей оценки; новый смысл M1 не вводится.
Отсутствующих предметных оснований для этой административной поправки не выявлено.

Self-review по docs/evc/review-checklist.md: diff ограничен ADM-FIX-03, права owner/
tenant проверены; публичное имя и расширение имеют явный допуск; прежние snapshots
не меняются; запрос не запускает LLM, оценивание или исправление профиля; история и
rollback сохранены. Проверка динамического purge/FK графа — анализ кода, не отдельный
запуск удаления аккаунта с новой квитанцией. Человеческое review этим не заменено.
Визуальная приёмка остаётся владельцу; browser asserts подтверждают поведение,
но не назначают человеческий PASS. Черновик описания PR: adm-fix-03-pr-body.md.


## Окончательные проверки и очистка

Для runtime-кода 03dc1e3f и неизменённых потребителей, все команды exit 0:

| Команда | Фактический результат |
| --- | --- |
| `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 npm run test:backend` | 1305 PASS, 713 deselected; 130.34 s |
| `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 npm run test:backend:http` | 219 PASS, 15 deselected; 67.86 s |
| `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 TEST_DATABASE_URL=… STAND_ADMIN_URL=… npm run test:backend:integration` | 488 PASS / 2 explicit real-provider SKIPPED, 1528 deselected; 925.93 s |
| `node --test tests/frontend/*.test.mjs` | 476 PASS; 8.02 s |
| `npm run lint:js`, `npm run build:web` | PASS, 2.1.43 без bump |
| `npx playwright test tests/browser/w02-acquaintance.spec.mjs tests/browser/admin-appeals.spec.mjs` | 8 PASS; 19.9 s |
| `.venv/bin/python -m pytest tests/integration/test_admin_appeals_db.py tests/integration/test_w02_acquaintance_db.py tests/integration/test_path_admin_contract_owned_stand.py --run-integration -q` | Финальный адресный повтор на 03dc1e3f: 10 PASS; 20.38 s |
| `TEST_DATABASE_URL=… ADMIN03_PYTHON=… node tests/browser/admin-appeals-live.mjs` | PASS; финальный повтор дополнительно проверил видимые исходный текст, имя и дату |
| `git diff --check`, существование локальных ссылок/описанных команд | PASS |

TEST_DATABASE_URL указывал исключительно на
postgresql://adm_fix_pytest@127.0.0.1:55484/agent4k_pytest,
STAND_ADMIN_URL — тот же собственный localhost:55484/postgres. Child БД создавались
и удалялись marker-owned harness. Реальные LLM SKIPPED:
tests/llm/test_m10_real_cycle_db.py:148 и :338; платных вызовов и почты нет.
Журналы дополнены /private/tmp/adm-fix-03-targeted-final.log и live-final.log.
PostgreSQL /private/tmp/adm-fix-03-pg-utf8.l52jAK/data остановлена штатно:
server stopped / exit 0. Проверенная временная .venv-ссылка удалена; основной
интерпретатор, чужой dirty root и пользовательские данные сохранены.

Следующий минимальный шаг: человеческое review локального результата и решение о
передаче одного PR. Уже согласованный допуск схемы/API/full_name повторно не требуется.
Перед возможным merge нужны разрешённый кандидат, актуальная база, Ready и полный CI.


## Передача в draft PR

На сообщение о завершении локальной реализации и следующем этапе передачи одного
PR владелец ответил «продолжаем». Следующий согласованный шаг — push этой ветки
в VadikB/4K_MBTI и один draft PR через встроенный браузер: branch_push/pr=true.
Это не принятие человеческого review и не допуск выпуска: version_bump/Ready/
merge/deploy/artifact_publish=false. Локальные проверки runtime 03dc1e3f остаются
применимы; после него менялись только отчёт и дополнительные live assertions.
