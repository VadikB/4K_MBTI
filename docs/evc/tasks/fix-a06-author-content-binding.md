# FIX-A06 — привязка авторского содержания IndicatorTarget после LLM

## Результат

Исключить повторяемую потерю защищённых авторских полей `IndicatorObservability`
на PM-03 real-provider пути, сохранив запрет допуска неполной или подменённой AS.

## Основание и источники

- Base: `85d94993f500edfb62cdbbb652bd2eb36d2eaa69`, test `2.0.26`.
- Воспроизведение: `A06.C01.SALES`, evidence
  `docs/evc/evidence/arch-a06/real-provider-pilot-2026-10-25.json`.
- Контракт: Change 01, ADR-002 C-34, package
  `m5-functional-personalization-cases` `0.3` и его
  `content-preservation-report.json`.
- Прочитаны: `README.md`, `CONTRIBUTING.md`, обязательные EVC-процедуры,
  Change 01, task manifest, ADR-002, traceability, generation service и тесты.

## Граница

- Включено: техническая привязка неизменяемых авторских полей из frozen input
  snapshot к ответу генератора до deterministic validation; регрессия девяти
  полей фактического A06 pilot.
- Не включено: изменение IndicatorIDs/смысла, исправление `M6_CONTEXT_REFERENCE`,
  остальные 26 real-provider строк, методологическая приёмка и Reliability.
- Исторические package/evidence/snapshot не изменяются.

## Решение

LLM не является владельцем авторского содержания. После разбора provider JSON
сервис создаёт новый candidate и для существующих совпавших IndicatorID заменяет
только защищённые авторские поля значениями frozen `author_as_example`. Отсутствующий,
лишний или переименованный target не создаётся и продолжает отклоняться валидатором.
До и после привязки сохраняются отдельные checksums, чтобы преобразование было видно
в trace. Содержательные дефекты остальных частей AS сервером не исправляются.

## Проверки

- Адресная регрессия и связанные A06/package тесты: PASS, `23 passed`.
- Полный backend-набор: PASS, `579 passed`, `230 deselected`.
- `py_compile` и `git diff --check`: PASS.
- `npm run lint:js`: PASS.
- Release candidate: `2.0.27`; `npm run build:web`: PASS.
- Real-provider повтор — отдельный явный LLM-прогон после controlled PASS.

## Откат

Revert отдельного commit. Новых схем и миграций нет; предыдущие snapshots остаются
исполняемыми. При FAIL real-provider новый evidence сохраняется отдельно и не
перезаписывает pilot от 25.10.2026.

## Открытые вопросы

Нет для controlled исправления. Повтор реального вызова уже разрешён владельцем
в пределах изолированной синтетической A06-матрицы.
