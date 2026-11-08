# AC18-ADM-1B — назначение оценки и приглашения

## Результат

Администратор видит понятные имя программы и роль, точные причины недоступности,
а после назначения или приглашения — достоверный результат по каждому выбранному
человеку без показа технического `assignment_ref` и без слепого повторного POST.

## Область

- Включено: B-AC01–09 редакции 1.1; UI идентичности и readiness; проверка batch-response;
  readback неизвестного исхода; адресная регрессия существующих серверных контрактов.
- Не входит: изменения формы/confirm 1A; почтовая история и lifecycle 1C; методология,
  публикация программ, схема БД, старт/Cycle/LLM, merge/deploy без отдельного разрешения.

## Контекст

- Основание: архив `P4K_ADM_1B_Assignment_and_Invitations_2026-11-08.zip`,
  `START_CODEX.txt`, `TASK.txt`, редакция 1.1 от 08.11.2026.
- Значимые точки входа: `web/js/screens/admin/organizations.js`, `Api/routes.py`,
  `tests/frontend`, `tests/browser`, `tests/e2e`, `tests/path_admin_contract_checks.py`.
- Архитектура/ADR: Product 4K context 1.0, Registry, Change 01, ADR-002;
  PM-02 владеет Role/Context, административный UI только представляет серверные факты.
- Существующие контракты: `assessment_programs.resolve`,
  `questionnaire_sources.assignment_readiness`, scoped assignment operation/bindings,
  personal invitation operation/statuses, member projection.
- Применимый комплект: Change 01 WORKING; M1 v1.4 FROZEN/CURRENT=NO; M3/M4 пакеты
  используются как понятийный источник, runtime-публикация не меняется.
- Прослеживаемость: TASK B-01/B-02 → public program/role/readiness → renderer → browser/frontend;
  B-03/B-05 → assignment batch contract → HTTP/PG + UI result; B-04/B-06 → operation readback
  и invitation response matching → browser/frontend + существующие HTTP tests.
- Предметные артефакты и published snapshots не изменяются; reference архива в Git не переносится.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, EVC workflow/matrix/artifact recipe,
  Product 4K context/Registry/Change 01/manifest, адресные M3/M4 упоминания, архивные
  `TASK`, `CURRENT_TASK_STATE`, `DECISIONS`, `BASELINE_2.0.83`, `WORK_MATRIX`,
  `MESSAGE_MATRIX`, `VISUAL_ACCEPTANCE`, `SOURCES`, UX-ADM27-03/04, PILOT31-03,
  PROGRAM01-R02 excerpt и ADR003 snapshot.
- База: `origin/main` = `0c59577d68b3b36de9df4a2134ccb22acca034e4`, version 2.0.83;
  SHA256 всех файлов архива PASS. 1A уже включён и не переделывается.
- Принято владельцем: программа «Пилот 4К · 9 кейсов»; видимая BaseRole, включая
  «Специалист»; самоназначение org-admin в своей организации; разделение назначения,
  приглашения и старта; конкретные причины отказа. D1/D2 не повышаются до нормы.
- Стоп-условия: отсутствуют для UI/контрактного остатка; внешняя визуальная приёмка,
  CI, merge и deploy остаются отдельными статусами, а не блокируют локальную реализацию.
- Требуется решение владельца: нет для реализации; потребуется отдельное разрешение
  только на push/PR/merge/deploy/version bump.

## План и состояние

- Завершено: проверены архив, контрольные суммы, base SHA, границы 1A/1B/1C;
  реализованы identity/readiness, per-person results, invitation batch validation и
  assignment readback; добавлены адресные browser-регрессии; frontend/HTTP PASS.
- Активный шаг: PATCH-кандидат `2.0.84` подготовлен каноническим preflight;
  требуется commit/push и повторный обязательный CI точного SHA.
- Следующий шаг: после успешного CI перевести Draft PR в Ready for review;
  human visual acceptance, merge и deploy остаются отдельными решениями.
