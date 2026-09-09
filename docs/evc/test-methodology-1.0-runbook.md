# Подготовка методологии 1.0 на test-стенде

## Назначение

Runbook восстанавливает неперсональный методологический слой baseline 1 на
изолированной test-БД. Пакет не содержит пользователей, профилей, сессий,
ответов, отчётов, журналов и секретов.

Канонический пакет:
`assessment_definitions/data/competencies_4k/v1.json`.

## Проверка пакета без изменения данных

```bash
PYTHONPATH=. .venv/bin/python scripts/import_methodology_bundle.py \
  --input assessment_definitions/data/competencies_4k/v1.json
```

Импортёр проверяет checksum и разрешает работу только с БД, имя которой содержит
`test` или `pytest`.

## Первичная установка на пустой test-стенд

```bash
PYTHONPATH=. .venv/bin/python scripts/import_methodology_bundle.py \
  --input assessment_definitions/data/competencies_4k/v1.json \
  --apply \
  --replace-existing

PYTHONPATH=. .venv/bin/python scripts/update_deployed_db.py \
  --apply \
  --recompute-case-quality
```

Перед заменой импортёр проверяет отсутствие зависимых assessment-сессий и
пользовательских ссылок на методологические сущности. Все удаления и вставки
выполняются в одной транзакции.

## Ожидаемый состав

- 3 оценочных роли и служебная роль администратора;
- 4 компетенции, 13 навыков и 42 критерия уровней;
- 57 кейсов и их связи с ролями/навыками;
- 4 профиля evaluator-агентов и 12 правил;
- 3 версии промптов интервьюера.

## Проверка после импорта

1. `/health/ready` возвращает `status=ready`.
2. Техническая регрессия проходит проверки `data_roles`, `data_skills`,
   `data_case_registry`, `data_prompt_profiles`.
3. В форме профиля доступны роли «Линейный сотрудник», «Менеджер», «Лидер».
4. Для каждой роли запускается подготовка оценки и создаётся session snapshot.
5. В snapshot присутствуют `methodology.definition.roles` и
   `methodology.definition.levels`.

## Откат

Импорт заменяет только методологические справочники. До появления assessment-
сессий пакет можно повторно применить. После начала тестовых прохождений замена
будет автоматически заблокирована; для отката используется отдельная чистая
test-БД либо восстановление её резервной копии.
