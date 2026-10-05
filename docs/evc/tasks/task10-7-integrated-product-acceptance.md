# 10.7 — интегрированная приёмка M1–M8

## План и границы

Техническая проверка завершена; ожидается CI/передача. База пула `80505e0eeb2ee73fbd719ca4578d09812db9c5d9`, main после fetch
`8654b97ed6605d560111c37cd291f98f82c41457`. Ветка `codex/task10-7-integrated-product-acceptance`.
Пул включает REV-01–04, 10.4, 10.5, 11.2, 10.6, 8.1; сохраняет 11.1/10.2/10.3.

1. Разведка и независимые ожидания: выполнено для основной браузерной трассы.
2. Выполнено: новая G01–03/06 browser трасса с read-only SQL отсутствия выходов до действий.
3. Выполнено: шесть прежних сценариев, общий backend/HTTP/DB/frontend/lint/build, два независимых bootstrap.
4. Выполнено: матрица G01–13, реестр и пакет решений.
5. Активный шаг: передача PR и CI. Код зафиксирован `7a5776b688fae63268ad0a54eef96bf8f95aa835`, свежий manifest переснят на нём. Merge/deploy не входят.

## Источники и решения

Прочитано задание [request](artifacts/task10-7/request.txt), EVC workflow, verification matrix,
CONTRIBUTING, browser README, runtime.spec.mjs, seed/stand/inspection, интеграционные контракты 8.1.
Повторно используется прочитанный контекст README, artifact recipe, архитектурные context/Registry,
Change 01, ADR002 и M1 v1.4/M2/M5/M6/M7/M8 из задачи 8.1; версии/хеши будут пересняты.
M1 FROZEN/CURRENT=NO; технический допуск не утверждает методологию.

CI базы 8.1 PASS: https://github.com/VadikB/4K_MBTI/actions/runs/37360758620
(80505e0; frontend, pytest включая browser; deploy-test не выполнялся).
Не приписывается будущему дереву 10.7.

Нормативные defaults, FROZEN и история не меняются. Только принадлежащие запуску БД.
Не предоставлены утверждённые GC/заключения или лимит real-provider: зависимые критерии
останутся NOT_RUN/BLOCKED; это не блокирует техническую проверку. Рабочий каталог/развёрнутый
test без разрешённого конфигурационного доступа — NOT_VERIFIED.

## Проверки и передача

На неизменном коде `7a5776b`: unit 362, HTTP 40, integration 92, frontend 4, browser 11 PASS; lint/build/diff PASS. Отдельно focused browser 1 и numeric 5 PASS. Логи — artifacts/task10-7; CI пока pending.
Откат: отменить коммиты 10.7; никаких миграций и массового пересчёта истории.

## Матрица общей приёмки (обновляется до передачи)

