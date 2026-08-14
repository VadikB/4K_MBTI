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
