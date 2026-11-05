# PATH-AC02/05 — оставшаяся бесплатная browser-матрица

## Основание, результат и границы

06.11.2026 владелец после завершённого выпуска2.0.67 попросил «идем дальше по
списку задач». Продолжаются два явно сохранённых пробела PATH1.3: AC02 повтор
создания организации и AC05 slow/error GET подключения. База нового чистого
worktree — `bb3b5cb34696af8a8a2bdaa1999dd8a795786085` /2.0.67,
ветка `codex/path-ac02-ac05-coverage`. Три посторонних untracked файла main сохранены.

Завершение предшествующего выпуска: [PR172 / EVC closure](https://github.com/VadikB/4K_MBTI/pull/172#issuecomment-6670022536).
Head463e7e2 принят человеком, squash bb3b5cb имеет то же дерево4565dbf0,
обязательный CI и deploy-test PASS; отдельный server/public readback exact SHA,
версия2.0.67 и45 assets+HTML PASS. Старые pre-PR WAITING в карточках — история,
не новый блокер. Это не приёмка всех18 AC и не EVC baseline.

## Источники и прослеживаемость

Прочитаны относящиеся AC02/05 и раздел исполнения PATH-START-01 редакции1.3
из `P4K_PATH_START_01_Assignment_to_First_Case_2026-11-04.txt` (Downloads),
`path-final-acceptance.md`, `pilot-1.2-path.md`, STATE, browser README/config,
`auth-r03.spec.mjs` R10/foreign/recovery/helpers, `organizations.js` create/connect/
readback/status/render, `api.js::fetchWithDeadline`, `wiring.js` handlers,
`Api/routes.py::create_admin_organization`, действующий full-verification workflow.
README/CONTRIBUTING/EVC workflow/matrix/review, architecture context/Registry,
M1v1.4 FROZEN/CURRENT=NO, Change01/manifest и artifact recipe предыдущего
неизменённого шага переиспользованы. Документ задания задаёт критерии, но не
расширяет более поздние разрешения владельца на платные операции/публикации.

Связь: PATH1.3 AC02/05 → PS-01 UI/точные organization+program refs →
entry/dist/wiring → create/connect/readback → browser regression.
409 уникального code — существующий серверный контракт; не вводится новая
идемпотентность. UI/HTTP с явными synthetic ответами не выдаётся за PostgreSQL
или новый real-provider PATH. Исторический PREP-DIAG-01 остаётся UNKNOWN отдельно.

## План и проверки

1. На неизменённом продукте добавить stateful synthetic HTTP browser проверки
   создания/reload/повтора409 и потери ответа, медленного и отказавшего GET
   подключения при confirmed/lost PUT. Настоящие HTML/entry/dist и15s deadline;
   не ускорять таймер, не подменять fetch/DOM/предметные gates.
2. Сохранить before JSON/первый разрыв. Только подтверждённый дефект выбранного
   пути исправить узко и повторить регрессии; нехватка теста сама по себе не дефект.
3. Выполнить applicable EVC: полный auth/admin browser, frontend, lint, build,
   diff/локальные ссылки; при продуктовой правке — before/after и узкий rollback.
   Неизменённый backend/SQL/LLM переиспользовать только в прежней области.
4. Обновить AC-матрицу/STATE, сохранить команды/results/hashes и рабочий commit.
   Новый PR/версия/CI/review/merge/deploy — отдельный gate, сейчас не запускать.

## Стоп-условия и риски

Все8 категорий — нет для данного scope: смысл/PM/API/схема/источники/новый контур/
потери/чувствительные данные не меняются; используются прежние технические fixtures.
Публикация, активация программы, рабочая БД, новая генерация и управляющие документы
исключены. При обнаружении иной требующей решения границы остановить только её.
Откат — удалить только новую тестовую/документальную дельту, при подтверждённом
UI fix — revert его source/dist; данные и published определения не затрагиваются.

Флаги: branch_push=false, pr=false, merge=false, deploy=false, version_bump=false,
artifact_publish=false, program_activation=false, paid_llm_run=false,
working_database_access=false. Исходный активный шаг — новые before browser tests;
актуальное завершение и следующий gate ниже.
Полные AC02/05/PATH пока не объявляются закрытыми. Main/test — bb3b5cb /2.0.67;
нового CI текущей ветки нет. Зависимостей от нового платного прогона для этих тестов нет.

## Установленные факты и исправление

`PATH-AC05-UNVERIFIED-DISCONNECTED`: после сохранённого PUT и отказа GET либо
потерянного ответа PUT+отказа GET продукт показывал error, но одновременно
«Программа ещё не подключена». Ожидали честный UNKNOWN, без ложного отрицания
связи. Чистые before: AC02 **3 PASS**, AC05 HTTP503 **2 FAIL** на неизменённом
bb3b5cb UI; source checksum `fbe338670d02dafc24708327a68e001f93076d66ce68a8fc5c6ebc57f1ddabad`.
Полная исходная fault-матрица также дала12 AC05 FAIL;3 иных FAIL в том смешанном
прогоне относятся к ещё неполному reload-fixture, не дефекту продукта.

Узкий fix в `organizations.js`: scoped unverified state относится к identity/org,
ставится до команды, очищается только после exact organization+program readback,
на смене аккаунта/потере доступа. Существующие command/normal/recovery guards и
operation_id сохраняются. Форма и проекции назначения больше не заявляют
«не подключена» при непроверенном результате; локальное назначение остаётся
заблокированным до проверки. Значения серверной связи/ролей/анкеты не подменяются;
server API, опубликованные артефакты и gates AS/плана/профиля/времени неизменны.
Пересобран dist, APP_RELEASE пока2.0.67: это рабочая дельта, не новый выпуск.

Регрессии:3 stateful AC02 browser (success/lost response/503 до сохранения,
keyboard repeat/409/reload);12 AC05 (confirmed/lost PUT × deadline15s/503/network/
invalid JSON/null/foreign program), прежние2 foreign organization. Адресно
**17 PASS**,52.1s, retries0; same operation_id, finite error→success→reload,
неопределённость сохраняется при reopen. Четыре widths1440/320/390/768 и PNG;
визуально просмотрены1440/320, существенное действие/пояснение доступны.

AC02 дополнен2 integration HTTP/SQL: реальный `create_admin_organization`,
commit/rollback/GET и exact DDL `organizations`/tombstones из Api/database.py;
auth и list projection явно synthetic. Повтор обычного и нормализованного code
даёт409, оставляет исходные id/name, одна строка видна отдельной транзакции;
последующая другая организация создаётся. **2 PASS**,3.82s, не новый full PATH.
Только новый локальный контейнер `4k-path-ac02-ac05-pytest-20261106`, DB
`product4k_pytest_ac02_ac05` на127.0.0.1:55439, owner labels; перед cleanup
сохранён вывод2 PASS/owner и0 оставшихся owned schemas. Контейнер1a8c236d…
штатно остановлен и удалён с собственным anonymous volume, без FORCE/host mounts;
readback отсутствия PASS. Остальные контейнеры и рабочая БД не затронуты.

## Сбои проверки, не переименованные в PASS

- Первый запуск:2 fixture FAIL/1 interrupted/14 not run. Неправильный `isVisible`
  сразу после reload, затем обнаружен отсутствующий synthetic session-bootstrap
  ответ. Исправлены только fixtures/ожидание реального экрана; negative JSON/PNG
  сохранены. Следующий чистый before AC02=3 PASS, продуктовый AC05=2 FAIL отдельно.
- Первый baseline auth launcher завершился до browser с MODULE_NOT_FOUND: в
  прежнем worktree отсутствовала локальная ссылка на имеющиеся Node dependencies.
  Сохранён stderr; добавлена только эта ссылка, tracked baseline не менялся.
  После проверок временные symlinks удалены, их targets/зависимости сохранены.
- Полный новый auth/admin набор: **114 PASS/1 FAIL**,136.215s. Старый R03 auth
  test ожидал «Сессия входа не сохранилась», получил пустое поле ошибки. Его
  source и auth runtime неизменны; на чистом дереве4565dbf0 отдельно5 PASS,
  на текущем UI отдельно5 PASS. Причина единичного сбоя **не установлена**;
  это не доказанный предсуществующий дефект и не доказанная регрессия AC05.
  Исходные JSON/log/PNG сохранены; разрешён один полный контрольный повтор
  неизменённого кода/теста после этого сравнения, не случайный подбор LLM PASS.

Свежие lint/frontend140/HTTP+M3 25/build-idempotency/diff/source hashes PASS.
HTTP-набор использовал sterile env/DB sentinel port9, integration — только свою
pytest БД; .env/секреты не читались, provider0. Существующий httpx deprecation
warning сохранён. Исторический paid PATH e63 не объявлен новым для этого UI.

## Итоговая проверка и передача

Контрольный полный `auth-r03.spec.mjs` — **115 PASS**, retries0, skipped0,
exit0; первый114/1 сохраняется отдельно с UNKNOWN причиной. Это успешный
контроль неизменённого кода, не доказательство устранения того единичного auth-сбоя.
Три операционные ошибки запуска/fixtures и два before FAIL одного UI defect не скрыты.
Staged diff-check выявил whitespace в сырых stdout/error-context; они сжаты без
потерь в gzip, а не нормализованы/исключены из проверки. Затем staged check повторён.
Новые PNG, автоматически записываемые старым тестом в adm-status-01, сохранены
отдельно в текущем evidence; исторические два PNG восстановлены из bb3b5cb,
их исходные байты не переизданы под прежними именами.

| Требование | Реализация и выполненная проверка | Evidence / остаток |
| --- | --- | --- |
| AC02 repeat/create/reload |3 stateful browser PASS +2 real HTTP/PG PASS; UNIQUE и rollback реального handler/DDL |`clean-before.json`, `ac02-integration.txt`, `ac02-result.png`; auth/list projection SQL-теста synthetic, не новый полный E2E |
| AC05 finite/unknown/retry |12 новых fault combinations PASS +2 прежних foreign-org PASS; exact refs, тот же operation_id,15s deadline без подмены времени |`mixed-before.json`, `clean-before.json`2 FAIL → `after-selection.json`17 PASS; полный `browser-full-control.json`115 PASS; не реальные сбои постоянного сервера |
| AC05 responsive |4 widths assertions/PNG, visual1440/320; действие и UNKNOWN читаемы |`ac05-unknown-*.png`; платная генерация не повторялась |
| AS/профиль/план/время/нормы |Runtime backend/Api/scripts/assessment_definitions не менялись; HTTP+M3 25 PASS, отсутствие source drift |Исторические SQL/real-provider evidence применимы только в их границах, не новая генерация |
| AC18 общий набор/сдача |115 browser/140 frontend/25 HTTP+M3/2 integration,lint/build45/idempotency/diff PASS;50 code+asset hashes |Новый mandatory CI/human review/deployed acceptance ещё NOT_RUN; все18 AC не принимаются автоматически |
| Ownership/cleanup |Новая отдельная pytest-БД,0 owned schemas после tests, exact owner/container readback и штатная очистка |`container-owner.txt`, `owned-schemas-after-tests.txt`, `container-after-cleanup.txt`; постоянная БД не использовалась |

Для остальных AC действует [полная историческая матрица](pilot-1.2-path.md#сопоставление-исходных-ac0118-без-расширения-результатов)
и [предыдущий бесплатный аудит](path-final-acceptance.md#что-именно-дополнено-к-исходным-ac).
Новые доказательства дополняют их, не превращают39 planned целей в наблюдённые и
не превращают component HTTP в полный real-provider PATH. PREP-DIAG-01 UNKNOWN
не смешивается с новым UI defect или единичным auth assertion failure.

Первичные данные и команды — [evidence README](../evidence/path-ac02-ac05/README.md).
Критерии не ослаблены, retries0, новые prompts/admission/repair отсутствуют.
Рабочий commit/diff/bundle указываются в передаваемом пакете; версия в этой рабочей
дельте остаётся2.0.67 и не выдаётся за новую test сборку. Main/test — bb3b5cb2.0.67,
обязательный CI/развёртывание того выпуска PASS; для новой ветки CI/PR отсутствуют.

Следующий минимальный шаг: решение владельца о выпуске новой UI дельты
(предлагаемый PATCH2.0.68 при неизменном main2.0.67), затем штатный preflight,
кандидат/PR/CI/human review. Сейчас версия не назначена; push/PR/merge/deploy не
выполнялись. После будущего review merge/test требуют отдельного разрешения.
Исторический paid run использован; новый LLM/активация/публикация не входят.
Саморевью агента: исправлен только confidence state PS-01, новые regression и
доказательства соответствуют двум оставшимся пробелам; это не человеческая приёмка.