- Ветка / base / head: `codex/ac18-adm-1b` / `0c59577d` / локальный review-ready commit
  `AC18-ADM-1B clarify assignment outcomes` (точный SHA — в итоговой передаче).
- Передача: обновлять этот раздел после каждого смыслового шага.

## Действия выпуска

- `branch_push=true`
- `pr=true` (Draft PR #195)
- `merge=false`
- `deploy=false`
- `version_bump=true` (`2.0.83` → `2.0.84`, PATCH)
- `artifact_publish=false`
- Основание: прямое разрешение пользователя 08.11.2026 на push/PR и продолжение
  release-подготовки; по правилам репозитория небольшое продуктовое изменение получает
  непосредственный PATCH-преемник базы, то есть `2.0.84`. Merge и deploy не разрешены.

## Ограничения и риски

- Совместимость: публичные API и сохранённые assignment/source bindings сохраняются.
- Данные и миграции: схема не меняется; integration только на owned test/pytest БД.
- Безопасность: никаких production/test секретов, PII и реальных писем в evidence.
- Внешние сервисы/LLM: не нужны; mail — controlled sink; LLM=0.
- Риск: потеря ответа требует readback той же операции/факта, не нового operation id.

## Критерии приёмки

- [x] B-AC01–02: понятная программа/роль и конкретные readiness-сообщения без raw ref.
- [x] B-AC03–06: точный результат по людям, защита partial/extra/duplicate и unknown readback.
- [x] B-AC07–08: права, stale/payload conflict и exact source bindings сохранены адресными HTTP-тестами.
- [x] B-AC09: автоматизирован desktop/mobile маршрут; human visual acceptance остаётся отдельно.
- [x] Новое предметное содержание не встроено в исходный код или генератор пакета.
- [x] Опубликованные snapshots и пакет подготовки/старта не изменены.

## План проверки

- Frontend: адресные Node tests, `node --check`, `npm run build:web`.
- Browser: адресные Playwright сценарии программы/назначения/приглашения и mobile.
- HTTP/integration: существующие assignment/invitation tests; owned PostgreSQL runner
  по matrix при наличии безопасного контура.
- Общие: `git diff --check`, review-checklist; CI до merge, но не подмена локальных проверок.

Фактические результаты 08.11.2026:

- `shasum -a 256 -c SHA256SUMS.txt` — PASS, 43/43 файла архива.
- `node --test tests/frontend/*.test.mjs` — PASS, 155/155.
- `pytest tests/e2e/test_adm27_assignment_http.py tests/e2e/test_r03_invitation_http.py -q` — PASS, 28/28.
- Адресный Playwright 1B — PASS, 4/4; mobile geometry включена в assignment-сценарий.
- `npm run build:web`, `node --check`, `git diff --check` — PASS.
- Draft CI исходного SHA `d7bdcbc8`: PASS обязательных `frontend` и `pytest`;
  `deploy-test` и полный draft-only workflow штатно SKIPPED.
- `npm run ready:prepare -- --candidate 2.0.84` — PASS против свежего
  `origin/main=0c59577d`, версия `2.0.83` → `2.0.84`, frontend пересобран.
- Реальная owned PostgreSQL integration — PASS: outer runner 1/1, child actual
  HTTP/PG checks 18/18; новая `product4k_pytest_*` БД, owner marker подтверждён,
  `database_absent=true`, `state_absent=true`, `force=false`. Временный PostgreSQL 16
  работал в Docker tmpfs и удалён; рабочая БД и `.env` не использовались.
- CI точного candidate SHA — NOT_RUN до push; deploy/test-stand/human visual acceptance —
  NOT_RUN, соответствующие действия не выполнялись.

## Откат

Совместимый revert UI/тестового коммита; созданные назначения, пользователи,
приглашения и результаты не удаляются и не мигрируются.
