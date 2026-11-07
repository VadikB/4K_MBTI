# Тесты backend

## Бесплатная регрессия готовности auth-формы AC18

```sh
npx playwright test tests/browser/auth-r03.spec.mjs \
  --grep 'AC18 auth readiness|AC18 failure capture' --workers=1
```

Удерживается synthetic confirm/reset HTTP response: форма скрыта/disabled до
валидации, затем штатный step2; отказ и network retry проверяются отдельно.
Это UI component, не real PostgreSQL/PATH/LLM. PATH29 использует exact-email
semantic-ready helper; failure capture сохраняет active actor/page и allowlisted
context, маскирует password/token inputs, не экспортирует значения query/credentials.
Результаты/границы: [AC18-AUTH-READY-01](../docs/evc/reports/ac18-auth-readiness.md).

## Модель из provider contract, не из env

`DEEPSEEK_MODEL` не выбирает модель и не обязателен для runner. `.env` — только
credentials/инфраструктура; существующая переменная игнорируется без правки файла.
Новая operation использует выбранный provider contract, сохранённая — свой snapshot.
Preflight фиксирует model/source/version/checksum, не значение legacy env и не ключи.
Нет обязательного контракта — BLOCKED, даже при наличии env-модели.

```sh
PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 .venv/bin/python -m pytest -q \
  tests/unit/test_provider_model_ownership.py tests/unit/test_deepseek_provider_contract.py \
  tests/unit/test_assessment_first_case.py tests/unit/test_test_stand.py
```

Это offline unit-проверки: synthetic transport/port probes не заменяют actual machine,
PostgreSQL или real-provider PATH. Свежие subprocess не читают developer `.env`,
не открывают БД и не вызывают LLM. Source selectors/admission/cleanup не ослабляются.

## Бесплатные AC06/AC07/AC09/AC10

Новая собственная localhost PostgreSQL16, без `.env`, почты и LLM. Задать
`STAND_ADMIN_URL` (maintenance `postgres`) и `TEST_DATABASE_URL` (другая изолированная
test/pytest БД, не DB_NAME) только этого экземпляра. Команды из корня checkout:

```sh
PYTHON_DOTENV_DISABLED=1 PYTHONPATH=. .venv/bin/python -m pytest -q -s \
  --run-integration tests/integration/test_path_admin_contract_owned_stand.py
BROWSER_PYTHON=.venv/bin/python npx playwright test \
  tests/browser/path-admin-contract.spec.mjs --workers=1
```

Wrapper создаёт новую marker-owned БД, выполняет существующий bootstrap/seed,
запускает 18 actual HTTP/PG checks и сохраняет evidence **до** cleanup. Для выгрузки
задать `PATH_ADMIN_EVIDENCE_DIRECTORY=/absolute/owned/evidence`.
Browser имеет отдельные настоящие contexts/sessions и PostgreSQL; transport abort
происходит только после `route.fetch()`/commit, fake success отсутствует.
Его экспорт — `PATH_ADMIN_BROWSER_EVIDENCE=/absolute/owned/evidence` либо `.test-stand`.
Ни Connection, ни успешные resolver/readiness/authorization не подменяются.
E10.2 Case QA — **синтетическая техническая подстановка**, не настоящий human review
и не допуск целевой пилотной программы. AS/LLM в этих admin checks не запускаются.
Не прикладывать `state.json`, session cookies, generated passwords или auth trace.
Отдельный PATH29 component-test с viewport collector остаётся component-only;
его upstream plan fixture запрещён для real/full PATH.

Постоянный синтетический контур «суперадмин → первый Case» и его текущие границы
описаны в [`docs/evc/assessment-first-case-profile.md`](../docs/evc/assessment-first-case-profile.md).

Для отдельно согласованного целевого PATH существующий runner принимает
`--program-source published-pilot` (точный опубликованный nine-case release).
`--check-bootstrap` проверяет минимальные источники/ownership/cleanup без LLM.
Default `functional-diagnostic` остаётся исторической synthetic QA подстановкой,
не доказательством допуска пилота. История PATH, включая прежний содержательный
отказ PM-03: [передача/AC-матрица](../docs/evc/tasks/path-start-01.md).

