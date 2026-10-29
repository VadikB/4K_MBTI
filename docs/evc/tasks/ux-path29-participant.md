# UX-PATH29 — единый путь участника

## Результат и границы

Запрос владельца 29.10.2026: выполнить четыре задания внешнего пакета одним PR.
Один независимо принимаемый результат: письмо с доверенным origin → назначение →
знакомство W01/W02 → согласие и три собственных ответа → подтверждение →
фоновая подготовка/восстановление → явный старт той же подготовленной ситуации.
Не входят: редизайн админки, Stage 2, методологические нормы, deliverability,
pilot/production, удаление данных, перезапись frozen M4/Cycle/AS/snapshots.

База после `git fetch origin main`: `a86775ff011a51831f9f86596be3dd776de79d11`,
2.0.34. Ветка `codex/ux-path29-participant`, переиспользован чистый прикреплённый
worktree `/Users/vadim_bogachev/.codex/worktrees/ux-adm28-add01-v2/4K`.
Основная пользовательская копия и её untracked/другие worktrees не меняются.

## Источники и чтение

Пакет: `P4K_Participant_Path_Tasks_2026-10-29.zip`, SHA256
`c6c70d9ba548cce1a8d01b18a4398ff0efea664fd62901334d036e196874e4cb`.
Распакован в `/private/tmp/p4k-participant-20261029.7Jo7NU`.
Прочитаны полностью START_CODEX, REPORT, DATA_CONTRACT, TASK01–04, ACCEPTANCE,
reference/READ_FIRST, W01 README/CHECKSUMS. W01 0.1/14.10.2026: 11/11 hashes PASS,
эталон не меняется. Исторические demo-вопросы/числа/фон/skip не являются runtime.
START SHA256 `2cd0e55a17634c0d6dd1777838c26d12249181b882649b132eedd0734f520f80`;
DATA_CONTRACT `65a9500e0b0de48c33defbbb04af6d1587ffc4151e81382e393280580c244fa6`;
ACCEPTANCE `004f2dae5c6dc998f633760ded36698387d5c9787171829548d1aa2bffc870bf`.

Прочитаны/повторно использованы неизменённые на этой базе: AGENTS, README,
CONTRIBUTING, EVC workflow/matrix/recipe/task-template/review-checklist;
архитектурные context/Registry, M1 1.4 FROZEN/CURRENT=NO, Change 01 README,
task SourceSet manifest, ADR-002/traceability; карточки W02, CTX01 и W02 ADD02/03.
Адресное чтение M3/M4/M5/M7 contracts/runtime и UI продолжается до реализации.
PM-02 владеет ролью/M4, PM-03 подготовкой AS, PM-04 стартом/временем;
ответы участника не Evidence, организационный текст не меняет фактическую оценку.
Corporate вопросы — существующий artifact participant_context/corporate/1.0,
definition SHA256 `3d4c18bbec032822b1c90e912f7ffadb4cd6f2765439d5fec16d2142a2d49071`.

Пробелы: отдельный P4K.DEV.PRINCIPLES 1.0 и исходный PDF ТЗ Кати не найдены в
архиве/репозитории; доступны EVC и приложенные W01/текстовый excerpt. Не объявлять
прочитанным отсутствующий источник. Конкретная operation из 8.jpg не идентифицирована;
владелец уточнил время: 28.10 около 22:40 МСК и разрешил диагностику логов/БД.
В journal test за 19:10–20:10 UTC найдены шесть preparation_failed в 22:40–22:46
МСК, все `ValueError / M4_PROFILE_NOT_READY`, стек `participant_profile.py:69`:
`get_selected_role_profile` вернул None. Это отказ до генерации, не provider failure.
Read-only сверка БД подтвердила все шесть failed operations: одна попытка,
нет result trace; текущие confirmation/consent сохранены, M4/роль не связаны.
Конкретный screenshot не связан с одним UUID без дополнительных данных; совпадение
окна и одинаковая причина подтверждены журналом и сохранёнными операциями.
[Безопасное доказательство](artifacts/ux-path29/incident-2026-10-28.md).

## Разведка: подтверждённое кодом, не состояние live-БД

- questionnaire briefing отдаёт ключи-строки; onboarding renderer ждёт label/value.
- `_bind_confirmed_answers` зависит от глобального `len(configs)==1` и роли user.
- journey после completed/skipped и incomplete M4 выбирает legacy complete_profile.
- answers confirmation ожидает prepare перед переходом к 4К; skip открывает AI-welcome.
- URL писем собираются из settings.app_base_url; effective server origin ещё не проверен.
- API назначения содержит assignment_ref/recipients, но не явные role/config refs.
  M4 уже различает determined_by=user/organization; применимость административного
  механизма и tenant-прав уточняется до расширения связи.

