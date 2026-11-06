# PATH-HARNESS-R1 — передача кандидата 2.0.70 на PR/CI/review

## Результат

Владелец отдельно подтвердил 2.0.70 PATCH, bump →push →PR →mandatory CI →human
review. [Карточка](../tasks/path-harness-release-2070.md). Merge/deploy/публикация/
активация программы/рабочая БД/платный AC18 не разрешены и не выполняются.
AUTH/R10 2.0.69 закрыт PR174, повторной задачи на его выпуск нет.

Один результат — actual HTTP/PG доказательства AC06/07/09/10 и постоянный harness
с проверенным read-only viewport collector для будущего AC18. Правила приёмки,
методология/M0–M8/admission/repair/prompts/API/схема не менялись. Продуктовых ошибок
в четырёх AC не подтверждено; исправлены два сбоя нового collector при проверке
release-кандидата. Это не приёмка всего PATH и не новый real-provider PASS.

## SHA, применимость и состояния

- Fresh main/base `3f42bba992e1a556e1961ca4abdaa0954a367153` /2.0.69.
- Исходный handoff `2fa1ed667707c8f146951c844b673b79fecd9e08`, source2a868e5,
  отдельная ветка/пакет сохранены. Архив SHA-256
  `0c8459e12b45ac4423c8f41182be8e67318333190feb448dc0fc7befb386d78f` совпал.
- Release branch `codex/path-harness-2070`, версия2.0.70. Source финальных5 browser
  и34 unit checks: `4510aa4b7ac3db87f44cd422862a549d8c72c9a7`.
  Итоговый commit перед PR добавляет только docs/evidence/STATE; exact head/tree
  передаются в PR. Полный CI должен относиться к этому head и актуальному base.
- Source c972a88: версия/build и921 backend/108 HTTP/145 frontend/22 release+CI/
  child18 actual PG. После него менялись только collector/его DOM tests/docs;
  Api/scripts/артефакты/metadata/web сохранены. Runner identity учитывает hash
  collector,12 его тестов повторены в34 на4510aa4. 240 integration исходного
  source2a868e5 применимы к неизменённым Python/SQL bytes, не объявлены новым run.
