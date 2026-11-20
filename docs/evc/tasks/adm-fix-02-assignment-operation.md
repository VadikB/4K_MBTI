# ADM-FIX-02 — повторное назначение и сохранённый исход команды

## Результат и границы

Основание: прямой запрос владельца от 20.11.2026 реализовать ТЗ
`/Users/vadim_bogachev/Downloads/P4K_ADM_FIX_02_Assignment_Operation_2026-11-20.md`
в рабочей ветке. ТЗ прочитано целиком; оно задаёт требования и само не разрешает
внешнюю публикацию/миграцию рабочих данных. Прошлый допуск ADM-FIX-01 не переносится.

База свежего `origin/main`: `dcd876f23036d0750b516e9eccf60f54daaae224`, 2.1.42.
Ветка: `codex/adm-fix-02-assignment-operation`; отдельный постоянный worktree.
Основной checkout с посторонними изменениями не меняется.

Включено: неизменяемый результат batch-команды, точный replay POST/GET,
доказуемый legacy readback/явная неопределённость, source binding конкретного
назначения, повторная проверка допустимости источников, HTTP/PG регрессии.
Не входит: изменение правил отмены/старта, перепись сохранённых M4 snapshots, оценивания, предметных
артефактов, UI-дизайна, выпуск приложения или платный LLM.

## Разведка и применимость

На актуальном main GET операции выбирает active assignment без связи с командой.
Операция хранит только fingerprint и не сохраняет поадресные исходы. `bind`
ищет confirmation по user/org/ref вместо точного назначения, а historical reuse
возвращает источники до проверки их допустимости.

Прочитаны: README.md, CONTRIBUTING.md, AGENTS.md; workflow/matrix/artifact-recipe,
task-template/review-checklist; architecture context 1.0/Registry, Change 01 README,
task SourceSet manifest и применимые И-2/3/6, ADR-002 C-23/C-24, ADR-003
ProgramDefinition; M4.Context v1.0 §M4.4; существующие assignment, cancellation,
program, acquaintance routes/контракты и адресные SQL/HTTP tests. Неизменённый
контекст ADM-FIX-01 и общие EVC документы переиспользованы из той же сессии.
M1 v1.4 FROZEN/CURRENT=NO; CURRENT и runtime-артефакты не меняются.

M4.4 → отдельный frozen профиль конкретной оценки → C-23/C-24, PM-02,
LU-02.5/02.6 → точные assignment/source refs → bind/late readiness → SQL/HTTP.
ADR-003 → применимость опубликованной программы и ролей → resolve/options →
проверка источников нового назначения, включая повторное использование.
Техническая квитанция команды — серверные данные идемпотентности, не новый
предметный артефакт. Вводить новую предметную норму не требуется.
Отдельные исходные карточки ADM-PATH-02/ADM-FIX-03 в репозитории не найдены;
сверка общей идентичности выполняется с действующим ADM-FIX-01 и runtime-кодом.

## Согласованный совместимый переход для квитанций

В прежней таблице операций нет места для результата. Реализуется только expand:
новая append-only `organization_assessment_assignment_operation_results` с PK
`(organization_id,actor_user_id,operation_id)`, composite FK на существующую
операцию, `request_json JSONB`, полный `request_fingerprint`, `result_json JSONB`, `created_at`.
В исходных operations/assignments формат fingerprint сохраняется для старого кода;
новая квитанция дополнительно фиксирует полный запрос, включая configuration selector.
Результат содержит исход для каждого адресата, assignment_id при успехе и
машинный код причины отказа. Триггер запрещает UPDATE/DELETE результата.
Новая квитанция и все эффекты сохраняются одной транзакцией; существующий unique
operation key сериализует конкурентные повторы. Валидация текущих прав остаётся
перед replay, параметры сверяются по fingerprint и сохранённому request_json.