Уточнение 05.11.2026: на main 2dc98c6 / 2.0.64 единственный разрешённый real run
получил admission PASS, но остановился **до start** на `PLAN_NOT_READY` (LIMITED).
Это не полный PATH PASS и не доказанный отказ HTTP start. Разбор контракта и
бесплатная доработка collector — [PATH-PLAN-01](../docs/evc/tasks/path-plan-diagnostics.md).

Проект ограниченного пилота PATH-PILOT-01 v0.1 принят отдельно по exact checksum:
[запись P1–P3/M1–M4](../docs/evc/evidence/path-pilot-owner-decision-2026-11-05.json).
Последующая локальная реализация принятого T1 —
[PATH-PILOT-02](../docs/evc/tasks/path-pilot-start-admission.md),
[контракт](../docs/architecture/pilot-plan-start-admission-contract.md).
Полный M2=61 сохраняется, план=39/22 вне; любой LIMITED автоматически не допускается.
Runner требует `m7_start_readiness/1` и exact frozen binding, обязательные стадии,
конечную допущенную AS и lineage. Прежний release fixture1.1 не заменён.
Код T1 выпущен в2.0.65 (PR170), harness — main/test e63eba6 /2.0.66 (PR171).
После отдельного разрешения опубликована только новая `specialist_pilot@1.2`, id2,
без подключений организаций;
[exact receipt/readback](../docs/evc/evidence/pilot-program-publication-execution/publication-result.json).
После отдельного разрешения один paid PATH1.2 выполнен: **PASS**, real LLM + штатный
repair, explicit start201/та же первая AS/0 ответов, owned cleanup и offline CHECK PASS.
[Итог](../docs/evc/tasks/pilot-1.2-path.md). Разрешение этого run использовано;
публикация или прежний PASS не разрешают автоматический повтор.
Исторический PREP-DIAG-01 остаётся UNKNOWN и не отождествляется с покрытием.

Harness теперь допускает явный внешний published receipt только полным selector
`--program-receipt /absolute/file.json --program-receipt-sha256 <bytes_sha256>
--program-version <exact_version>` вместе с `--program-source published-pilot`.
Legacy default1.1 сохранён побайтово, latest/fallback нет; proposed draft не является
receipt публикации. Подробности в [профиле](../docs/evc/assessment-first-case-profile.md),
реализация/проверки — [PATH-PILOT-HARNESS-01](../docs/evc/tasks/pilot-program-harness.md).
Saved exact bytes и program refs перепроверяются после cleanup в summary.
Согласование нового selector не разрешает publication/активацию/paid run.

Actual published receipt1.2 проверен существующим `--check-bootstrap` на test
e63eba6 /2.0.66: **PASS_BOOTSTRAP_ONLY**, новая owned-БД и marker-guarded cleanup,
минимальные counts1/0,9 Cases/27 исходных QA, LLM0.
[Первичные evidence](../docs/evc/evidence/pilot-program-1.2-bootstrap/remote-result.json).
Команда из repo root требует `PYTHONPATH=.`; это исправлено в профиле. Bootstrap
не доказывает новый human review/качество AS, first start или полный PATH.

Бесплатные SQL-регрессии самого release seed:

```sh
# Только собственный localhost PostgreSQL, maintenance URL и отдельная test/pytest reference DB:
.venv/bin/python -m pytest -q --run-integration tests/integration/test_published_release_seed_db.py
```

Нужны одновременно `STAND_ADMIN_URL` и `TEST_DATABASE_URL` одного изолированного
PostgreSQL. Тест создаёт/удаляет новые owned-БД, проверяет минимальную загрузку и
неизменность исходных27 Case QA. Метаданные будущей программы — явная SYNTHETIC
подстановка, не реальная публикация или новый human review. Provider disabled.

Бесплатные проверки нового контракта:

```bash
.venv/bin/python -m pytest -q tests/unit/test_pilot_plan_admission.py tests/unit/test_assessment_start_readiness.py
# Только собственная изолированная test/pytest БД; ключи LLM пусты:
.venv/bin/python -m pytest --run-integration -m 'integration and not llm' tests/integration/test_pilot_start_admission_db.py
```

SQL suite использует **синтетические** записи принятия плана и LLM-стадий. Она
проверяет настоящий серверный gate/start/AS/time, но не новый human review или
качество генерации. Для полного integration нужны `TEST_DATABASE_URL` и отдельный
`STAND_ADMIN_URL` на maintenance `postgres` того же owned PostgreSQL; рабочая БД
из серверного `.env` никогда не является автотестовой БД.

