# ACCOUNT-DELETE-FIX-01: доступность отдельного удаления исключённого участника

## Основание и границы

- Задание владельца от 11.11.2026: исполнитель — Codex архитектора, ветка
  `codex/account-delete-fix-01`, worktree `ARCH_WORKTREES/account-delete-fix-01`,
  сессия `P4K-ACCOUNT-DELETE-01-ARCH`. Изменение назначения из сообщения владельца
  имеет приоритет над реквизитами в архиве. Один исполнитель изменений на ветке.
- Base `main` и проверенный `origin/main`:
  `e6b294e43811fb67afb695506f15547e5efc5f9e` (11.11.2026). После
  согласованного squash merge EXEC-FIX-05 (#208) интегрирован новый `origin/main`
  `ed141abbbbcc3f1033737b93282f58984a2156d4` (PATCH `2.0.95`);
  автоматический `deploy-test` для этого SHA прошёл:
  `https://github.com/VadikB/4K_MBTI/actions/runs/43008683483`.
- Владелец отдельно утвердил `version_bump` PATCH `2.0.96` для PR #207
  на базе `ed141abbbbcc3f1033737b93282f58984a2156d4`, commit/push
  кандидата и перевод в `Ready for review`. Merge и deploy этого PR
  данным решением не разрешены.
- Архив `P4K_ACCOUNT_DELETE_FIX_01_2026-11-11.zip`:
  SHA-256 `fc56089c0bd015483b6b3de667ac59b818a3ddb7d1d44e1c045f016ecd09b2f5`;
  13 записей `SHA256SUMS` проверены, 0 расхождений. Прочитаны `START.txt`,
  `TASK.txt`, `COMMON_WORKFLOW.txt`, `AUDIT.txt`, `evidence/users/FINDINGS.txt`,
  `results.json`, относящиеся строки `REMARKS_COMBINED_implemented_TASK.md` и
  глоссария `WORKING 2026-09-30`.
- Прочитаны `AGENTS.md`, `README.md`, `CONTRIBUTING.md`,
  `docs/evc/{agent-workflow,verification-matrix,artifact-recipe}.md`,
  `docs/architecture/product-4k/1.0/context.md`, `registry.md`,
  `1.0/updates/2026-10-01/{README.md,source.md}` (И-1/6/7),
  `docs/methodology/source-sets/2026-10-01/manifest.json`, `docs/adr/003-arch30-program-and-deletion-lifecycle.md`,
  `docs/evc/change01-traceability.md`, адресные API/UI/тесты.
  Change 01 `WORKING`, M1 v1.4 `FROZEN / CURRENT=NO`; правило M1 о сохранении
  материала и контекста не изменяется. Выбранный SourceSet не повышен до CURRENT.
  SHA-256 исходного PDF Change 01: `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081`;
  manifest: `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8`;
  ADR-003: `ed8d515ee5a9bfc67ee8c80f169e45a4750f1c6c6848991fc4c18e66f1abcfe2`.
- Результат: суперадмин видит сохранённый обычный аккаунт после исключения и
  выбирает существующий отдельный purge. Участие, административная роль и
  физическое удаление остаются разными действиями. Публичная схема ответа
  расширяется необязательным полем; БД и методологические пакеты не меняются.
- Не входят: EXEC-FIX-05, EXEC-CONTOUR-FIX-02, перенос участника,
  миграция БД, общие TEST/production пользователи, платные LLM, merge/deploy.

## Правило → контракт/данные → код → проверка

| Правило и источник | Контракт/данные | Фактический код | Проверка |
| --- | --- | --- | --- |
| #204 и задача: исключение сохраняет аккаунт и историю | `organization_memberships.is_participant=FALSE`; `users` и зависимости сохранены | `DELETE /members` без изменения поведения | owned Chromium/HTTP/PG, `test_path29_participant_owned_stand.py` |
| ADR-003: отдельный account purge с preview и fingerprint | `GET /admin/organizations` даёт отдельный `excluded_accounts`; прежний `detached_accounts` сохраняется | `Api/routes.py`, `Api/schemas.py`, `web/js/screens/admin/organizations.js` | SQL integration и owned Chromium/HTTP/PG |
| Администратор организации не получает глобальный purge | scope и `_require_superadmin`; protected/configured emails исключены | существующий RBAC и новая выборка только для superadmin | browser/HTTP 403, scoped response пуст |
| Admin-роль, чужая организация и действительно detached аккаунт различаются | `role`, `is_participant`, `organization_id` | SQL-критерий discovery, отдельные UI-разделы | SQL integration и browser/HTTP/PG |
| Физическое удаление только по существующей политике | preview, email, fingerprint, operation id, self-delete и test/ledger guard | существующий `POST /admin/users/{id}/purge` без изменения | browser/HTTP/PG: неверный email/stale отклонены, purge и replay PASS; прежние unit/HTTP/PG наборы |

## Решения, стоп-условия и откат

Стоп-условия рабочего цикла по смыслу, публичной совместимости, миграции,
источникам, артефактам, правам, откату и объёму: **нет**. Additive поле
`excluded_accounts` имеет default `[]`; `detached_accounts` не переопределяется.
Новый раздел показывается только суперадмину. Исключённый admin остаётся в
`admins`, а не превращается в ordinary purge candidate. Текущий account purge
по-прежнему окончательно решает допустимость через preview и серверные защиты.

Откат кода — revert коммита этого PR. Схема БД и опубликованные артефакты не
меняются. Уже выполненный реальный purge необратим; локальные проверки удаляли
только синтетическую marker-owned БД.

## Проверки 11.11.2026

Все локальные команды запущены из worktree; Python использует неизменённый
`/Users/vadim_bogachev/Developer/4K/.venv/bin/python`. PostgreSQL 15.16 —
отдельный локальный кластер на `127.0.0.1:55479`; test DB `account_delete_pytest`,
browser stand создаёт и уничтожает только собственную marker-owned
`product4k_pytest_*`. URL в отчёте без пароля.

| Команда/контур | Результат |
| --- | --- |
| `git diff --check` | PASS |
| `npm run lint:js` | PASS |
| `node --test tests/frontend/*.test.mjs` | 226 PASS |
| `npm run build:web` | PASS; `web/dist` собран из текущих `web/js` |
| `npm run ready:prepare -- --candidate 2.0.96` | PASS после интеграции EXEC-FIX-05: `2.0.95 → 2.0.96`, release gate 40 продуктовых путей |
| Python `pytest -m 'not integration and not e2e and not llm' -q` | 1055 PASS на исходном head; 1065 PASS после интеграции EXEC-FIX-05 |
| Python `pytest -m e2e tests/e2e -q` | 144 PASS |
| Python `pytest --run-integration -q tests/integration/test_arch30_membership_db.py tests/integration/test_purge_test_organization_db.py` на `account_delete_pytest` | 9 PASS |
| Python `pytest --run-integration -q tests/integration/test_path29_participant_owned_stand.py` на marker-owned stand | 1 PASS |
| Playwright `tests/browser/account-delete-owned.spec.mjs` на marker-owned stand | 1 PASS; actual Chromium/HTTP/PostgreSQL |

После интеграции `ed141abb` повторно выполнены lint, 226 frontend-тестов, сборка,
1065 backend, 144 HTTP, 9 адресных PostgreSQL integration, PATH29 (1 PASS) и
Chromium/HTTP/owned PostgreSQL (1 PASS). Конфликты были только в генерируемом
`web/dist`; он пересобран штатной командой из объединённых исходников.
Изолированный PostgreSQL после проверок остановлен и удалён.

Первый запуск `initdb` и integration в sandbox не получил доступ к shared memory
и localhost TCP соответственно; повторы с разрешённым локальным доступом прошли.
Первая сборка после удаления конфликтного `web/dist` остановилась из-за отсутствия
каталога; пустой каталог создан и штатная сборка прошла. Продуктовый код от этих
ошибок не менялся.

Первая адресная integration попытка выявила неполный synthetic fixture без
`users.full_name`: 1 FAIL, 8 PASS. Fixture дополнен полем, повторный прогон 9 PASS.
Первый вызов несуществующего `npm run test:frontend` завершился exit 1; действующая
команда проекта — `node --test tests/frontend/*.test.mjs`, 226 PASS.

В browser сценарии подтверждены: сохранение `users`, membership, сессии и числа
приглашений после исключения; точка выбора в UI; восстановление того же `users.id`
после повторного добавления; admin остаётся в `admins`; участник другой организации
не попадает в `detached_accounts`/`excluded_accounts`; truly detached control
остаётся в прежнем списке; scoped admin не видит глобальные кандидаты и получает
403 на purge; неверный email и stale fingerprint дают 409; успешный purge удаляет
пользователя, replay того же operation id идемпотентен; контрольные аккаунты
сохранены. Существующая PATH29 регрессия отдельно проверяет сохранённый пароль.

Общий TEST/production и реальные пользователи не затронуты проверками этой задачи.
Платные/provider вызовы не выполнялись. Для ACCOUNT-DELETE-FIX-01 остаются
CI точного PR head после перевода в Ready, человеческое review и отдельное
решение о merge/deploy в окне выпуска.
Рекомендуемый порядок: EXEC-FIX-05 → ACCOUNT-DELETE-FIX-01 → EXEC-CONTOUR-FIX-02.
