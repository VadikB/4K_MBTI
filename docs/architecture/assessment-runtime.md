# Runtime платформы оценки

## Основные связи

```text
AssessmentConfiguration
  ├── MethodologyVersion
  ├── ScenarioVersion
  └── AgentDefinitionVersions
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

## Процесс управления версиями

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

В `agent_definitions` prompt bundle также сохраняются точные опубликованные версии
определений оценочных агентов: Markdown-инструкция, contract references, executor,
runtime metadata и checksum. Published agent definition неизменяем; изменение
начинается клонированием в следующий draft.

При выполнении competency evaluator входной контракт получает определение только
из session snapshot и повторно проверяет checksum, input/output contract,
executor и runtime mode. Единый executor выбирает реализацию строго по паре
`executor.code + executor.version`; fallback по позиции агента в списке запрещён.
Текущие Python-алгоритмы зарегистрированы как стратегии `legacy_adapter`, а
Markdown-инструкция из определения включается в semantic evaluation prompt.

`runtime.mode=universal_llm` направляет тот же self-contained input в единый
Markdown-driven evaluator. Режим защищён выключенным по умолчанию environment
kill switch, принимает только профиль `assessment_strict`, ограниченные
temperature/retry/timeout/output tokens и `fallback=fail`. Ответ LLM обязан
полностью пройти Pydantic contract и проверку ссылок на skill/case из входа до
передачи в repository. `legacy_adapter` остаётся отдельным совместимым режимом.

Для `universal_llm` competency definition обязана содержать непустой список
`skill_codes`. Generic material repository использует только эти замороженные
коды и текущий `session_id` для чтения skills, rubrics, cases, user evidence,
required blocks и red flags. Такой runtime не резолвит competency-specific
Python agent и не требует legacy evaluator prompt profile. Для published legacy
v1 сохраняются прежние loaders и обратная совместимость.

Опциональный `competency.shadow_evaluation` ссылается на отдельный frozen
`universal_llm` AgentDefinition и собственный `skill_codes`. Shadow запускается
только после сохранения официального `legacy_adapter` результата и только при
двух включённых kill switches. Его ошибка не меняет статус official analysis.
Отдельная таблица хранит version/checksum обоих агентов и только обезличенные
метрики сравнения: уровни, количества evidence/red flags и case IDs. Rationale,
excerpts, пользовательский текст и сырой LLM-ответ в shadow storage не попадают.
