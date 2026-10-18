# UX-REP02 — описательный отчёт о проявленных навыках

## Основание и границы

- Вход владельца: `/Users/vadim_bogachev/Downloads/UX-REP02_Descriptive_Report_2026-10-17.txt`, редакция 1.0 от 17.10.2026.
- Base: `main@09ebdb4` после REP01 и CTX01.
- Источники: Change 01, SourceSet `2026-10-01`, M8 1.2, C-67, partial-result 1.0, frozen M4 snapshot Cycle.
- Один результат: новая версия представления существующего Results/Report. Results, C-67 прошлых версий и PDF не переписываются.
- Вне границ: рекомендации, обучение, кадровые выводы, новый Skill Level/CompetencyScore, массовая регенерация истории, REL01.

## Решения реализации

- Новый report package `m8_basic_report/1.4.0` запрещает рекомендации и фиксирует контракт описательных утверждений.
- Prompt, JSON-схема и политика валидации — версионируемые артефакты; пользовательский текст передаётся как данные.
- Числа, outcome и ограничения берутся только из сохранённого Results; генератор не может их заменить.
- Каждое утверждение связано с `skill_ids`, допустимыми основаниями и локальными ограничениями; цитата обязана точно встречаться в разрешённом фрагменте.
- GET/UI/PDF читают только сохранённую версию и не вызывают LLM.
- Исторические отчёты получают явную projection без рекомендаций и без сочинённого резюме.

## Трассировка приёмки

| Требование | Реализация | Проверка |
|---|---|---|
| Четыре исхода, zero != null | C-67 skills без производных уровней | unit + HTTP + browser |
| Имена и состав M2 | snapshot каталога из точной M2 | unit |
| Почему сделан вывод | saved descriptive claims + basis refs | unit + integration |
| Контекст на утверждение | claim-level context selection из frozen M4 | unit + integration |
| Нет советов | package invariant + validator + UI/PDF | unit + frontend |
| Сбой пояснения не скрывает факты | `pending/ready/failed`, точные сообщения | HTTP + browser |
| История неизменяема | новая Report revision/projection | integration |

## Проверки и откат

- Минимум: `git diff --check`, Python compile, профильные unit, frontend tests/lint.
- DB/HTTP: изолированная PostgreSQL; browser acceptance по доступному CI.
- Реальный provider и недоступные браузеры отмечаются `NOT_RUN`, synthetic gateway не считается содержательной приёмкой.
- Откат: revert кода и возврат loader на 1.3.0; созданные immutable Report revisions не удалять.