Существующие таблицы/колонки и квитанции не переписываются. Backfill нет.
Legacy outcome восстанавливается только из assignment с точными org/actor/op/
fingerprint; при отсутствии доказательства возвращается `uncertain` без ID.
Текущее active назначение не подставляется в исторический результат.
Чтение старых квитанций проверяется до/после expand и после отката приложения.
Откат: revert приложения; новую таблицу/историю оставить, старый код её игнорирует.
Удаление квитанций при rollback запрещено. Рабочие БД не цель автотестов.

20.11.2026 владелец явно ответил «Разрешаю совместимое расширение» на вопрос о
новой append-only таблице, дополнительных reason_code/uncertain и проверках только
на новой изолированной БД, без выпуска на TEST. Зависимая реализация началась
после этого ответа. Деструктивной миграции/автоматического backfill нет.

## Стоп-условия и полномочия

1. Новая предметная норма — нет.
2. Schema/public contract — изменение есть: append-only result и additive reason
   code/uncertain; совместимость/откат выше, допуск владельца получен. Открытого стопа нет.
3. Миграция с удалением/потерями — нет; backfill/перепись запрещены.
4. Отсутствующая обязательная предметная норма — не выявлена.
5. Новый предметный формат/контур — нет.
6. Права/развёртывание — не расширяются, внешняя передача не разрешена.
7. Откат — определён выше.
8. Выход за область — нет.

Разрешены локальная реализация, коммиты, синтетические изолированные test/pytest
БД, подставные внешние сервисы и проверки. `branch_push=false`, `pr=false`,
`merge=false`, `deploy=false`, `version_bump=false`, `artifact_publish=false`.
Один PR — целевой состав результата после отдельного допуска публикации.

## План и проверки

1. Разведка свежего main — завершена; оба дефекта присутствуют.
2. Воспроизведение на базе — завершено: новая редакция/роль дают SOURCES_FROZEN,
   legacy GET подставляет active assignment вместо явной неопределённости.
3. Bind-fix и атомарное сохранение квитанции — реализованы после решения expand.
4. Приёмка A → допустимая отмена → Б; старые/новые источники и роль, запрещённые
   источники, historical profile/checksum, отмена после старта.
5. Lost reply/concurrent replay/partial batch/legacy uncertainty/foreign actor/
   changed request; атомарный rollback при позднем SQL-сбое.
6. Локальный минимум: backend, HTTP, full integration на новом localhost PG,
   `git diff --check`; frontend-набор при изменении его границы/fixtures.
7. Review, полный отчёт, SHA и подготовленный текст одного PR. CI перед merge
   обязателен; merge/deploy вне текущего допуска.

## Текущее состояние

Реализация и адресные проверки выполнены. Первый общий прогон остановлен штатным
SIGINT после доработки совместимости; он не объявляется PASS. Полный набор будет
повторён на зафиксированном кандидате. Публикации/CI/выпуска нет.

На промежуточном `d3b0ed72e9106b78290b3f5d5da382ca092bd691` дополнительно
обнаружен обход: до собственного confirmation Б мог получить ready через профиль А.
Общий `CONFIRMATION_ASSIGNMENT_SCOPE_SQL` теперь применяется в bind, W02
save/resolve/late gate и общей административной проекции ADM-FIX-01. Modern JSON
содержит точный assignment_id; legacy требует собственного времени source binding
(оба timestamps имеют NOW clock) либо точной Cycle-связи. Старое подтверждение
до binding Б не подходит. GET не создаёт confirmation/profile или очередь.
Б может подтвердить новые ответы по штатному W02; профиль А не переписывается.
Задержанный resolve А не переключается на Б после смены назначения.

Промежуточные полные прогоны остановлены после доработок: первый — 290 PASS до
SIGINT, второй также прерван; ни один не засчитывается как полный PASS.
Окончательный SHA и полный повтор записываются ниже после фиксации.

ТЗ SHA-256: `56241fbb54f43ae4c6c91f14989330aab6475ee26429e15a1a21afa1784163c9`.
M4 mirror SHA-256: `9af86011c1ea1bef12058700bdd345c5cee335bbc6ec4d392fcfc4f3e5709fd1`.
Change 01 PDF SHA-256: `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081`.

## Реализация и проверка требований

