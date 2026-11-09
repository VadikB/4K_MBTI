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
- Human visual acceptance владельца пройдена на кандидате `fc4b903c`; владелец
  разрешил PATCH `2.0.85`, полный preflight, push и PR 09.11.2026. Текущий шаг —
  релизный кандидат и обязательный CI; merge/deploy требуют отдельного решения.
- Ветка: `codex/ac18-adm-1c-status-history`; base/head до изменений: `65a62aca…`.
- Для этапа до визуальной приёмки действовали `branch_push=false`, `pr=false`,
  `version_bump=false`. После прямого ответа владельца: `branch_push=true`, `pr=true`,
  `version_bump=true` для PATCH `2.0.85`; `merge=false`, `deploy=false`,
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
- Human visual acceptance владельца на локальном кандидате `fc4b903c` — PASS.
  CI, merge, deploy и deploy/test-stand readback — `NOT_RUN`.

## Кандидат визуальной приёмки · 09.11.2026

- Fresh base: `origin/main@61f94edfb7db5c382b8d327aca232d3ea79b7c20`; общий предок
  ADM-1C и main — `65a62aca6b5f3fb870826a7f41977a4fd0f3b590`.
- После базы в main добавлен один процессный commit `61f94edf` (PR196). Пересекались
  `Api/routes.py`, `Api/schemas.py`, отчёты 1А/1Б, browser/e2e tests и generated
  assets; `git merge-tree` не показал content conflicts. Выполнен локальный merge,
  чужой commit сохранён без переписывания.
- Owned stand: PostgreSQL 16 в отдельной БД `product4k_pytest_*` с marker,
  localhost `127.0.0.1:18531`, provider disabled, controlled `@example.test`;
  рабочая БД/.env, реальные письма и LLM не использовались.
- Воспроизводимый seed: `scripts/seed_adm1c_visual_acceptance.py`; 14 участников,
  приглашения queued/sending/error/expired/revoked/used, назначение, acquaintance,
  preparing/failed, active, processing/failed, ready Report и два поколения истории.
  Синтетические M8-строки предназначены только для визуального предъявления; права,
  readback и сохранение отдельно проверяются actual HTTP/owned PG тестами.
- Визуальный self-check: desktop Chromium/IAB — PASS для входа, сводки,
  статусов/срока/пояса, read-only processing и карточки истории. Владелец подтвердил
  human visual acceptance кандидата `fc4b903c` 09.11.2026. Физическое устройство,
  отдельное доказательство 200% zoom и deploy readback не проверялись.
- Найден и исправлен дефект: старое отменённое поколение перезаписывало текущий этап
  нового поколения с тем же `assignment_ref`. Newest-first проекция теперь сохраняет
  первое поколение; регрессия добавлена в `test_admin_assessment_stage.py`.

## Матрица критериев пакета 1В

| Критерий | Происхождение | Фактическое поведение | Проверка | Статус | Остаток |
| --- | --- | --- | --- | --- | --- |
| C-AC01 · 33 строки | Существующие stage/mail guards + ADM-1C проекция | Один главный этап; mail/link/registration вторичны; unknown не становится missing | unit stage matrix, frontend contract, synthetic PG route, owner visual acceptance | PASS | — |
| C-AC02 · ранние/поздние этапы | Поздние Cycle/Report существовали; ADM-1C довёл ранние и loading/error | Active/processing/report выше старого письма; отсутствующий exact assignment поясняется отдельно | 12 unit + 5 frontend + self-check | PASS | — |
| C-AC03 · карточка/история | used/revoked API существовал; история и generation priority — ADM-1C | Точное текущее назначение, Cycle и revoked→new history; новое поколение не затирается старым | owned PG UI + новая unit regression + owner visual acceptance | PASS | — |
| C-AC04 · processing/read rights | Endpoint существовал; handler/dialog — ADM-1C | Read-only пояснение; нет admin start/resume/retry; Report только при access | browser AC18 + self-check dialog | PASS | Direct 403 покрыт существующими access tests |
| C-AC05 · срок/lifecycle | Guards accept/revoke/repeat существовали; factual expiry — ADM-1C | Реальный `expires_at`, GMT+3, used/revoked/expired и понятный delivery state | browser AC18 + owned PG UI | PASS | Реальная доставка не входит |
| C-AC06 · ST-R1 | Ранее реализовано | Открытие/закрытие/Escape не создаёт mutation; destructive actions отдельно | frontend contract + прежняя ST-R1 regression | PASS | Не переписывалось |
| C-AC07 · ST-R3/scope/late context | Ранее реализовано; exact operation guards дополнены ADM-1C | Identity/org/assessment/generation изолированы; поздний ответ не попадает в другой context | e2e + 6 Playwright AC18 | PASS | — |
| C-AC08 · самостоятельный маршрут | Новый ADM-1C fixture/stand | Готовый вход и 14 состояний без SQL/создания пользователей владельцем | technical self-check desktop actual HTTP/PG + owner visual acceptance | PASS | Физическое устройство не проверялось |
| C-AC09 / ADM-09 | Release facts 1А/1Б существовали; отчёты актуализированы ADM-1C | CI/release/history отделены от actual PG и human acceptance | task reports + текущий owned PG route + owner visual acceptance | PASS | CI/deploy readback, 200% и физическое устройство — NOT_RUN |
| C-AC10 / ADM-10 | Новая ADM-1C modern projection | M5 Cycle/M8 Report counters; started/closed; нет legacy index/fake zeros; pre-M1–M8 не учитывается | unit metrics, owned PG, dashboard self-check | PASS | Физическая очистка рабочей БД — отдельная операция |
| C-AC11 / B-RES01 | Остаток 1Б исправлен ADM-1C | Confirmed POST не отменяется failed refresh; unknown подтверждается только exact receipt; stale/null не успех | HTTP/e2e, owned PG, Playwright cases 1–3 + owner visual acceptance | PASS | — |
| C-AC12 / B-RES02 | Остаток 1Б исправлен ADM-1C | Per-person queued/error/uncertain/registered; без raw operation_id и provider=0; unknown имеет readback | HTTP/e2e, owned PG, Playwright cases 4–6 | PASS | Реальная почта не входит |

