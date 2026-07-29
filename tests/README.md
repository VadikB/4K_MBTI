# Backend tests

Тесты разделены по уровню:

- `unit` — быстрые проверки без PostgreSQL, HTTP и реального LLM;
- `integration` — проверки постоянной очереди с отдельной PostgreSQL;
- `e2e` — будущие полные пользовательские сценарии через HTTP;
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

## Integration

Создайте отдельную базу, например `app_db_mbti_pytest`, и задайте URL:

```bash
export TEST_DATABASE_URL='postgresql://app_user:password@127.0.0.1:5432/app_db_mbti_pytest'
.venv/bin/python -m pytest --run-integration -m integration
```

Защита в `conftest.py` запрещает integration-прогон, если имя базы не содержит
`test` или `pytest`, либо совпадает с `DB_NAME`. Рабочую `app_db` использовать
для pytest нельзя.

## Coverage

```bash
npm run test:backend:coverage
```

## Правила для новых тестов

1. Любая исправленная ошибка должна получать регрессионный тест.
2. Unit-тесты не читают `.env` и не подключаются к PostgreSQL.
3. Integration-тесты создают данные только в `TEST_DATABASE_URL`.
4. Реальные DeepSeek-вызовы всегда помечаются `@pytest.mark.llm`.
5. Тест обязан удалять созданные записи или использовать изолированную схему.

## CI

Workflow `.github/workflows/backend-tests.yml` запускается на каждый push и
pull request. Он поднимает временный PostgreSQL 16, выполняет быстрые тесты,
а затем integration-набор. Пароли и данные рабочей БД в CI не используются.