## План и состояние

1. Разведка и воспроизведение: реальные формы/назначение без готового M4,
   две published configurations, данные и consent, очередь и повтор.
2. TASK01: единый валидируемый trusted origin, controlled mail sink,
   deployment/effective-origin verification без секретов.
3. TASK02: participant-safe projection, явная допустимая роль/config binding,
   канонический scoped resume, обязательные шаги на сервере, совместимость истории.
4. TASK03: последовательный чат W01 с поздними решениями, сохранённый ввод,
   адресные действия/error/busy/focus, геометрия шести viewport и zoom/short height.
5. TASK04: диагностика причины, операция до ожидания, независимая подготовка,
   recovery/dedup/scope, prepared → explicit idempotent start без раннего времени.
6. Полный применимый минимум, один candidate/PR, CI exact head, отчёт U01–U07.

TASK01–04 реализованы в рабочем diff. Активна сквозная проверка и регрессии;
выпуска, PR и полной приёмки ещё нет. Предметные опубликованные пакеты не менялись.

### TASK02: expand / compatibility / recovery до записи схемы

Основание допуска: прямой запрос владельца выполнить TASK02 пакета, разрешающий
минимальную аддитивную привязку источников в существующем tenant-admin механизме;
M4 допускает `determined_by=organization`. Не вводим публикацию или редактирование
методологии для org-admin. Выбор — только опубликованные M3/configuration и
опубликованный assessment catalog, доступный данной организации, не QA другого tenant.

Expand: новая таблица append-only `organization_assessment_source_bindings`:
assignment FK, questionnaire revision, configuration/role FKs, actor/time/operation.
Старые строки назначения не переписываются/backfill не выполняется. Новая редакция
связи допустима до первого bound M4 этого назначения; после — только новое назначение,
без изменения исторического snapshot. Повтор operation возвращает ту же связь либо
409 при несовпадении. Scope чтения: organization+recipient+assignment+questionnaire
revision. Отсутствие точной связи — ожидание, не global/default fallback.

Совместимость: новые поля admin request optional для прежних клиентов; без них
сохраняется создание назначения, но подготовка ждёт ответственного. GET options
с tenant gate отдаёт только доступные опубликованные источники для выбора, не
новые права публикации. Участник не может назначать себе источники этим API.
После подтверждения ответы read-only; изменение требует нового назначения,
одинаковый транспортный replay не снимает подтверждение. Отдельная идемпотентная POST-команда разрешает M4 из
тех же сохранённых ответов; GET состояния не создаёт M4. Legacy snapshot продолжает
свой контракт чтения; ответы знакомства не заменяются duties/организационным текстом.

Откат: revert приложения, таблица/история связей остаются; старый код её игнорирует.
Не удалять ответы, согласия или M4/Cycle. Фактические записи live не меняем до gates.

Для совместимости single-row legacy state добавляется scoped history
`participant_acquaintance_scope_states` (user+organization+assignment+questionnaire
revision → сохранённый state). Перед переключением активного scope его draft и
факт согласия архивируются, при возврате читаются из того же scope; GET не пишет.
Это техническое хранилище состояний, не новый предметный артефакт. Null legacy
revision кодируется 0 только в ключе history; исходный state сохраняет NULL.
Текущая таблица остаётся совместимым active projection, destructive migration нет.

Дополнение expand перед реализацией: append-only
`organization_assessment_assignment_operations` хранит org+actor+operation_id и
fingerprint всего batch (включая состав участников и явные source refs). Это
техническая идемпотентность команды, включая случай, когда все назначения уже
существуют и новые строки assignments не создаются. Конкурирующий повтор
сериализуется уникальным ключом; иные параметры с тем же operation_id → 409.
Старые operation fingerprints проверяются дополнительно; backfill не нужен.
Откат кода оставляет журнал неизменным, старый код его игнорирует.

## Стоп-условия и решения

1. Новые предметные нормы — нет; существующие artifacts/snapshots сохраняются.
2. Контракты/данные — анализируется минимальное аддитивное расширение refs;
   до записи нужен явный expand/compatibility/rollback plan, не скрытый fallback.
3. Миграция с потерями — нет; backfill/удаление/перепись истории запрещены.
4. Отсутствующий предметный источник — конкретного конфликта пока не выявлено;
   отсутствующие общие principles/PDF отмечены, новые нормы не изобретаются.
5. Новый контур артефакта — нет, используем corporate/1.0 и действующие M3/M4/M5/M7.
6. Права/чувствительные данные — не расширяются; неопределённая власть назначения
   блокирует только соответствующее расширение до решения владельца.
7. Откат — revert кода, сохранить аддитивные записи/ответы/consent и frozen snapshots.
8. Выход за область — нет; real-provider smoke требует отдельного допуска и
   изолированных synthetic данных, обычные тесты используют controlled gateway.

