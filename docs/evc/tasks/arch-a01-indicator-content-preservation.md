# ARCH-A01 — сохранность содержания IndicatorTarget до M6

## Основание и границы

- Пакет постановки P4K Case/AS/Cycle Plan, редакция 2.0, карточка
  `03_A01_Content_Preservation.txt`.
- Base разведки: `origin/main@f4af7beb0d09374153bf0e16c6edb5c0dabe1cec`.
- Источник: `functional-personalization/0.2/sources/functional-v0.2`, 9 Case,
  9 авторских AS и 55 `IndicatorObservability`.
- M2, IndicatorID, дескрипторы, достаточность и агрегация не меняются.
- Исторические package `0.2`, runtime rules `1.0.0`, snapshots и evidence не
  перезаписываются.

## Прочитанные источники

`README.md`, `CONTRIBUTING.md`, EVC workflow/matrix/artifact recipe/review,
архитектурные context/Registry, Change 01, SourceSet `2026-10-01`, M5 runtime и
M6 input resolver, карточка ARCH-A01 редакции 2.0.

## Решение

Все 55 целей имеют единую явную source schema из 15 полей. Профиль
`functional-personalization-indicator-v1` принимает только точный набор полей и
не использует fallback/sentinel. Авторские условие, форма проявления, дефект
потери, материалы/факты, нормативный источник, инварианты, ограничение
адаптации и статусы сохраняются в нормализованном target.

Источник не задаёт отдельные branch/event predicates. Поэтому они не
синтезируются из общего условия: сохраняются `null` и явное основание
`SOURCE_HAS_NO_SEPARATE_BRANCH_OR_EVENT_PREDICATE`.

Выпускаются новые draft-артефакты:

- Case package `m5-functional-personalization-cases/0.3`;
- compiler `m5-functional-json-compiler/0.3.0`;
- runtime rules `m5-functional-personalization-runtime/1.1.0`.

## Трассировка

`source IndicatorObservability` → явный compiler profile → Case target →
AssessmentSituation snapshot/execution payload → C-45 → `m6_input_resolver`
без преобразования содержательных полей. Отчёт
`content-preservation-report.json` фиксирует source pointer и checksum
сохранённого содержания каждой из 55 целей.

## Проверки

- сборка package `0.3`: PASS, 9 Case / 55 targets;
- независимое source-based сравнение всех содержательных полей: 55/55 PASS;
- отрицательные удаления условия, material refs и adaptation constraint:
  отклоняются до сборки и pre-admission принятия generated AS;
- адресные unit компилятора/runtime: 19 passed, затем 14 passed;
- адресные generation/pre-admission регрессии: 23 passed;
- backend без integration/e2e/llm: 539 passed, 220 deselected;
- HTTP/e2e: 66 passed, 11 deselected;
- PostgreSQL: импорт package, исполнение всех девяти Case и путь
  `accepted AS → execution → C-45 → M6 input`: 2 passed;
- `git diff --check`: PASS.

## Непроверенное и стоп-условия

- Реальный provider не запускается в ARCH-A01; он относится к сквозной A06.
- Методологическая приёмка, Reliability и runtime admission не присваиваются;
  новые пакеты остаются `draft`/`runtime_enabled=false`.
- Ветка создана от base до слияния FIX-B01/B02. Перед PR обязательны обновление
  от нового `main`, release preparation, повторный полный локальный минимум и CI.

## Откат

Не выбирать package `0.3` и runtime rules `1.1.0` для новых запусков. Чтение и
история `0.2`/`1.0.0` сохраняются; старую дефектную AS не считать принятой.
