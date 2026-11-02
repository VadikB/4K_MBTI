# PROGRAM01 R02: системная идентичность оценки и анкеты

## Результат и область

При подключённой ProgramDefinition администратор не вводит технический
`assignment_ref`: UI получает точный ключ из текущей связи программы и отдельно
показывает название, версию, роль и ключ оценки. Preview и confirmation анкеты
серверно проверяются против той же связи.

Включено: org-admin questionnaire UI, preview/confirm guard и регрессии.
Не входят: новая сущность кампании, миграция или переименование исторических
ключей, публикация ProgramDefinition, изменение M6–M8.

## Источники и решения

- Основание: audit package `P4K_PROGRAM01_AUDIT_2.0.47_2026-11-02`, R02.
- Base: `origin/main@553a550519069922ec1ff2e803caffc35fbcd8bc`.
- Прочитано: `README.md`, `CONTRIBUTING.md`, Change 01 README/manifest,
  ADR-002, `change01-traceability.md`, текущие ProgramDefinition,
  questionnaire API/UI/tests.
- Источник идентичности: immutable current ProgramDefinition connection
  (`organization_id`, `program_definition_id`, `assignment_ref`, configuration,
  roles); анкета сохраняет точные `organization_id`, `assignment_ref`, revision ID.
- Legacy-организации без ProgramDefinition не блокируются глобально.
- Стоп-условия: нет; новые предметные нормы и сущности не вводятся.

## Прослеживаемость

R02 / PROGRAM01-03 / AC06 / UI06 → current ProgramDefinition connection →
точный questionnaire scope → UI hidden key + backend preview/confirm guard →
frontend/browser/integration regression.

## Действия выпуска

- После явного разрешения владельца выполнены `branch_push=true`, `pr=true`:
  создан Draft PR #151 для обязательного CI.
- `merge=false`, `deploy=false`, `version_bump=false`, `artifact_publish=false`.
- Version bump выполняется отдельным preflight только перед переводом в
  `Ready for review`, а не для Draft PR.

## Критерии приёмки

- [x] Первая анкета подключённой программы создаётся без ручного ввода ключа.
- [x] Подходящая существующая revision выбирается только по точному ключу.
- [x] Черновик чужой оценки и совпадающее видимое имя не подменяют scope.
- [x] После смены программы UI использует новый ключ, старую revision не подтверждает.
- [x] Неподтверждённая/подтверждённая revision остаются различимы.
- [x] Сервер отклоняет подмену ключа в preview и stale revision в confirm.

## Проверки и откат

Фактический результат локальной проверки:

- Python compile (`Api/assessment_programs.py`, `Api/routes.py`) — PASS.
- `node --check web/js/screens/admin/organizations.js` — PASS.
- Integration ProgramDefinition, изолированная pytest-БД — 5 PASS.
- HTTP questionnaire confirmation — 3 PASS, 1 предупреждение Starlette.
- Browser `UX-ADM27` — 1 PASS; промежуточный FAIL был вызван устаревшим
  тестовым названием вкладки, селектор исправлен без изменения продукта.
- Первый Draft CI на `173cc15`: `frontend` и `pytest` — PASS,
  `full-verification` — FAIL; real-browser `ADM28` и `PATH29` ожидали ручное
  заполнение ставшего системным hidden `assignment_ref` и истекли по таймауту.
- После обновления acceptance-контракта на изолированной pytest-БД:
  `PATH29` — PASS, `ADM28` — PASS. Новый полный CI обязателен для нового head.
- Адресный frontend ProgramDefinition — 4 PASS; полный frontend — 125 PASS.
- Backend без `integration/e2e/llm` — 685 PASS, 313 deselected,
  1 предупреждение.
- `npm run lint:js`, `npm run build:web`, повторная сборка с теми же
  content hashes и `git diff --check` — PASS.
- GitHub CI — NOT_RUN до публикации PR; обязателен перед merge.

Схема БД и данные не меняются. Откат — revert PR; исторические revisions и
ProgramDefinition connections не изменяются.
