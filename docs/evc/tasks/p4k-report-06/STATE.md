# STATE — P4K-REPORT-06

- Ветка/worktree: `codex/p4k-report-06`, `worktrees/p4k-report-06`.
- Проверенный commit реализации: `c93786c10e3eb2528ef55f7fbf2ff20594e9ac45`. Дальнейшее обновление STATE/CHECKS — только документация передачи.
- Base: `7e96d4dc49e8e37356aa93a736d1373fb58eb779` (REPORT-05 merge). Git-дерево совпало с временной базой `9ea439af`; ветка перенесена на точный merge commit без изменения рабочих файлов.
- Выполнено: история по закрытию с устойчивой связью на один Cycle, сохранённая программа в кабинете, отдельный список M8 без legacy-архива и выбора revisions, страницы по 10, обновление состояний, точный deep link, возврат на страницу, понятный переход старого адреса. Публичные данные/схема не удалены.
- PATCH 2.1.19 подготовлен `npm run ready:prepare -- --candidate 2.1.19`; сервер и UI согласованы. SQL-миграций и предметных артефактов нет.
- Локально: 1 PostgreSQL15 integration PASS на собственной `p4k_report06_pytest` (порт 55466 освобождён), 33 HTTP PASS (32 исходных + 1 новый), 354 frontend PASS, browser REPORT-04/05/06 9 PASS и W02/LK01 4 PASS, ESLint/build/release unit 11 PASS, `git diff --check` PASS. Полный backend: 1117 PASS, 9 sandbox `PermissionError` в synthetic-limits; адресный повтор с разрешённым запуском subprocess — 19 PASS. См. `CHECKS.md`.
- Снимки истории в `evidence/history-list-{1440,390}.png` и `history-{1440,390,720}.png`; 720 CSS px использованы как адресная проверка компоновки при уменьшенном viewport, 320 px проверены на отсутствие горизонтальной прокрутки. Человеческая визуальная приёмка не выполнена.
- Следующий шаг: push и PR; обязательные CI `frontend`, `pytest`, `full-verification` точного head и визуальная приёмка до merge. `merge/deploy=false`.
