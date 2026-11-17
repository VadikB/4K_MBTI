# STATE — P4K-REPORT-10

- База `61dbe0c80a7d4847fa98353b6d8b9b162d4b9e32`, ветка `codex/p4k-report-10` в отдельном worktree; пользовательская ветка не затронута.
- Реализация и проверка выполняются по `TASK.md`; фактические результаты записываются в `CHECKS.md`.
- Источник → правило → контракт/данные → код → проверка: M8 v1.2, REPORT-05/07/09 → `m8-results-report-contract.md`, C-67 и comparison payload → `m8_results.py`, `m8_report_comparison.py`, Typst/SVG, routes → PDF unit/HTTP/integration и визуальные страницы.
- Материал проверки: 10 синтетических сохранённых проекций, PDF bytes и PNG страниц в `evidence/`; SHA-256 PDF зафиксированы в `evidence/sha256.txt`. Runtime PDF использует выбранный `report_id` и неизменяемую C-67; печатный макет — `v2`, старый `v1` не изменён.
- Rollback: revert кода и шаблонов; сохранённые отчёты не меняются. Указатель исправлений REPORT-09 должен оставаться читаемым.

- Локальный минимум: backend 1209 PASS, HTTP 193 PASS, integration 446 PASS/2 SKIP, frontend 364 PASS, browser REPORT-10 1 PASS, lint/build/diff PASS. Обязательный CI актуального PR head и приёмка владельца остаются gates.
- Стоп-условий в согласованной области не выявлено; merge/deploy REPORT-10 не выполняются до принятия владельцем.
