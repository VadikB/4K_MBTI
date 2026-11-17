# STATE — P4K-REPORT-11

- База `fffd501a51cae673a4e0ee87ec5d6cbc83069e21`, версия 2.1.26;
  `codex/p4k-report-11` в отдельном worktree. Пользовательская ветка не затронута.
- Завершено: разведка источников, AC07/AC08 в `main`, конечный ресурсный
  профиль; HTTP/SQL bridge seeded pre-close Cycle → закрытие → C-67 →
  повторное чтение/PDF; браузер по его сохранённому ответу, просмотр экранов/PDF.
- Коммит `b7690554`, PR #242: обязательный CI обнаружил в прежнем QA19-04
  Linux размер SVG-подписей ниже 14/12 px; остальные 7 jobs успешны.
- Владелец согласовал `version_bump=true` до 2.1.27 и обновление PR, без
  merge/deploy. CSS-правка 16/13.5 px, `ready:prepare` PASS; на кандидате
  browser QA19-04/REPORT-05/REPORT-11 — 5 PASS, frontend 9 PASS, build PASS.
- Следующее: commit/push кандидата, обязательный CI точного head.
  Человеческая визуальная приёмка и merge/deploy отдельно; пробелы PARTIAL в CHECKS.
- Откат: revert этого test/docs PR; собственную БД удалить после остановки
  процессов, без изменения runtime/snapshots.