| Критерий | Статус | Доказательство и граница |
|---|---|---|
| G10.7-01 | PASS | Новый browser `G10.7`: read-only отсутствие UserContext/M4 и выходов, UI confirm/role, реальный start/dialogue/clarification/workers/admission/Report/PDF. `browser/G01-empty-owner-inputs-and-all-outputs-1.json`, `G01-03-receipts-1.json`. Только AI transport синтетический. |
| G10.7-02 | PASS | Реальный logout, clearCookies/localStorage/sessionStorage, новый login; тот же JSON/revision, PDF проверен по содержимому; SQL output counts/refs не изменились. Legacy-сессии для истории не создаются. |
| G10.7-03 | PASS | Новый независимый Cycle и Results; две карточки; повтор regenerate key отдаёт ту же новую revision первого Report; исходный Results и прежний Report неизменны. Изменённый M4 для следующего Cycle дополнительно проверен owned-stand integration 10.5. |
| G10.7-04 | PASS | Повтор всех шести 10.3: A/T11, B, C1, C2, Recovery, synthetic character. `browser-summary.json`. C1 — реальная visibility hidden; C2 — прежний pause/deadline сценарий, не утверждается физическое закрытие ОС/браузерного процесса. |
| G10.7-05 | PASS | `test_profile_access_owned_stand`, `test_profile_to_m4_owned_stand`, owner history/report integration: anonymous/owner/same org/other tenant, отказ и отсутствие изменений; смена org/config не переиспользует старый M4. Browser owner/account switch повторён. HTTP TestClient части набора не утверждается сетевым browser-доказательством. |
| G10.7-06 | PASS | G01 real M4→Results→nonempty projection→application_context UI/C67/PDF; `test_m8_recommendations` empty/partial/identity filtering; owned-stand 10.5 изменение профиля после Cycle не меняет исторический snapshot/регенерацию. Экспертная полезность отдельно не принята. |
| G10.7-07 | PASS (технический) | A/T11 positive и IE перед L1, basis refs, три типа только при допустимом основании; unit justified L0; real DB `test_r11_history_regeneration_failure_and_real_http` отделяет отсутствие основания/ошибку и фильтрует старый неподтверждённый C67. Нормативная оценка рекомендаций не выводится. |
| G10.7-08 | BLOCKED (содержательная приёмка) | Saved chain admission/individual/joint failure/not_comparable/no IA→C56/C67/PDF проверены 8.1 DB. Вариативность L1/L3 — unit. E01–E05 пока не выполнены как независимый содержательный eval на полном наборе сохранённых контрпримеров: scripted decisions не доказывают смысл. Ожидания/условия/нужные ответы — `owner-decisions.md` и независимые ожидания 8.1. Не подменяется техническим PASS. |
| G10.7-09 | PASS (расчёт/передача) | Новый `test_integrated_acceptance_db`: пять saved QA цепочек, четыре исхода + full_score=0; PostgreSQL→C56→Results→C67→HTTP/PDF (actor fixture; настоящий auth отдельно G01/G05). Независимая формула 7/4 и 3/2 по M2 grouping/M6 равным весам; denominator=3 сохраняется. QA decisions заданы явно, это не admission oracle. Unit guards duplicate AS/revision; G03 отсутствие удвоения Cycle. |
| G10.7-10 | PASS (технический) | Recovery/lost response/two tabs и смена пользователя browser; реальные DB worker timeout/lease/process exit/retry; no fabricated assessment после сбоя. Новый DB тест запрещает admission/generate при GET/PDF готового отчёта; исторические fingerprints не меняются. Реальная недоступность внешнего provider не вызывалась. |
| G10.7-11 | BLOCKED / NOT_VERIFIED на test | Read-only Git inventory выполнен: пять WORKING v0.1, роли/цели/open decisions. Нет подтверждения рабочего каталога/QA и конфигурационного доступа к развёрнутому test. FROZEN copies не считаются допуском; CASE04 остаётся закрыт. |
| G10.7-12 | NOT_RUN | Нет согласованных provider/model/лимита затрат для этого пула. Секреты не искались; нужны перечисленные в `owner-decisions.md` доступы/решения. |
| G10.7-13 | В работе | Локальные unit 362, HTTP 40, frontend 4, lint/build, browser 11 и focused numeric 5 PASS. Общий integration 92 PASS; CI точного head ожидается. |

Ссылки артефактов в таблице относительно [каталога доказательств](artifacts/task10-7/).

## Исправления и результаты разведки

Продакшен-код, API, схема, prompts, правила и UI не менялись: новых технических
дефектов на обязательном пути пока не выявлено. Исправлен пробел доказательств:
до G01 проверяются все оценочные выходы, а четыре исхода передаются через реальное
хранение/HTTP/PDF. Числовой fixture — отдельный CASE-G107-NUMBERS/synthetic-v1 в QA;
исходный CASE-TDISC-01 и остальные WORKING остаются неизменными.

В ходе построения fixture пойманы его ошибки: applicability/passport не совпадали
с целями; исправлена согласованность до импорта. Первый draft ожидания ошибочно
считал три компонента K1.3. Сверка M2 показывает C06={I12}, C07={I13,I14};
по M6 равным весам правильное независимое ожидание (1+(2+3)/2)/2=1.75.
Алгоритм не менялся, защитные проверки не отключались. История не переписывалась.

Известное ограничение прежнего REV-02 mixed legacy test: два legacy HTTP-ответа
подменены только для проверки маршрутизации старого экрана; schema gap
`competency_skill_id` на чистом bootstrap остаётся отдельно. Новый G10.7 не содержит
этой подмены и не использует legacy Reports. Полная очистка legacy и новый UX вне задания.
Текущий UI технически показывает данные, но рекомендации/ограничения дают длинную
страницу; это не полная UX-приёмка. PDF G01 — 7 страниц, текстовая проверка всех
проверяемых полей PASS; визуально просмотрены страницы 1 и 7, не весь нормативный набор.

## Предметные решения, пилот и развёрнутый test

| Область | Итог |
|---|---|
| Технический пользовательский путь | PASS на synthetic AI, реальном runtime/HTTP/DB/workers; готов к техническому review |
| Real-provider | NOT_RUN |
| Рабочий каталог | Допуск не подтверждён; локальные исходники WORKING, deployed DB NOT_VERIFIED |
| Предметный admission | Ожидания E01–E05 и полная saved-input eval не приняты; BLOCKED |
| Экспертный просмотр рекомендаций | NOT_RUN, заключение эксперта отсутствует |
| Approved GC / нормативная Reliability | Не представлены; `not_verified` сохраняется |
| CI кандидата | Ожидается, база 8.1 не подменяет текущий запуск |
| Развёрнутый test | NOT_VERIFIED для этого пула; main всё ещё 8654b97e, merge/deploy 10.7 не выполнялись |