Промежуточный кандидат: `956fa0dfb6f5d775695574d7e0e6e3b77a55e604`:
backend 1305 PASS, HTTP 219 PASS, frontend 476 PASS; полный integration дал
484 PASS / 2 FAIL / 2 explicit LLM SKIPPED (765.74 s). Оба FAIL — изолированный
PM-02 без таблицы m5_cycles. Отсутствие optional Cycle witness теперь даёт FALSE
в соответствующей ветви SQL, а не зависимость создания первого M4 от PM-04.
Точное назначение в JSON и собственный binding provenance проверяются всегда.
Изолированные PM-02 тесты не ослаблялись и не заменялись подставным PASS.
Окончательный кандидат и повтор полного набора фиксируются ниже.

- `Api/assessment_assignment_operations.py`: unique operation INSERT сериализует
  одинаковые команды; request/result сохраняются одной транзакцией с assignments
  и bindings. Result immutable на уровне PostgreSQL. Полный fingerprint включает
  явный configuration selector; старый header fingerprint совместим с прежним кодом.
- `Api/routes.py`: текущие права проверяются перед replay. Сохранённая квитанция
  читается до текущих readiness/program checks; существующая историческая команда
  не назначает текущее поколение повторно. Отсутствующая operation → 404,
  несовпадающие параметры → 409. Legacy без доказательства → uncertain без ID.
- `Api/schemas.py`: additive `reason_code`; `uncertain` использует прежнее строковое
  поле status. Параметр configuration selector добавлен к GET readback. Существующий
  frontend при uncertain сохраняет неизвестный исход, успех не показывает.
- `Api/assessment_assignment_sources.py`: sources проверяются перед любым reuse;
  frozen guard относится к confirmation/profile именно этого назначения. Новое Б
  не меняет sources А. Общая SQL-проверка scope нужна W02 и admin projection.
- `Api/acquaintance.py`: новые подтверждения включают assignment_id в свой JSON/
  checksum; Б проходит W02 и формирует свой профиль. Legacy профиль сохраняется
  только при доказанном scope; старые JSON/checksum не пересчитываются. Поздний
  resolve не перескакивает с А на Б. Старый unmanaged W02 остаётся совместимым.
- `Api/admin_assignment_projection.py`: строка/сводка используют тот же scope
  confirmation. Даже exact modern operation не подменяет отсутствие профиля Б.
- Регрессии расширяют существующие suites, а не создают параллельный продуктовый
  путь: adm1c receipts, adm31 cancellation, questionnaire/lineage и marker-owned
  path_admin_contract. Для W02 используются настоящие lifecycle M4 и HTTP routes.

| Критерий | Фактическая проверка | Итог адресного набора |
| --- | --- | --- |
| А → отмена до старта → Б, readback/replay А и Б | Реальные sessions + HTTP/PG, точные ID и исходный status | PASS |
| Б со старыми источниками / новой редакцией / новой ролью | Три параметризованных сценария; свои ответы и новый M4; А/profile/confirmation/checksum без изменений | PASS |
| Ранний допуск Б | HTTP показывает отсутствие собственного profile, preparation_scope отказывает; современная operation сама профиль не заменяет | PASS |
| Замороженный А и отмена после старта | Существующие cancellation/start/lineage guards и отрицательный bind А | PASS |
| Запрещённые источники | Реальные AC10 program/role/catalog/tenant/ref negatives; повторное использование недоступного config отклонено | PASS |
| Lost reply / одновременный same-key | Идентичный ответ и одна запись результата; different-key сохраняет собственный исход already_assigned | PASS |
| Частичный пакет и последующая смена eligibility | Assigned/not_assigned с reason_code сохраняются при POST/GET replay | PASS |
| Чужой actor/org, потерянные права, подмена запроса | Реальные 403/404/409; cfg/role/recipient substitution не получает успех | PASS |
| Атомарность | Реальный поздний bind SQL failure и trigger failure в финальной записи результата; snapshot всех effects неизменён | PASS |
| Immutable result | UPDATE и DELETE отклоняются PostgreSQL trigger | PASS |
| Legacy и откат | Unknown без связи; exact historical ID после revocation; readback до/после expand; прежний INSERT при наличии новых квитанций | PASS |

