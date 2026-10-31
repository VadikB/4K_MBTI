# Тесты backend

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
автоматически запускается при открытии или повторном открытии PR и после каждого
нового commit, а также при переходах между draft и `Ready for review`; он выполняет
unit, HTTP, integration и browser acceptance в PR-контексте актуального head.
В draft быстрый frontend-набор откладывает только release gate. При переводе в
`Ready for review` обязательный CI запускается повторно и требует согласованный
новый номер для продуктовых изменений.
Активный ruleset запрещает merge без checks `frontend`, `pytest` и
`full-verification`. После push в `main` проверки повторно не запускаются: workflow
выполняет только `deploy-test` уже проверенного commit.
Все БД временные и изолированные; рабочие пароли и данные в CI не используются.
