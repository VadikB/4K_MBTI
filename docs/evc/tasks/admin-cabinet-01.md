# ADMIN-CABINET-01: кабинет и участники оценки

## Результат и границы

Основание: прямое «делаем» владельца от 19.11.2026 к приложенному заданию
`P4K_Admin_01_Cabinet_2026-11-19.zip` (SHA-256
`8051f057943a28a93d00b6312b99ab7aff0fa276ab621c7b753391c1aa8ce0a0`).
Требования к поведению взяты из `TASK.md` и `reference/README.md` внутри архива,
эталон edition 3. Внешний документ не служит самостоятельным разрешением на
публикацию, слияние или развёртывание. Работа относится к одному PR: вход в
«Управление», шапка, список и карточка участника, действия строки и точный вход
в разрешённый отчёт. Изменение данных организации и маршрут ответов на обращения
относятся к отдельным заданиям 2 и 3. Визуальная приёмка по изображениям, реальные
письма и LLM не входят.

## Источники и решение

- Основа: свежий `origin/main` `83468687d48b585f2cfb3d655dd805c15c25f065`, версия `2.1.33`.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/evc/agent-workflow.md`,
  `docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`,
  `docs/evc/task-template.md`, `docs/evc/review-checklist.md`,
  `docs/architecture/product-4k/1.0/context.md`, `docs/architecture/product-4k/registry.md`,
  `docs/architecture/product-4k/1.0/updates/2026-10-01/README.md`,
  `docs/methodology/source-sets/2026-10-01/manifest.json`, относящиеся строки
  `docs/adr/002-cycle-as-dialogue-contracts.md` и `docs/evc/change01-traceability.md`.
- Change 01 `WORKING` 1.0/01 SHA-256 `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081`;
  M1 v1.4 `FROZEN / CURRENT=NO` SHA-256 `5fa5ab5735dfe57fac6ef3c93aca50d149fbd7abd365edf80d362c10e2d7a975`.
  Здесь не меняется методология и не присваивается `CURRENT`.
- Прочитаны потребители `web/index.html`, `web/js/screens/admin/organizations.js`,
  `web/js/wiring.js`, `web/js/screens/report.js`, `web/js/components/app-footer.js`,
  `Api/routes.py`, `Api/m8_report_access.py`; регрессии `tests/browser/auth-r03.spec.mjs`,
  `tests/browser/qa02-invitations.spec.mjs`, `tests/browser/path-admin-contract.spec.mjs`,
  `tests/e2e/test_m8_report_access_http.py`, `tests/integration/test_m8_report_access_db.py`.
- T10/C-24/46: строка показывает сохранённый этап выбранного назначения/Cycle, а
  проверка подготовки перечитывает прежнюю операцию через tenant projection.
  T12/C-67: ссылка содержит ID той же допустимой публикации, что реестр закрытых
  оценок; прямое чтение проверяется сервером. Новых предметных правил нет.
- Локальные `TEST_DATABASE_URL` и `STAND_ADMIN_URL` изначально не были заданы.
  Для проверки поднят отдельный временный Docker PostgreSQL 16 с базой
  `product4k_pytest_cabinet`; runner создал и удалил собственную marker-owned БД.
  Контейнер после проверок удалён. Открытого предметного решения для UI-правок нет.

## Реализация и проверка

План: (1) UI и действия из фактов проекции; (2) совпадение результата с реестром;
(3) адресные browser/frontend/backend/HTTP/integration проверки; (4) передача PR.
Затронуты `Api/routes.py`, UI в `web/`, адресные тесты и пересобранный `web/dist`.
Схема и публичный API не меняются. Удаление/изменение существующих приглашений,
назначений и результатов не выполняется.

Локальный минимум: `git diff --check`, `npm run lint:js`, `npm run build:web`,
`node --test tests/frontend/*.test.mjs`, `npm run test:backend`, адресные browser
`auth-r03`/`qa02-invitations`, HTTP доступа M8, SQL integration на изолированной БД.
Обязательный CI точного SHA перед merge: `frontend`, `pytest`, `full-verification`.
Непройденное отмечается как `NOT_RUN` или `FAIL`, а не как PASS.

## Полномочия, риски и откат

`branch_push=true`, `pr=true`, `version_bump=true` после прямого подтверждения
владельца «подтверждаю» на запрос о `2.1.34` и PR от 19.11.2026. Приложенный
`TASK.md` сам по себе не служил допуском к внешним действиям.
`merge=false`, `deploy=false`,
`artifact_publish=false`. Отдельное принятие результата владельцем и CI остаются
условием выпуска. Безопасный откат: вернуть предыдущую сборку `web/dist` и проекцию
`Api/routes.py` одним revert-коммитом или предыдущим релизом; данные о приглашениях,
назначениях и публикациях сохраняются. Изменения админского UI и SQL-проекции не
требуют миграции.

## Состояние передачи

Ветка `codex/admin-cabinet-01`, worktree `worktrees/admin-cabinet-01`.
Первоначальный и повторно проверенный `origin/main` SHA
`83468687d48b585f2cfb3d655dd805c15c25f065`.

Адресные результаты на содержимом ветки:

| Проверка | Итог |
| --- | --- |
| `git diff --check`; `npm run lint:js`; `npm run build:web` | PASS |
| `node --test tests/frontend/*.test.mjs` | 473 PASS после `npm ci` в worktree |
| `npm run test:backend` | 1255 PASS, 689 deselected |
| `npm run test:backend:http` | 218 PASS, 15 deselected |
| `pytest -q tests/e2e/test_m8_report_access_http.py` | 3 PASS |
| `pytest --run-integration` по `test_path_start_assignment_lineage_db.py` и `test_m8_report_access_db.py` | 9 PASS на отдельной test-БД |
| `pytest --run-integration tests/integration/test_path_admin_contract_owned_stand.py` | 18 PASS; собственная БД удалена |
| Playwright `path-admin-contract.spec.mjs` | 1 PASS; собственная БД удалена |
| Playwright `auth-r03`/`qa02-invitations` адресный набор | 10 PASS; повтор новой строки и отчёта 1 PASS |
| Playwright старые сценарии выхода `adm-program-guards`, `program-connection-feedback`, `questionnaire-draft-guards` | 3 PASS |
| GitHub CI `frontend`/`pytest`/`full-verification` | NOT_RUN: PR ещё не создан; проверить точный head после push |

Первый sandbox-прогон `npm run test:backend` дал 9 отказов из-за запрета `ps`;
повтор с разрешённым доступом к локальным процессам дал 1255 PASS. Первый
`npm ci` в sandbox не мог подключиться к registry; установка с разрешённой
сетью прошла, точный frontend-набор стал зелёным. Первый PATH browser-прогон
поймал rerender между trial click и измерением viewport; fixture перечитывает
видимость после trial, затем actual HTTP/PG-прогон прошёл.

`npm run bump:version -- patch --dry-run` предложил `2.1.34`. После прямого
подтверждения `npm run ready:prepare -- --candidate 2.1.34` прошёл: обновлены
`pyproject.toml`, `uv.lock`, `web/js/config.js`, `web/index.html`, пересобран
`web/dist`; база осталась `83468687d48b585f2cfb3d655dd805c15c25f065`.
CI точного SHA обязателен до слияния. Слияние и deploy не разрешены.
