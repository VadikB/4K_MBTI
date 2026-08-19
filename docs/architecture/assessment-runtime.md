# Assessment runtime

## Основные связи

```text
AssessmentConfiguration
  ├── MethodologyVersion
  └── ScenarioVersion
             │
             ▼
       Session snapshot
             │
             ▼
       Scenario runner
             │
             ▼
       Component registry
```

## Жизненный цикл версии

```text
draft -> ready_for_review -> published -> retired
```

Редактируется только `draft`. Published-версия никогда не меняет definition; для изменения она клонируется в следующий draft.

## Authoring workflow

Новая сущность создаётся через `POST /users/admin/assessment-definitions/{entity_type}` и получает собственный `code` и draft-версию 1. Существующая сущность получает следующую версию через clone endpoint.

Полный путь публикации:

```text
create draft v1 -> validate -> submit -> publish definition
                                          │
published methodology + published scenario
                     │
                     ▼
       create configuration draft -> publish
                                      │
                                      ▼
                      freeze prompt bundle and optionally make default
```

Default назначается только во время публикации конфигурации. Draft не может вытеснить текущую рабочую default-конфигурацию.

## Жизненный цикл сессии

1. Выбирается опубликованная assessment configuration.
2. Methodology и scenario definitions валидируются и объединяются.
3. Snapshot и checksum сохраняются в `user_sessions`.
4. Runner исполняет стадии только из snapshot.
5. Каждый запуск стадии записывается в execution trace.

До создания `user_sessions` подготовительные стадии связываются с `assessment_preparation_jobs`. После создания или восстановления сессии эти stage runs получают также `session_id`, поэтому единый trace сохраняет bootstrap и последующее исполнение.

## Ограничения scenario definition v1

Первая версия формата поддерживает:

- зарегистрированные component code и version;
- линейные переходы;
- параллельную группу оценочных компонентов;
- фиксированные переходы success/failure;
- retry policy с числовым лимитом.

Формат не поддерживает произвольный Python, SQL или `eval`-условия. Условия могут ссылаться только на зарегистрированные predicates.

## Разделение LLM и методологии

LLM gateway отвечает только за транспорт. Промпты разрешаются по ссылкам из session snapshot. Domain-компоненты получают gateway и resolved prompt через зависимости и не выбирают текущие активные настройки самостоятельно.

Опубликованная assessment configuration содержит неизменяемый `prompt_bundle_json`. В него входят промпты интервьюера, профили и правила evaluator-агентов и инструкции генерации кейсов. При создании preparation job bundle копируется в execution snapshot; последующее изменение настроечных таблиц не влияет на эту сессию.
