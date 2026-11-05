# Тесты backend

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
конечную допущенную AS и lineage. Новая программа пока не опубликована, прежний
release fixture 1.1 не заменён. Новый paid PATH, публикация и выпуск не выполнялись.
Исторический PREP-DIAG-01 остаётся UNKNOWN и не отождествляется с покрытием.

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