## Действия выпуска

`branch_push=true`, `pr=true` — один PR по прямому запросу владельца.
`version_bump=true`: владелец подтвердил единый PATCH-кандидат 2.0.35 для всего PR.
`merge=false`, `deploy=false` до отдельной передачи/человеческого review нового
head и обязательного зелёного CI; старые review PR #122/#123 не переиспользуются.
`artifact_publish=false`; управляющие документы не меняются, baseline не заявляется.

## Минимум проверок до PR

Регрессии до/после по каждому установленному дефекту; lint, frontend tests,
build/reproducible dist/release guard/diff-check; backend unit и HTTP;
PostgreSQL integration только owned test/pytest DB, без developer/shared test DB;
полный synthetic путь U01–U07 без предсозданного M4 и реальных писем.
Browser: mock fault cases отдельно от реального isolated backend; 1440/1280/768/
390/360/320, short height/zoom200, computed styles/geometry/keyboard.
Real LLM отдельно `llm`, не заменяется synthetic PASS. Incident без доступа остаётся
NOT_VERIFIED; platform matrix и визуальная приёмка владельца не присваиваются агентом.
Перед merge frontend/pytest CI exact head/base обязательны.

## Проверки пока

PASS: свежий origin/main, чистый исходный worktree, W01 checksums 11/11.
PASS: `pytest -p no:cacheprovider -q tests/unit/test_public_origin.py
tests/unit/test_test_deploy_bootstrap.py tests/unit/test_frontend_asset_retention.py`
— 39 passed. Отдельно config security defaults + public origin — 21 passed.
Остальной минимум NOT_RUN: реализация и воспроизведение ещё не завершены.

TASK01 адресный прогон после дополнения delivery sink/Host и rollback: `pytest
-p no:cacheprovider -q tests/e2e/test_r03_invitation_http.py
tests/unit/test_auth_public_origin.py tests/unit/test_public_origin.py
tests/unit/test_test_deploy_bootstrap.py` — 58 PASS, exit 0.

На текущем рабочем diff TASK01: backend unit `632 PASS`, HTTP `93 PASS`,
`sh -n scripts/deploy_test_remote.sh` и `git diff --check` PASS (exit 0).
Это промежуточные проверки, не итоговый SHA полного кандидата; TASK02–04,
integration/browser U01–U07 и real-provider ещё NOT_RUN.

### TASK01: конфигурация и совместимость

`APP_ORIGIN_MODE=local|public` сохраняет явно локальный HTTP-контур разработки;
public требует HTTPS DNS origin без credentials/path/query/fragment/IP/localhost.
Публичные URL строятся только из операторской настройки, не из Host/forwarded headers.
TTL, purpose, HMAC/хеш и одноразовость токенов/tenant-проверки не меняются.
Неверный origin отклоняется до записи токена/приглашения.

Чтобы не читать и не переписывать серверный secret `.env`, штатный test deploy
атомарно создаёт отдельный ignored `.public-origin.json` schema 1 через
`scripts/configure_public_origin.py --origin https://test.4k-assistant.ru`.
Он содержит только публичный origin/mode и переопределяет только APP_BASE_URL/mode,
остальные настройки не затрагивает. Повреждённый файл — fail closed, не fallback.
Isolated stand явно игнорирует этот deployment override.

`GET /users/version` в public mode дополнен `public_origin`; в local ответ прежний
(поле None исключено). Deploy сверяет effective origin работающего backend и
сохраняет/восстанавливает прежний public config при rollback. Доставленные письма
не меняются: новая ссылка только через штатный новый запрос/явную повторную отправку.
Live effective-origin и mail sink после будущего deploy ещё NOT_RUN.

## Откат и передача

Рабочие изменения сохраняются только в одной ветке задачи. Аддитивные связи и
ответы после rollback кода не удаляются; начатые Cycle используют прежний snapshot.
Конкретный план схемы/совместимости будет внесён перед соответствующей записью.
Следующий шаг: завершить полный integration/browser минимум, проверки восстановления
и UI, единый bump 2.0.35 и review diff. Затем один PR и CI точного head.
Версия 2.0.35 согласована и присвоена один раз на границе пакета.
Коммит/PR полного результата ещё не созданы, live не изменён.

## Реализация и промежуточная проверка 29.10

- TASK02: `assessment_assignment_sources` — только явные опубликованные config/role
  refs существующего org-admin; student/чужой tenant исключены, после M4 refs frozen.
  Batch operation journal не позволяет повторить ключ с иными участниками/источниками.
  `acquaintance_state_store` архивирует и восстанавливает draft/consent по точному scope.
  Реальные user fields проецируются типизированными read-only объектами; роль не должность.
  Confirm answers сохраняется независимо от наличия M4. Отдельный POST resolve-profile
  связывает сохранённые версии ответов с M4 без глобального выбора/default; повтор
  сериализован user lock. После bound M4 изменённые ответы → 409, identical replay
  не снимает подтверждение. Существенные прежние conflicts не обнуляются.
