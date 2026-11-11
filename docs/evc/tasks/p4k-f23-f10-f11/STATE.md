# Состояние P4K-F23-F10-F11

- Base `origin/main=aeea4e10014f9852e269eff0da8bf8cabe8d4427`;
  ветка `codex/p4k-f23-f10-f11`, отдельный чистый при создании worktree.
- Завершено: сверка источников и опубликованного receipt; F01 уже в main;
  воспроизведено нарушение идемпотентности F23 на owned PG; исправлены повторные
  записи membership/suppression; добавлены регрессии F23, F10 dry-run/publish,
  F11 A→B/replay/history. Сквозной browser выявил stale UI после grant при
  корректном PG/GET; добавлен повторный GET перед success для grant/revoke.
  Старые предметные механизмы не переписаны.
- Локальный кандидат: один commit ветки `codex/p4k-f23-f10-f11`, точный SHA
  записан в финальном `/private/tmp/p4k-f23-f10-f11-final/*/source.json` и
  передаётся владельцу отдельно. Все проверки локального минимума завершены.
- Следующий шаг владельца/релиза: отдельный допуск на push/PR и, если нужен
  новый рабочий выпуск, на `artifact_publish`; затем обязательные CI, review,
  merge/deploy, TEST/readback SHA и визуальная приёмка. Эти внешние стадии не
  выполнены локальным кандидатом.
- Изменены: `Api/routes.py`, `web/js/screens/admin/organizations.js` и
  производный `web/dist`, два существующих integration-теста, новый
  `tests/integration/test_f10_publisher_db.py`, combined browser/PG fixture и
  `TASK.md`/`STATE.md`/`CHECKS.md`/`PR_BODY.md`.
- Проверки до финального SHA: targeted frontend 13 PASS; HTTP F23/F01/ADM19
  19 PASS; исходные PG 29 PASS; новая F23 регрессия before FAIL → after PASS;
  новые F10/F11 PG 3 PASS; frontend 261 PASS; lint/build PASS; backend 1089 PASS;
  HTTP 152 PASS; адресный browser 41 PASS, deep-link 1 PASS, combined 1 PASS.
  Первый полный integration: 367 PASS, 25 setup ERROR из-за DSN, 2 skipped;
  EXEC-FIX02 при правильном DSN 25 PASS. Исправленный полный integration:
  392 PASS, 2 ожидаемых real-provider skip. Сквозной browser с проверкой
  UI grant/revoke повторён: 1 PASS, 42.3s; финальный повтор на SHA commit —
  1 PASS, owned cleanup подтверждён.
- Блокеры: внешний TEST/owner visual и CI не выполнены; исходные
  `P4K.DEV.PRINCIPLES`/glossary/F23/F10/F11 не доступны отдельно от входного
  объединённого задания. Для локального точечного исправления это не требует
  нового предметного решения.
