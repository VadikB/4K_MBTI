# AC18-ADM-1C — статусы, история и дозавершение админского пути

## Результат и область

- Основание: пакет `P4K_ADM_1C_Statuses_and_History`, редакция 1.3 от 08.11.2026.
- База: `origin/main` `65a62aca6b5f3fb870826a7f41977a4fd0f3b590`, версия 2.0.84, PR195.
- Включено: C-AC01…12; сначала доказанный остаток C-AC11/12, затем gap-анализ C-AC01…10.
- Не входит: изменение методологии, published snapshots, admission/start/таймеров, новая программа,
  физическая очистка рабочей БД, реальные письма и LLM-вызовы.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/evc/agent-workflow.md`,
  `docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`, Product Architecture/Registry,
  Change 01 и manifest, ADR-002, traceability, task/review/baseline templates.
- Пакет: `START_CODEX.txt`, `TASK.txt`, `CURRENT_TASK_STATE.txt`, `DECISIONS.txt`,
  `BASELINE_2.0.83.txt`, `WORK_MATRIX.csv`, `METRIC_DECISIONS_APPROVED.txt`, `SOURCES.txt`,
  `STATUS_RULES.txt`, `VISUAL_ACCEPTANCE.txt`; SHA256 архива — PASS для всех файлов.
- Принято владельцем: M-02…M-06; M-07 заменён исключением до-M1–M8 legacy; дополнительный
  banner M-01 не добавлять. CURRENT/FROZEN не присваиваются.
- Доказанный остаток 1Б: четыре контрпримера B-RES01/02 на SHA базы.
- Стоп-условия: база и требования определены; миграция и новый предметный артефакт не нужны;
  рабочая БД и внешняя публикация не затрагиваются. Решение владельца сейчас не требуется.

## План и checkpoint

- Завершено: архив и base проверены; C-AC11/12 получили exact receipt/readback и понятный
  per-person результат; C-AC03/05 — история поколений и фактический срок приглашения;
  C-AC04 — read-only обработка; C-AC10 — современная Cycle/Report-проекция без legacy/fake zero.
- Завершено review diff: недостижимые legacy-агрегаторы `user_sessions` удалены из активного
  модуля; воспроизводимый визуальный маршрут покрыт адресными browser-тестами.
- Следующий шаг: human visual acceptance; затем согласованный PATCH candidate, push/PR и CI.
- Ветка: `codex/ac18-adm-1c-status-history`; base/head до изменений: `65a62aca…`.
- `branch_push=false`, `pr=false`, `merge=false`, `deploy=false`, `version_bump=false`,
  `artifact_publish=false`.

## Проверка и откат

- JS: `node --check`, адресные Playwright tests, `npm run build:web`.
- Backend/API: unit/e2e и integration только с изолированной БД `test`/`pytest` и marker владельца.
- Общие: `git diff --check`; полный CI обязателен перед merge.
- Visual/human/test stand фиксируются отдельно и не объявляются PASS агентом без доказательства.
- Откат: совместимый `git revert` собственных изменений; пользовательские данные не удаляются.

## Фактические проверки · 09.11.2026

- `npm run lint:js` — PASS.
- `node --test tests/frontend/*.test.mjs` — PASS, 155/155.
- backend без integration/e2e/llm — PASS, 976/976.
- полный HTTP/e2e — PASS, 110/110 (12 deselected по marker).
- адресный Playwright `AC18-ADM-1C` — PASS, 6/6; Chromium component/browser mock,
  не human acceptance и не физическое устройство.
- owned PostgreSQL 16 `product4k_pytest_adm1c` — PASS, 2/2: exact operation receipt и
  modern Cycle/Report metrics; Docker `--rm`, рабочая `.env`/БД не использовалась.
- `npm run build:web`, Python/Node syntax и `git diff --check` — PASS.
- Повтор после удаления legacy-кода: профильные backend-тесты — PASS, 29/29;
  frontend contract-тесты ADM-STATUS-01/PROGRAM01 — PASS, 5/5.
- Первые вызовы `npm run test:backend` и несуществующего `npm run test:frontend` в worktree —
  FAIL инфраструктурно (нет локальной `.venv`, script отсутствует); эквивалентные прямые
  команды выше выполнены и PASS. Первый PG-вызов в sandbox — FAIL `Operation not permitted`,
  разрешённый повтор к тому же localhost owned DB — PASS.
- CI, merge, deploy, test-stand readback и human visual acceptance текущего 1C — `NOT_RUN`.