## Review и эксплуатация

Техническое EVC review: один результат, scope/права проверяются сервером;
fingerprint, status и assignment_id принадлежат команде, GET не создаёт эффектов.
UI/сценарий, предметная модель и техническое хранение разделены. Новых prompts,
справочников, thresholds, нормативных fallback или изменений опубликованных
пакетов нет. Профиль/отмена/подготовка/старт остаются разными условиями.
Сохранённые snapshots/контрольные суммы и API-маршруты не переписываются.
Синтетические test fixtures не являются нормой или подтверждением human review.

Миграция — только аддитивный CREATE TABLE в действующем bootstrap sources.
На рабочие TEST/production БД не применялась. В приложении до expand нельзя
использовать новую команду: обязательная таблица не подменяется transient fallback.
GET старой operation совместим и до появления таблицы результатов.
Откат сохраняет новую таблицу/записи; старый код продолжает читать старые поля и
fingerprint. Его прежние дефекты readback после отката снова возможны. Исправлять
историю миграцией либо выдавать текущую assignment за старую receipt запрещено.

Открыто: внешний CI, человеческое review/визуальная приёмка и отдельный допуск
публикации/выпуска. Предметных неразрешённых решений ADM-FIX-02 нет. Задача не
объявляет полный продуктовый PATH, методологическое качество M4/AS или baseline.

## Окончательная проверка

Промежуточные runtime/tests: `c2a451f03b6d5098875feb7e815ed1b987a07514`.
Адресный повтор после optional Cycle fix: 43 PASS / exit 0 (16.51 s).
Полные backend: 1305 PASS / exit 0 (91.41 s); HTTP: 219 PASS / exit 0 (50.53 s);
frontend: 476 PASS / exit 0 (2968 ms). Его полный integration прерван после
дополнительной проверки действующего frontend: readonly формы опирается на
mandatory_complete. На c2a451f0 HTTP-модель Б наследовала этот признак А:
same/role — 2 FAIL / 22 PASS внутри owned suite. Это не засчитывается как PASS.

Исправлен только read-model: при отсутствии собственного confirmation timestamp
старой active projection не означает подтверждение Б. Значения ответов остаются
доступным draft, GET ничего не сохраняет, API shape не меняется. Непривязанный
собственный confirmation после явного confirm при этом считается подтверждённым
и может штатно разрешиться в M4. Адресный набор после исправления: 43 PASS / 0,
18.28 s, включая actual HTTP mandatory_complete=false/новые ответы Б/новый M4.
Следующий полный прогон выполняется на новом зафиксированном SHA.

Фактические команды из worktree (dotenv отключён):

```sh
PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 npm run test:backend
PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 npm run test:backend:http
PYTHON_DOTENV_DISABLED=1 TEST_DATABASE_URL=postgresql://adm_fix_pytest@127.0.0.1:55483/agent4k_pytest STAND_ADMIN_URL=postgresql://adm_fix_pytest@127.0.0.1:55483/postgres npm run test:backend:integration
node --test tests/frontend/*.test.mjs
git diff --check
```

Изолированный собственный PostgreSQL 15.16 создан для задачи с нуля:
`/private/tmp/adm-fix-02-pg.6fY5qN/data`, localhost:55483, только синтетические записи.
Временная ссылка `.venv` ведёт на существующий интерпретатор рабочей среды;
`.env`/рабочие БД/секреты не читались. Два explicit real-provider acceptance не
входят в стандартный фактический LLM-прогон; настоящих LLM/писем не было.
Логи финальных прогонов: `/private/tmp/adm-fix-02-{backend,http,integration,frontend}-verified.log`.

Следующий шаг: полный повтор на новом SHA, затем остановить только свой PostgreSQL,
удалить только свою ссылку .venv, перепроверить Git/diff/ссылки, закоммитить отчёт
и текст PR. Незавершённые/failed промежуточные прогоны сохранены отдельно.
Новых push/PR/версии/Ready/merge/deploy по текущему допуску нет.