- Journey/legacy API: обязательные факты consent+3 answers+confirmation проверяются
  сервером; completed/skipped и старый profile/role/start не обходят новый путь.
  Старые действительно unmanaged участники сохраняют прежний API; старые M4/Cycle
  не переписываются. Если историческая confirmation не содержит revision в checksum,
  сохранённая запись не меняется: новая canonical confirmation имеет новый checksum.
- TASK03: W01 chat вместо promo-слайдов: история без старых кнопок, актуальный
  вопрос+поле+действия, вопрос/ответ в сводке, адресная правка до подтверждения,
  back 44×44 вне badge; палитра только owner tokens. Шапка проверяет journey и
  не выбрасывает unsent ввод. Нормативное объяснение берётся из выбранного published
  M2 с checksum, не встроенным словарём; при отсутствии источников — честное ожидание.
- TASK04: confirm немедленно открывает 4К; resolve/prepare/poll идут независимо.
  UUID записывается до POST, серверная операция восстанавливается по scope;
  semantic dedup начальной подготовки исключает transport UUID, но не ключ next AS.
  Смена identity/экрана прекращает только локальное ожидание; worker fencing сохранён.
  Prepared snapshot требует admitted AS; кнопка старта использует тот же Cycle.

Промежуточные результаты (рабочий diff, не финальный SHA):

- `npm run test:backend` — 646 PASS / 256 deselected; предупреждения о TestClient
  и недоступной записи pytest cache, ошибок нет.
- HTTP + M4 regression — 94 PASS. Собственно HTTP — 93, M4 — 1.
- Новые owned participant API + W02 + scope history: 4 PASS; отдельно M4 после
  актуализации минимального fixture — PASS. Ранее очередь/M10/positive path — 17 PASS.
- `node --test tests/frontend/*.test.mjs` — 85 PASS; lint/build PASS.
- Новый `path29-participant.spec.mjs` — 1 PASS / 36.9s: реальные UI анкеты,
  участник и явные sources, controlled HTTPS mail, новая регистрация без готового M4,
  consent/3 answers/адресная правка, failed PUT с сохранением текста, reload,
  4К во время held real worker, две вкладки/один UUID, prepared без started_at,
  явный старт/первая AS в чате. Viewport 1440/1280/768/390/360/320, short+zoom200.
  Owned artifacts: `.test-stand/path29/b26c4e64-c15f-4323-8b9d-da475eca0c67/`.
  Не публиковать state.json (синтетический пароль) или auth URL/cookies.
  Harness не входит в production main: требует isolated marker, owned DB и localhost.

Найдены и исправлены по проверкам: frontend запрещал локальные hex вне owner palette;
старый CSS другого экрана менял направление topbar; тест сравнивал весь текст
queued/running вместо устойчивого operation UUID. Это не provider retry.
Первый полный integration: 167 PASS, 2 FAIL (минимальные fixtures без revision и
ожидание готовности от плана без admitted AS), 2 explicit llm SKIP. Исправлено:
revision добавлена в тестовую схему; plan-only теперь проверяется как NOT READY,
сам snapshot сохраняется и читается через read_plan. Адресный повтор — 12 PASS.
Это не итоговый PASS всего набора: полный повтор перед review обязателен.

Browser: 63 PASS (auth + прежний новый positive), отдельно ADM28 real PASS.
Дополнительно 6 UI fault cases PASS: 403/409/503/network/failed/organization;
network/5xx/409 не анимируют fake preparation и не выдаются за job failure.
Runtime S10-A обнаружил обход штатного lazy-loader при новом прямом старте:
первое сообщение могло опередить инициализацию. Переход переведён на loadInterview;
адресный S10-A до saved Report/PDF — PASS / 1.1m. Unmanaged historical M4/QA
оставлен на прежнем journey, modern assignments не попадают в legacy profile.
Prepared QA snapshot использует явно выбранный QA scope только из guarded test contour.
Новый positive дополнен потерей ответа prepare после настоящего commit и отправкой
первого ответа; финальный полный browser ещё не завершён.

Real-provider smoke NOT_RUN: владелец 29.10 явно разрешил один smoke после штатного
deploy на test, на новых синтетических данных, с текущими моделью и лимитами,
без изменения ключей; при окончательном отказе остановка, дополнительных операций нет.
P0 генерации не закрывается synthetic PASS; визуальная приёмка владельца/маркетолога
и реальная платформенная матрица NOT_RUN. Chromium viewport не равен Safari/iOS/Яндекс.
