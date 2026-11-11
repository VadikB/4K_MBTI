# STATE — P4K-F01

- Первоначальная база: `origin/main`
  `748be43e55587aa3b7e3a3945189c5ac737f59eb`, 2.0.97. Актуальная база:
  `3beb84596ea27bd7f19b06a2f5b8ee4533908043`, 2.0.98 (F02 #210).
  Ветка `codex/p4k-f01-role-isolation` в отдельном worktree.
- Передача: опубликована ветка и открыт draft PR
  https://github.com/VadikB/4K_MBTI/pull/211 к `main`.
- Реализация/тесты: `da3304b76cbb71c4d165a4763f0746a38a68c881`,
  12 путей, 452 добавления, 32 удаления к базе. Локальный отчёт и PR-body:
  `e4573cbd6cee912eb34d3aaefea4c0e081bff7b9`.
- Решение: прямое поручение владельца выполнить
  `P4K-F01_Role_Isolation.txt` v1.0. Исключения: действующие данные,
  реальные письма, LLM, merge/deploy. После локального отчёта владелец ответил
  «Продолжаем»: `branch_push=true`, `pr=true` для draft PR F01 к `main`;
  затем прямо утвердил patch `2.0.98` и Ready: `version_bump=true`,
  `ready=true`, `merge=false`, `deploy=false`, `artifact_publish=false`.
  После появления F02 в `main` владелец утвердил следующий patch `2.0.99`.
  Вложение само по себе не давало допуска на push/PR.
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
  Быстрый CI на `428c1337`:
  https://github.com/VadikB/4K_MBTI/actions/runs/43065958463 — frontend PASS,
  pytest PASS. На `b155cc08`:
  https://github.com/VadikB/4K_MBTI/actions/runs/43066470788 — frontend PASS,
  pytest PASS. Полный workflow и deploy-test ожидаемо SKIPPED в draft.
  Для `e733db81` на прежней базе: быстрый CI
  https://github.com/VadikB/4K_MBTI/actions/runs/43067617362 PASS, полный CI
  https://github.com/VadikB/4K_MBTI/actions/runs/43067617348 PASS; эти результаты
  устарели после нового `main`.
  TEST/human visual NOT_RUN.
- Подготовка `2.0.98`: первый `ready:prepare` остановился на отсутствующем
  `esbuild` после очистки `web/dist`; lockfile совпадает с исходной копией.
  Повтор со временной ссылкой на её установленный `node_modules` — PASS;
  `npm run lint:js` PASS, frontend 250 PASS, `git diff --check` PASS.
- Обновление базы: `749707e481361e4cd336d5e170e88f529ca048cb` включает F02;
  конфликты только в `web/dist`, разрешены пересборкой. Повтор после объединения:
  backend 1089 PASS, HTTP 152 PASS, frontend 261 PASS, integration 389 PASS/
  2 SKIP, браузер F01 PASS на полной схеме; обе БД и сессия удалены.
  `ready:prepare -- --candidate 2.0.99` — PASS.
- Следующий шаг: опубликовать подготовленный кандидат 2.0.99 и проверить
  повторный CI на точном head/base; затем человеческое review. Merge/deploy
  не разрешены.
