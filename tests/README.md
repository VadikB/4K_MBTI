# Тесты backend

Постоянный синтетический контур «суперадмин → первый Case» и его текущие границы
описаны в [`docs/evc/assessment-first-case-profile.md`](../docs/evc/assessment-first-case-profile.md).

Бесплатные адресные проверки harness (без БД, credentials и LLM):

```bash
.venv/bin/python -m pytest -q tests/unit/test_assessment_first_case.py tests/unit/test_test_stand.py tests/unit/test_assessment_run_summary.py
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
