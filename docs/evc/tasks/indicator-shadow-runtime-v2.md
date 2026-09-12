# Shadow runtime Indicator evaluator v2

## Результат и область

Добавлен выключенный по умолчанию shadow runner для contract v2. Он строит
строгий JSON prompt из frozen AgentDefinition и самодостаточного input, проверяет
полноту Indicator output, сохраняет результат только в indicator repository и
изолирует сбой от официальной оценки. Не входят подключение к analysis queue,
публикация AgentDefinitions 1.1 и включение флага.

## Критерии приёмки

- [x] При выключенном flag LLM и БД не вызываются.
- [x] Используется только frozen Markdown и contract schema v2.
- [x] Ответ содержит каждый и только каждый входной Indicator.
- [x] Case и Red Flag references ограничены конкретным Indicator.
- [x] Ошибка shadow не влияет на официальный результат и не раскрывает evidence в лог.
- [x] Успешный output сохраняется только в indicator-level repository.

## Откат

Оставить `ASSESSMENT_INDICATOR_SHADOW_ENABLED=false` или удалить новый runner.