После интеграции main и исправления generation priority: backend profile — 30/30 PASS,
frontend contract — 5/5 PASS, Playwright ADM-1C — 6/6 PASS, `git diff --check` — PASS.
Human visual acceptance владельца на `fc4b903c` — PASS. Полный CI, push, PR и deploy —
`NOT_RUN`; физическое устройство и отдельное доказательство 200% zoom — `NOT_RUN`.

## Release-preflight после визуальной приёмки · 09.11.2026

- `git fetch origin main` — PASS; `origin/main` остаётся на `61f94edfb7db5c382b8d327aca232d3ea79b7c20`.
- `scripts/check_release_version.py --base-ref origin/main` ожидаемо остановлен: product paths
  изменены, а версия кандидата остаётся `2.0.84`.
- `scripts/prepare_ready_release.py --base-ref origin/main --release-type patch` подтвердил
  требование одобренного кандидата `2.0.84 → 2.0.85` и завершился с gate-кодом 2 до любых
  изменений версии, сборки и публикации.
- Version bump, push, PR, CI и deploy не выполнялись; для следующего внешнего этапа требуется
  отдельное разрешение владельца. Это исторический результат preflight до ответа владельца.

## Подготовка PATCH 2.0.85 и локальный review · 09.11.2026

- Прямое разрешение владельца: PATCH `2.0.85`, полный preflight, push и PR в существующей
  ветке; merge/deploy и публикация предметных артефактов не разрешены.
- Fresh `origin/main@61f94edfb7db5c382b8d327aca232d3ea79b7c20` совпал с merge-base.
  `scripts/prepare_release.py patch --candidate 2.0.85 --dry-run` — PASS: четыре
  version-файла. `npm run ready:prepare -- --candidate 2.0.85` — PASS: версия,
  `web/dist` и release gate. `scripts/check_release_version.py --base-ref origin/main`,
  `git diff --check` — PASS.
- `npm run lint:js` — PASS; `node --test tests/frontend/*.test.mjs` — PASS 155/155;
  backend unit — PASS 977/977; HTTP/e2e — PASS 110/110; Playwright ADM-1C — PASS 6/6.
- PostgreSQL 16 `product4k_pytest_release` на отдельном localhost: `TEST_DATABASE_URL`
  содержит `pytest`, `STAND_ADMIN_URL` указывает на maintenance DB этого же контейнера;
  рабочая БД и `.env` не использовались. ADM-1C SQL — PASS 2/2.
- Полный первый integration-прогон выявил устаревшее ожидание «Среднее время
  прохождения» в `scripts/test_stand_smoke.py`; 58 PASS, 1 FAIL, далее остановлен
  для исправления. Smoke теперь проверяет современную Cycle/Report-сводку; повтор
  actual HTTP/PG на двух пустых owned-стендах — PASS 1/1. Первый sandbox-вызов
  к localhost завершался `Operation not permitted`; разрешённый повтор к той же
  owned-БД прошёл. Полный локальный повтор — 67 PASS, затем остановлен без новых
  ошибок после профильного PASS; оставшиеся сценарии — NOT_RUN локально. Обязательный
  полный CI integration/browser ожидается на Ready PR для точного head.
- Реальные письма и LLM — NOT_RUN по границам задачи. `gh` CLI не авторизован;
  Git push dry-run через настроенный HTTPS credential — PASS. PR создаётся через
  авторизованный браузер после фиксации кандидата.
