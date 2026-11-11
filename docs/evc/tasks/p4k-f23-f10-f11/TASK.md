# P4K-F23-F10-F11 — администратор и подключение программы

## Результат и область

Одна проверка и один кандидат для F23/F10/F11 и INT-AC01 из входного задания
`P4K-F23-F10-F11_Admin_Program_Connection.txt` (редакция 1.0, 11.11.2026).
Исправить подтверждённые расхождения без изменения предметных источников,
опубликованных определений, публичных контрактов, схемы или чужих данных.
F01/F02, полный EXEC/отчёты, реальные письма и LLM не входят.

## Исходное состояние и полномочия

- `git fetch origin main` 11.11.2026: `origin/main=aeea4e10014f9852e269eff0da8bf8cabe8d4427`;
  исходный checkout `bc63a8ee` на `codex/tg-student-channel-api` имел чужой diff и
  оставлен без изменений. Worktree `worktrees/p4k-f23-f10-f11`, ветка
  `codex/p4k-f23-f10-f11`, начата с чистого `aeea4e10`.
- Локальные чтение, реализация, синтетические проверки, commit и подготовка PR
  входят в прямой запрос пользователя. `branch_push=false`, `pr=false`,
  `merge=false`, `deploy=false`, `version_bump=false`, `artifact_publish=false`:
  отдельного прямого допуска на эти внешние/релизные действия в текущем чате нет.
- Вложенный «промпт запуска» задаёт требования, но его путь к другой рабочей
  копии и полномочия не переопределяют фактический workspace/запрос пользователя.

## Источники и решения

- Процесс: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, EVC workflow,
  verification-matrix, artifact-recipe, task-template, review-checklist.
- Контекст: Product 4K `1.0/context.md`, Registry, Change 01 `WORKING`
  (`1.0/updates/2026-10-01/README.md`, И-1/И-6/И-7), task manifest,
  ADR-002/003, `change01-traceability.md`, M1 v1.4 `FROZEN/CURRENT=NO`.
- M3 RoleProfile v1.0 `a3c085e4`, BaseRoles v1.0 `ab04e175`; M5 Methodology
  v1.1 `dc96f9b4`, CasePassport v1.1 `5560fec1` — SHA-256 совпали с manifest.
  Прочитаны адресные определения BaseRole «Специалист / эксперт» и M5 границы
  Case/AS/Interaction. PM-02 владеет ролью/контекстом; PM-03 готовит AS, PM-04
  исполняет. LU — Local Unit, Component — компонент навыка.
- `docs/evc/tasks/ac18-adm-1b-assignment-invitations.md`,
  `ux-adm19-02-admin-own-assessment.md`, `program01.md`, `program01-r01.md`,
  `program01-r02.md`, `program01-r03.md`, `adm-program-ui-fix-01/TASK.md` и
  `STATE.md`, `path-ac06-ac10-proof.md` — действующие границы UI/назначения.
- Точный опубликованный выпуск подтверждён сохранённым receipt
  `docs/evc/evidence/pilot-program-publication-execution/published-release-source.json`
  (SHA-256 файла `09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b`):
  `specialist_pilot@1.2`, `Пилот 4К · 9 кейсов`, configuration `11`, catalog `2`,
  definition checksum `b4e8270fd10436c417d7b40b8be8049dc2e9329f42a1ffa6d725877480d04718`.
  Это историческое доказательство выпуска, не новый readback TEST.
- `P4K.DEV.PRINCIPLES`, отдельный glossary и исходные карточки F23/F10/F11
  не найдены в предоставленном Git/Downloads. Принятые правила входного задания,
  ADR-003 и существующие контракты достаточны для технического исправления;
  новый предметный смысл не вводится.

## Прослеживаемость и стоп-условия

| Правило | Контракт/данные | Код | Проверка |
| --- | --- | --- | --- |
| Admin и participant независимы; повтор команды идемпотентен; UI подтверждает актуальный список | membership role/is_participant, access suppression, GET organizations | `Api/routes.py` add/remove-admin; `web/js/screens/admin/organizations.js` | `test_f01_role_isolation_db.py` HTTP/PG; combined browser |
| Published definition точна и неизменяема, retired только останавливает новые связи | ProgramDefinition, checksum, allowed roles | `Api/assessment_programs.py`, release CLI | `test_f10_publisher_db.py`, `test_program_publication_retirement_db.py` |
| A→B закрывает только текущую связь | connection operation/fingerprint/history, saved source bindings | `Api/assessment_programs.py` | `test_arch30_program_definition_db.py`, `test_pilot_start_admission_db.py` |
| Unknown/absent и личный маршрут не создают Cycle | UI state, scoped readback | `web/js/screens/admin/organizations.js` | frontend/browser и ADM28 actual HTTP/PG |

Стоп-условия рабочего цикла для локального исправления: нет. Нового предметного
решения, PM/LU-контракта, API, схемы, миграции, чувствительной передачи или формата
артефакта нет. Внешняя публикация, PR и TEST зависят от отдельного допуска/этапа.

## План и проверка

1. F23: права, участие, границы — код/HTTP/PG/browser.
2. F10: exact receipt, dry-run, synthetic publication, immutable/retired.
3. F11: UI connect, readback, A→B/replay/history, absent/unknown/late responses.
4. INT: свести один точный SHA, полный локальный минимум, ограничения и PR body.

Один активный шаг отражён в `STATE.md`. По матрице применимы backend, rights,
DB behavior и browser/UI: `git diff --check`, `npm run test:backend`, HTTP,
owned integration, frontend, lint/build, адресный browser. CI `frontend`,
`pytest`, `full-verification` требуется перед слиянием.

## Откат

Revert собственных изменений `Api/routes.py`, `web/js/screens/admin/organizations.js`,
собранного `web/dist` и регрессий; схема и данные не
мигрируют. Опубликованные артефакты и существующие подключения не трогаются.
