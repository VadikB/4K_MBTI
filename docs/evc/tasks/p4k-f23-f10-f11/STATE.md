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

## Продолжение релиза 11.11.2026

- Владелец отдельно разрешил push `b8654a8943b628145a2995da6f8f3bd54d35f82b`
  и один PR к `main`. Создан draft PR #212, GitHub подтвердил точный head SHA.
  На этом head CI `frontend` и `pytest` — PASS; `full-verification` пропущен
  условием `draft == false`.
- Затем владелец прямо утвердил PATCH `2.0.100`, `ready:prepare`, commit/push
  обновления PR #212 и перевод в `Ready for review`. Свежий
  `origin/main=aeea4e10014f9852e269eff0da8bf8cabe8d4427`, версия базы
  `2.0.99`, `merge-base` совпадает с базой. `ready:prepare` без кандидата
  предложил `2.0.100` без записи (ожидаемый exit 2). С утверждённым кандидатом
  preflight — PASS: четыре файла версии и производный `web/dist`, release gate
  и сборка пройдены. Финальный SHA release commit и результаты CI фиксируются
  после push.
- `merge=false`, `deploy=false`, `artifact_publish=false`. До merge необходимы
  полный CI на release head и человеческое review; TEST/readback SHA и owner
  visual остаются отдельной стадией. Действия публикации программы не разрешены.

## CI и исправление ожидания

- PR #212 переведён в `Ready for review` на head
  `11b91319e9ee38afb54f5a3e58c0e1c6ab088d96`.
- CI: `frontend`, `pytest`, integration и четыре runtime browser lanes — PASS;
  browser fast — FAIL 1 из 231, итоговый `full-verification` — FAIL. Новый
  combined тест ожидал текст версии в форме, который присутствовал ещё до
  завершения connect. CI успел перерисовать форму и очистить введённый email.
- Исправлено только ожидание нового теста: обе версии A/B теперь проверяются
  по подтверждённому состоянию `Подключено` после readback. Адресный тест на
  owned PostgreSQL — PASS (1, 36.9s). Следующий шаг — commit/push исправления,
  обязательный полный CI и человеческое review на новом SHA.
