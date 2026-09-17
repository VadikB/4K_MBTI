# Репозиторий материалов Indicator evaluator v2

## Результат и область

Самодостаточный вход evaluator contract v2 строится из frozen определения
методологии и зафиксированных для сессии связей `case → indicator`. Включены
authoring-проекция, фиксация связей в session snapshot-проекцию, indicator evidence
rules, read-only loader и builder. Не входят алгоритм selection, автоматическое
создание authoring-mappings, LLM execution, публикация 1.1 и агрегация.

## Инварианты и критерии приёмки

- [x] Нормативные поля Indicator читаются только из execution snapshot.
- [x] БД определяет только назначенные сессии кейсы и их evidence-настройки.
- [x] Loader ограничен `session_id`, `methodology_version_id` и frozen Indicator IDs.
- [x] Authoring-связь после старта не меняет состав материалов сессии.
- [x] Legacy skill material repository не меняется.
- [x] Пустой или несогласованный frozen scope отклоняется до evaluator.

## Откат

Удалить loader/builder и не заполнять новые таблицы. Пустые таблицы совместимы со
старым runtime; удаление заполненных таблиц требует отдельного решения по данным.
