# STATE — P4K-F01

- База: `origin/main` `748be43e55587aa3b7e3a3945189c5ac737f59eb`,
  2.0.97; ветка `codex/p4k-f01-role-isolation` в отдельном worktree.
- Реализация/тесты: `da3304b76cbb71c4d165a4763f0746a38a68c881`,
  12 путей, 452 добавления, 32 удаления к базе. Локальный отчёт и PR-body:
  `e4573cbd6cee912eb34d3aaefea4c0e081bff7b9`.
- Решение: прямое поручение владельца выполнить
  `P4K-F01_Role_Isolation.txt` v1.0. Исключения: действующие данные,
  реальные письма, LLM, merge/deploy. После локального отчёта владелец ответил
  «Продолжаем»: `branch_push=true`, `pr=true` для draft PR F01 к `main`;
  `merge=false`, `deploy=false`, `version_bump=false`,
  `artifact_publish=false`. Вложение само по себе не давало допуска на push/PR.
- Реализация: общий разбор `SUPERADMIN_EMAILS`, проверка configured/local/active
  platform permissions до записи во всех действующих входах, скрытие
  ошибочных связей из ответа обычному admin, auth и повтор приглашения.
  Ошибочные данные не удаляются.
- AC01 PASS локально; AC02 PASS для действующего списка (отдельного поиска
  участников нет); AC03 PASS локально; AC04 PASS локально.
- Проверки: backend 1068 PASS, HTTP 152 PASS, адресные 50 PASS,
  DB integration 4 PASS, actual browser/HTTP/PG
  PASS. Первый полный integration: 360 PASS/11 FAIL/2 SKIP, из них10 —
  урезанный R03 fixture без платформенных таблиц (исправлен, адресно14 PASS),
  1 — timezone локального PG (UTC, адресно1 PASS). Полный повтор:
  372 PASS/2 SKIP/1224 DESELECTED, 0 FAIL.
  Обе одноразовые БД удалены, локальный PG остановлен, временный токен удалён.
  CI/TEST/human visual NOT_RUN.
- Следующий шаг: push ветки F01 и draft PR, проверить быстрый CI на точном
  head/base; затем решение владельца о версии/Ready и отдельное review.