- Main не изменён. Последнее подтверждённое test —3f42bba/2.0.69,
  [закрытие](https://github.com/VadikB/4K_MBTI/pull/174#issuecomment-6681555673).
  Свежего live server readback нет; новый deploy NOT_RUN.
- Новый CI до создания PR NOT_RUN, человеческое review нового head NOT_DONE.
  После CI статус фиксируется в PR без status-only commit/смены проверенного SHA.
- Три чужих untracked документа корня и другие worktrees сохранены.

## Изменённые файлы

От main: runner code-identity включает viewport helper, actual HTTP/PG/browser
fixtures и регрессии, профиль/README, план AC18, первичное evidence и отчёты.
От handoff2fa1: штатные4 metadata/45 rebuilt assets, viewport helper с тремя
collector-only DOM regressions, release task/report/evidence и актуализация плана.
Api/assessment_definitions/CI/schema не меняются. Необходимость PATCH определяется
существующим release gate из-за scripts/assessment_first_case.py, не новой нормой.

## Источники и решения

Прочитанные пути/версии,8 стоп-условий и флаги — в карточке. Неизменённый контекст
исходного proof переиспользован; источники Change01 И-6 →ADR-003 scoped права,
questionnaire/assignment →actual routes/resolver/PG →31 events/25 no-write.
M1v1.4 FROZEN/CURRENT=NO; синтетический исходный QA — тестовая подстановка, не
human review и не методологический допуск целевого пилота. Закрытый старый audit
не использован как доказательство нынешнего дефекта. PREP-DIAG-01 UNKNOWN отдельно.

## Ожидание →факт →исправление →повтор

| Ожидание / факт | Причина и исправление | Повтор |
| --- | --- | --- |
| Видимый submit после trial / IO ratio0 при сохранённом box в viewport; c972a88 browser1 PASS/1 FAIL | Collector измерял box до trial и дублировал actionability отдельным IO-based assert. Точный механизм callback UNKNOWN. Теперь измерение после trial, реальное пересечение viewport/clipping ancestors +прежние горизонтальные/visible/active/actionability gates | 4510aa4 browser5 PASS; негативные offscreen/clipping/overflow не принимаются |
| Capture admin select / DOM detached на предварительном scroll; ef0cc87 browser3 PASS/1 FAIL | Карточка штатно перерисовалась при ответе questionnaire. У enabled убран лишний scroll, trial сам разрешает актуальный locator и выполняет actionability/scroll без click. Disabled не включается насильно | Actual admin PG/browser PASS и отдельные12 DOM replacements PASS |

Оба отрицательных JSON/PNG/cleanup сохранены в новом evidence. Никаких retries
полного теста ради скрытого PASS, отключения условий или коррекции admission нет.
Это отказы collector, не новые содержательные отказы AS и не причина PREP.

## Команды →фактический результат

Только sterile env: PYTHON_DOTENV_DISABLED=1/PYTHONPATH=./DB_POOL_MIN_SIZE=0;
обычные тесты с DB_NAME=unused/localhost:1, без ключей/mail credentials.
Реальные проверки — новый PostgreSQL16 container tmpfs,localhost65523,
STAND_ADMIN_URL maintenance postgres, TEST_DATABASE_URL agent4k_pytest_harness2070.
Эти URL теперь недействующи: собственный контейнер удалён, не заменять рабочей БД.

| Команда | Факт / source |
| --- | --- |
| `npm run ready:prepare -- --candidate 2.0.70` и повтор | PASS против fresh main3f42bba;4 metadata/45 JS assets SHA-256 identical, без второго bump |
| `npm run lint:js`; `node --test tests/frontend/*.test.mjs` | PASS /145 PASS, c972a88; runtime web после этого тот же |
| `pytest -q tests/unit/test_release_version.py tests/unit/test_ci_verification_workflows.py` |22 PASS, c972a88 |
| `npm run test:backend`; `npm run test:backend:http` |921 PASS/354 deselected (285.93s);108 PASS/12 deselected (155.40s), c972a88 |
| `pytest -q -s --run-integration tests/integration/test_path_admin_contract_owned_stand.py` | outer1 PASS/child18 PASS,102.98s;31 events/25 no-write; c972a88 |
| `pytest -q tests/unit/test_assessment_first_case.py tests/unit/test_release_version.py tests/unit/test_ci_verification_workflows.py` |34 PASS,4.34s,4510aa4 |
| `npx playwright test tests/browser/path-admin-contract.spec.mjs tests/browser/path29-participant.spec.mjs tests/browser/path-viewports.spec.mjs --workers=1` |5 PASS,0 retry/skip/flaky,2.0min,4510aa4; real HTTP/PG и отдельно component-only/DOM |
| Node syntax/diff/release gate, source equality, primary evidence CHECK | PASS; исходные negative/evidence bytes не переписаны |

Первичные [результаты, source hashes и offline CHECK](../evidence/path-harness-release-2070/README.md).
Warnings Starlette/httpx и psycopg_pool open сохранены, не suppress. Python3.12.13,
Node25.5.0/Playwright1.63.0; CI отдельно проверит Linux/Node22/Python3.12.

| AC | Статус и остаток |
| --- | --- |
| AC06 | PASS actual403/no-write, ordinary admin program connect и foreign organization writes |
| AC07 | PASS current revision200/SQL refs/replay; stale и foreign409, foreign URL403/no-write |
| AC09 | PASS real PG same/different-key concurrency, lost delivery/readback и late rollback; browser dblclick1 POST, повтор не создаёт Cycle; component post-start replay1 Cycle |
| AC10 | PASS invalid program/role/scope/questionnaire, предусмотренные отказы без частичных предметных строк; foreign recipient200 item not_assigned по существующему контракту |
| AC18 | NOT_RUN: [план](../tasks/path-ac18-final-plan.md), точный deployed SHA только после отдельного merge/test и отдельного разрешения платного run |

## Риски, безопасность и откат

Конфиг — только номер приложения/build; схема/миграции/данные/права — без изменений.
Ни рабочая .env/БД, ни почта, ни provider не использованы. Синтетические
@example.test/контролируемые fixtures не выданы за реальный human review.
Viewport helper выполняет только bringToFront/resize/scroll/trial/read/screenshot,
не start/answer/generation. Actual full PATH по-прежнему проверяет stages,
финальную admitted AS/lineage/exact org+program/profile/time/start и0 answers;
component-only успешный resolver для AC06–10 не применялся.

Все7 owned test БД удалены штатно после export;0 owned DB/0 connections readback,
точный container ID/label проверен, stop+rm без FORCE. Удалены только временные
synthetic test данные, восстанавливать их не требуется; evidence сохранено.
Неизменяемый исходный пакет и чужая работа сохранены. Откат до merge — revert
только release commits; сохранённых данных/миграции нет. Baseline не присваивается.

## Следующий минимальный шаг / открытые gates

Агент: завершить final diff/check/preflight, commit/push/Ready PR и дождаться
mandatory frontend/pytest/full-verification exact head/base. Владелец: review
нового кода collector/регрессий и исходного actual PG proof. Это новый review,
не ранее принятый AUTH/R10. Merge/test требуют отдельного прямого разрешения;
после deploy/readback — отдельно один AC18. Публикация программы не требуется.
