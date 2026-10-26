# R00–R10: функциональный путь Case / Cycle

## Результат и область

Довести путь Profile → Case → принятая персонализированная AS → runtime → Evidence
→ IA → допуск → Results Cycle → M8 до проверяемого кандидата. Карточки R00–R10
образуют один связанный принимаемый результат; каждая фиксируется отдельным рабочим
коммитом и записью в `STATE.md`.

Base: `main@b3bbdc9e78880879e1d4fc930ef8c9cc9f200524`, приложение `2.0.28`.
Рабочая ветка: `codex/case-cycle-r1`. Активная карточка: R00.

## Источники и решения

Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, документы EVC, Change 01,
SourceSet `2026-10-01`, архитектурный контекст/Registry и архив
`P4K_Main_Case_Cycle_Restart_2026-10-26.zip`. Remote `origin/main` после fetch
совпадает с base; повторный аудит не требуется. Авторское поручение от 26.10.2026
разрешает отдельное изменение управляющих документов и CI в R00 и последовательное
выполнение R01–R10 без повторного разрешения на каждую карточку.

Остановленная работа сохранена: исходный checkout на
`codex/ux-ui02-spacing-radar-status-colors@717bff56a69c2674434bc20434475d29d3a97d4e`,
untracked файлы не изменялись. `gh` отсутствует; состояние PR локально не подтверждено.

## Стоп-условия и границы

На R00 стоп-условия отсутствуют. Предметные значения, IndicatorIDs, дескрипторы,
достаточность и агрегация не меняются без решения владельца. Внешний блокер
останавливает только зависимую карточку. Исторические snapshots и FROZEN-артефакты
не переписываются.

До точки кандидата: `branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`. На R09 разрешено подготовить один
номер приложения-кандидата; merge/deploy и публикация артефактов требуют своей
согласованной точки.

## Проверки и откат R00

Минимум: YAML parse, release checker, проверка ссылок/команд, `git diff --check`,
содержательная сверка четырёх событий CI. Продуктовые тесты для R00 не применимы.
Откат: revert только R00 commit; данные и runtime не затрагиваются.

## R01 — карта полей

`author IndicatorObservability[index]` → immutable author layer + checksum → adapted
target с точным `source_pointer`/checksum → compiled target. В compiled/C-34/M6
сохраняются `material_refs`, `event_refs`, `character_refs`, `authority_refs` и
`author_basis`; фактические C-45 context refs остаются отдельными предъявленными
materials/events/Turns с sequence boundary. Package `0.5`, compiler `0.5.0`, draft;
исторические `0.2`–`0.4` не изменены. Откат для новых запусков — вернуть resolver
на `0.4`; сохранённые snapshots продолжают читаться по собственной версии.