Владелец может принимать технический путь и набор воспроизводимых проверок после
финального CI/review. Допуск пилота требует рабочих case/QA, решения admission,
экспертного просмотра, протокола GC/Reliability и проверки реального provider с лимитом.
Порядок: review пула → предметные решения и каталог → разрешённый provider-eval →
обязательный CI/решение выпуска → отдельные merge/deploy и приёмка test → пилот.
Новому UX/UI нужна отдельная приёмка после его реализации.

## Изменённые файлы и риски

- `tests/browser/runtime.spec.mjs`, browser README: новая интегрированная трасса, старые сохранены.
- `scripts/inspect_profile_browser.py`: read-only counts в owned stand, без материалов/секретов.
- `tests/integration/test_m6_evidence_db.py`: явный opt-in отдельного synthetic case для numeric tests; default fixture не меняется.
- `tests/integration/test_integrated_acceptance_db.py`, `tests/fixtures/integrated_acceptance/`: сохранённые исходы и AI-independent read.
- `scripts/integrated_acceptance_manifest.py`: хеши существующих файлов, версии среды, режимы AI; отсутствующие файлы не попадают в manifest.
- Этот отчёт и `artifacts/task10-7/`: задание, sources, реестр, решения, безопасные логи, Report/PDF/screenshots.

Конфиг/схема/deploy/права: изменений нет. Тесты используют owned lifecycle 10.2,
исторические реальные данные не читаются. Отчёты/имена в артефактах синтетические.
State/password/cookies/auth trace не включены. Откат — revert коммитов 10.7;
схема и история не требуют восстановления. Более ранний пул сохраняется.
Управляющие документы не менялись; делегирования не было; baseline не присвоен.


## Команды → фактические результаты

Все команды из worktree `.worktrees/independent-review-remediation`. Файлы кода/тестов
соответствуют `7a5776b688fae63268ad0a54eef96bf8f95aa835`; последующие правки отчёта
не меняют проверенное поведение. Полный runtime/test manifest — `candidate-manifest.json`.

| Команда | Результат / exit |
|---|---|
| `npm run test:backend` | 362 PASS / 0 |
| `npm run test:backend:http` | 40 PASS / 0 |
| `TEST_DATABASE_URL=<owned DB> STAND_ADMIN_URL=<local maintenance> npm run test:backend:integration` | 92 PASS / 0, включая два empty bootstrap/seed/restart |
| `node --test tests/frontend/*.test.mjs` | 4 PASS / 0 |
| `npm run lint:js` | PASS / 0 |
| `npm run build:web`; `git diff -- web/dist` | PASS / 0, сборка совпадает с Git |
| `STAND_ADMIN_URL=<local maintenance> npm run test:browser` | 11 PASS / 0, retries=0 |
| `npm run test:browser -- --grep G10.7` (owned env) | 1 PASS / 0 |
| `.venv/bin/python -m pytest --run-integration -q tests/integration/test_integrated_acceptance_db.py` (owned env) | 5 PASS / 0 |
| `git diff --check`, report relative links, artifact JSON | PASS / 0 |
| `.venv/bin/python scripts/integrated_acceptance_manifest.py --output docs/evc/tasks/artifacts/task10-7/candidate-manifest.json` | PASS, только существующие файлы |

Локальная среда: Python 3.12.13, Node v25.5.0, Playwright 1.63.0 / Chromium
153.0.8010.12, PostgreSQL 15.16, Typst Python/compiler package 0.14.9.
CI использует собственные версии (Python 3.12, PostgreSQL 16); не подменяет локальный
manifest. AI modes отражены в manifest; Recommendations deterministic.
Первый Chromium-запуск в sandbox завершился Permission denied до сценария;
повтор с разрешённым запуском прошёл. Это инфраструктурный неуспех, не скрытый retry.
Локальные одноразовые БД удалены штатным `test_stand.py destroy`; shared test не использован.

## Review и следующий шаг

Проведено собственное ревью по EVC: runtime/API/схема/FROZEN не изменены,
новые fixtures не подменяют нормативные ожидания; отрицательные сценарии сохранены,
артефакты содержат только synthetic данные. Подтверждены ссылки и JSON, snapshot/code diff.
Независимое человеческое review не выполнено агентом. Следующий шаг — CI и review PR;
для предметных блокеров нужны ответы из owner-decisions.md, без повторного решения
уже согласованных технических деталей.