Старые статические browser component-сценарии после нового first-start gate
используют отдельную **явную синтетическую upstream plan-policy подстановку**,
не допуск программы: [границы/guards и реальный negative browser gate](browser/README.md).
Они не заменяют положительную SQL/HTTP проверку пилотного контракта или будущий
разрешённый paid PATH. В real-provider/full-PATH эта подстановка запрещена.

Бесплатные адресные проверки harness (без БД, credentials и LLM):

```bash
.venv/bin/python -m pytest -q tests/unit/test_assessment_first_case.py tests/unit/test_test_stand.py tests/unit/test_assessment_run_summary.py tests/unit/test_assessment_plan_receipt.py
node --test tests/unit/test_assessment_receipt_file.mjs tests/unit/test_assessment_preparation_receipt.mjs
```

`first-case-success.json` — явно синтетическая техническая подстановка для
validator/unit-тестов. Она не доказывает продуктовый LLM PASS, human review или
допуск программы. Проверяется настоящий общий browser/summary validator, а не его
копия. INCOMPLETE/FAIL и недопущенная AS не принимаются; PASS_WITH_WARNINGS
принимается только с `admitted_for_participant=true` и всеми обязательными связями.

Тесты разделены по уровню:

- `unit` — быстрые проверки без PostgreSQL, HTTP и реального LLM;
- `integration` — проверки постоянной очереди с отдельной PostgreSQL;
- `e2e` — HTTP-контракты и критические пользовательские smoke-сценарии без реального LLM;
- `llm` — будущие проверки с реальным провайдером, запускаются только явно.

## Установка

```bash
.venv/bin/pip install -r requirements-test.txt
```

## Быстрый прогон

```bash
npm run test:backend
```

или:

```bash
.venv/bin/python -m pytest -m "not integration and not e2e and not llm"
```

## Интеграционные тесты

Создайте отдельную базу, например `agent4k_pytest`, и задайте URL:

```bash
export TEST_DATABASE_URL='postgresql://app_user:password@127.0.0.1:5432/agent4k_pytest'
.venv/bin/python -m pytest --run-integration -m integration
```

Integration-набор проверяет обе постоянные очереди:

- подготовку assessment-сессии;
- итоговый анализ `cases_completed → analyzing → completed/report_ready`;
- дедупликацию активных заданий;
- восстановление истекшего lease;
- окончательную ошибку и ручной повторный запуск.

## HTTP smoke-тесты

```bash
npm run test:backend:http
```

Набор проверяет критические HTTP-контракты независимо от production-сервисов.
Он не заменяет browser-приёмку на test-контуре и PostgreSQL integration-тесты.

Защита в `conftest.py` запрещает integration-прогон, если имя базы не содержит
`test` или `pytest`, либо совпадает с `DB_NAME`. Рабочую `app_db` использовать
для pytest нельзя.

## Покрытие

```bash
npm run test:backend:coverage
```

## Правила для новых тестов

1. Любая исправленная ошибка должна получать регрессионный тест.
2. Unit-тесты не читают `.env` и не подключаются к PostgreSQL.
3. Integration-тесты создают данные только в `TEST_DATABASE_URL`.
4. Реальные DeepSeek-вызовы всегда помечаются `@pytest.mark.llm`.
5. Тест обязан удалять созданные записи или использовать изолированную схему.

## Непрерывная интеграция (CI)

На `pull_request` workflow `.github/workflows/backend-tests.yml` выполняет быстрые
unit- и HTTP-проверки. Workflow `.github/workflows/full-verification.yml`
выполняет integration и browser acceptance в PR-контексте актуального head без
повторения unit и HTTP. В draft запускаются только быстрые jobs, а frontend-набор
откладывает release gate. При переводе в `Ready for review` быстрый CI запускается
повторно, требует согласованный новый номер для продуктовых изменений и запускает
`full-verification`. После этого каждый новый commit Ready PR повторяет полный
набор; новый commit draft PR его не запускает. Устаревший незавершённый полный
прогон того же PR отменяется.
Активный ruleset запрещает merge без checks `frontend`, `pytest` и
`full-verification`. После push в `main` проверки повторно не запускаются: workflow
выполняет только `deploy-test` уже проверенного commit.
Все БД временные и изолированные; рабочие пароли и данные в CI не используются.
