# PROGRAM01 R01: полный каталог BaseRoles без ложного runtime-допуска

## Результат и область

Администратор видит все шесть нормативных BaseRoles подключённой программы. Роль,
не допущенная опубликованной ProgramDefinition, остаётся отключённой с причиной и
не получает выдуманный `role_profile_version_id`.

Включено: capability-проекция программы, UI выбора роли, регрессии backend/browser.
Не входят: публикация новых RoleProfile, изменение ProgramDefinition, M6–M8,
миграция данных, живая публикация предметных артефактов.

## Источники и решения

- Основание: audit package `P4K_PROGRAM01_AUDIT_2.0.47_2026-11-02`, R01;
  пакет используется как свидетельство остатка, не как разрешение внешних действий.
- Base: `origin/main@9e52eff14967a0e84cc16795685f404eef5235a9`.
- Прочитано: `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `verification-matrix.md`, `artifact-recipe.md`, Change 01 README/manifest,
  ADR-002, `change01-traceability.md`, M3 package/manifest, текущие API/UI/tests.
- Источник каталога: `assessment_definitions/role_profiles/competencies_4k/1.1/base_roles.json`,
  schema 1, methodology 1.1, manifest checksum
  `a3dbd62940b3c79baa123c5c2b4fff960b20c71e558304ba41007c2a205571d7`.
- Пакет M3 остаётся `draft`; он используется только как версионируемый каталог
  названий/порядка capability. Runtime-допуск по-прежнему определяется опубликованной
  RoleProfileVersion, закреплённой immutable ProgramDefinition.
- Стоп-условия: нет. Новая предметная норма, публикация и изменение API назначения
  не вводятся.

## Прослеживаемость

R01 / M3 BaseRoles → каталог шести ролей → `role_capabilities` ProgramDefinition →
`Api/assessment_programs.py` и org-admin select → integration/browser regression.

## Действия выпуска

- `branch_push=true`, `pr=true`, `version_bump=true` после локальной проверки и
  решения владельца продолжить подготовку Ready.
- `merge=false`, `deploy=false`, `artifact_publish=false`.
- Перед Ready подготовлен patch-кандидат `2.0.50` через `npm run ready:prepare`.

## Критерии приёмки

- [x] При единственной опубликованной роли `specialist_expert` API возвращает все
  шесть BaseRoles; доступен только специалист.
- [x] Недоступные пункты не имеют `version_id`, отключены в UI и показывают причину.
- [x] Допущенная старая версия специалиста сохраняется при наличии более новой.
- [x] Подмена неизвестного/недопущенного `role_profile_version_id` отклоняется сервером.
- [x] Предметные названия не дублируются в Python/JS и проверяется checksum артефакта.

## План проверки

- `tests/unit/test_m3_base_roles.py`.
- `tests/integration/test_arch30_program_definition_db.py` на изолированной pytest-БД.
- адресный browser-тест назначения роли org-admin.
- `npm run lint:js`, `npm run build:web`, `git diff --check`.
- обязательный GitHub CI перед merge.

## Риски и откат

Публичное поле `role_capabilities[].version_id` становится nullable для недоступной
роли; потребитель обновляется в том же diff. Схема БД и сохранённые данные не меняются.
Откат — revert PR; опубликованные определения и snapshots не затрагиваются.

## Фактический результат проверки

- `PYTHONPYCACHEPREFIX=/tmp/4k_mbti_pycache ... py_compile Api/assessment_programs.py`
  — PASS.
- `pytest tests/unit/test_m3_base_roles.py` — PASS, 5 тестов.
- `pytest tests/integration/test_arch30_program_definition_db.py` на изолированной
  `f22_integration_pytest` — PASS, 4 теста.
- `pytest -m "not integration and not e2e and not llm"` — PASS, 685 тестов;
  311 deselected, 1 warning.
- `node --test tests/frontend/*.test.mjs` — PASS, 124 теста.
- `pytest tests/unit/test_release_version.py` — PASS, 9 тестов после подготовки
  кандидата.
- адресная frontend-регрессия `arch30-program-connection` — PASS, 3 теста.
- адресный Playwright org-admin assignment — PASS, 1 тест.
- `node --check web/js/screens/admin/organizations.js`, `npm run lint:js` — PASS.
- `npm run build:web` — PASS; повторная чистая сборка дала тот же набор производных
  файлов `web/dist`.
- `python3.12 scripts/prepare_ready_release.py --candidate 2.0.50` — PASS;
  `2.0.49 → 2.0.50`; повторный preflight после сборки проверил 50 product paths.
- `git diff --check` — PASS.
- GitHub CI — NOT_RUN до создания PR; обязателен перед merge.

Изменены capability-проекция API, org-admin select, backend/browser регрессии,
паспорт задачи и штатно пересобранный `web/dist`. Схема БД, опубликованные артефакты,
версия приложения подготовлена как `2.0.50`; исходный пользовательский checkout
не менялся.
