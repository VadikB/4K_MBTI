# ADM-FIX-01 — готовность назначений и подготовка

## Результат и границы

Задание владельца: `/Users/vadim_bogachev/Downloads/P4K_ADM_FIX_01_Readiness_2026-11-20.md`, прочитано целиком.
Исходная база свежего `origin/main`: `e4bc5c88c45b775a6406f034750e75aa1e4c47be`, приложение 2.1.40.
Ветка `codex/adm-fix-01-readiness`, текущий worktree
`/Users/vadim_bogachev/Developer/4K/worktrees/adm-fix-01-readiness`.
Один результат: HTTP чтение/сохранение анкеты после знакомства и точная проекция
готовности/подготовки назначения. Без изменения схемы, API, сохранённых snapshots,
методологических артефактов, прав и правил допуска к старту.

Флаги текущего этапа: branch_push=true, pr=true, version_bump=true,
merge=true и deploy=true на TEST после обязательных проверок и review;
artifact_publish=false. Визуальная приёмка — владелец.


Текущий этап: разрешённый владельцем выпуск ADM-FIX-01 на TEST через PR #258.
Ветка синхронизирована с `origin/main=fa55e1ef` (2.1.41); кандидат проверок —
`94b001254cfd3f86f4b8c753763b16489640be8d`. CI frontend/pytest этого SHA прошёл.
Локально backend 1305 PASS, HTTP 218 PASS, frontend 476 PASS, harness 66 PASS,
17 адресных SQL/HTTP PASS. Полный integration нового основания завершён: 484 PASS / 2 explicit llm SKIPPED.
Read-only Ready preflight определил следующий PATCH 2.1.42 и завершился exit 2
без изменения версии. Затем владелец явно разрешил выпуск на TEST; готовится PATCH 2.1.42.

## Источники и решения

Прочитаны README.md, CONTRIBUTING.md, AGENTS.md текущей базы; docs/evc/{agent-workflow,
verification-matrix,artifact-recipe,task-template,review-checklist,decision-register}.md;
Product 4K context/Registry, Change 01 README/source.md И-1–3 и И-6 и task manifest от 2026-10-01;
ADR-002 C-23/C-24, change01-traceability T01; M1 v1.4 README и source.md §M1.4 (FROZEN/CURRENT=NO),
M4.Context v1.0 зеркало §M4.4; задачи ux-adm01-organization-data-readiness,
ux-w02-acquaintance, ux-w02-add02-add03; потребители и адресные тесты.

M4.4 → сохранение версий источников → C-23/C-24, PM-02 → точные source bindings,
confirmation и PersonalizedProfile → late_readiness и административная проекция →
SQL/HTTP регрессии. PM-03 выполняет подготовку; PM-04 допускает старт по существующему
плану и первой AS. Нормы M1/Change01 не меняются, CURRENT не назначается.
Внешний аудит по ChatGPT Library не загружался; ТЗ содержит
воспроизводимые симптомы и точные ссылки на код. Для исправления достаточно кода,
действующих контрактов и регрессии. Новых предметных решений не требуется.
Все восемь стоп-условий рабочего цикла: нет, область исправления задана владельцем,
контракты/схема/данные не меняются, откат — revert кода.

## План

1. Разведка — завершена: отсутствует context ID; используется org latest вместо pinned;
   preparation выбирается по user_id без lineage.
2. Воспроизведение регрессий на базе — завершено (KeyError/HTTP 500).
3. Исправление и адресные SQL/HTTP проверки — завершено, 17 PASS.
4. Исходная реализация: backend 1301 PASS, HTTP 218 PASS, integration 484 PASS / 2 llm SKIPPED. Draft PR #258 создан.
5. Продолжение по команде владельца «продолжаем»: main синхронизирован; адресный frontend regression test исправлен; быстрый CI прошёл; полный локальный integration прошёл (484 PASS / 2 llm SKIPPED). Решение о выпуске получено; выполняются PATCH/Ready, полный CI и условный merge/deploy на TEST.

## Проверки

План: `git diff --check`, `npm run test:backend`, `npm run test:backend:http`,
`npm run test:backend:integration`; адресно test_questionnaire_sources_db.py и
 test_path_start_assignment_lineage_db.py. PostgreSQL 15.16, новый экземпляр localhost:55481,
пустые БД adm_fix_01_pytest и agent4k_pytest, dotenv disabled, внешние LLM/почта не используются.
CI перед merge обязателен; локальный PASS его не заменяет.

## Откат и риски

Revert коммита исправления возвращает прежние чтения. Миграций и изменения конфигурации
нет, immutable profiles/checksums сохраняются. Возвращаются известные дефекты чтения.
Уже начатая оценка продолжает использовать прежний snapshot. Управляющие документы
не меняются; traceability задачи ведётся здесь.

## Идентичность выбранных источников

| Файл | SHA-256 |
| --- | --- |
| ТЗ ADM-FIX-01 от 20.11.2026 | `493e574de3544e8986d310df6b4ec85688c9ec5cd12de07fdd6f39f4bbec21dd` |
| M1 v1.4 source.md | `282e69b87585c28b52327e657d71a620c15842f7ade134467788252829833299` |
| M4.Context v1.0 m4_context_source.md | `9af86011c1ea1bef12058700bdd345c5cee335bbc6ec4d392fcfc4f3e5709fd1` |

Change01 source.pdf: `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081`;
M4.Context оригинал v1.0: `07875e93ae422668b1b30cd60bc1c6140cae91db12b0b80ba4abca441cfe9291`
(выбранные записи task manifest, оригиналы не изменялись). Ссылка/выбор источника
отличаются от проверки runtime; техническое соответствие ниже ограничено ADM-FIX-01.

## Изменённые файлы и фактическое поведение

- `Api/questionnaire_sources.py`: для каждого участника читаются закреплённая редакция
  и полный результат assignment_readiness, включая context version ID и assignment ID;
  текущая анкета остаётся источником редактирования/будущих назначений. Счётчик профилей
  независим от нового черновика/публикации. Причины отсутствующих источников сохраняются.
- `Api/acquaintance.py`: missing context / несовпадающее назначение возвращают
  W02_PROFILE_ASSIGNMENT_SCOPE_MISMATCH вместо KeyError.
- `Api/admin_assignment_projection.py`: существующая SQL-проекция строки перенесена
  из routes; её joins Cycle/profile/legacy job/product operation используются и сводкой.
  Современная операция требует точные organization/user/assignment/revision/profile;
  совместимая старая — доказанную confirmation либо Cycle-связь. Более позднее
  неподвязанное confirmation не позволяет вернуться к прежнему профилю. При общей
  связке источников нескольких поколений legacy job остаётся неизвестным для
  назначения: одной profile ref недостаточно. Точный modern assignment_id решает
  эту неоднозначность; чтение старой операции по ID не меняется.
- `Api/routes.py`: использует общий SQL; readback routes и форматы API сохранены.
- `tests/integration/test_questionnaire_sources_db.py`: настоящие M4 snapshot/checksum,
  late_readiness и HTTP list/preview/read/confirm; реальные права и program validator;
  подменяется только lookup тестовой identity. Данные участников/confirmation синтетические,
  M4 создаётся действующим lifecycle, никакие resolver/readiness не заменены.
- `tests/integration/test_path_start_assignment_lineage_db.py`: общий SQL, современная
  очередь и legacy linkage, первая AS и запрет возврата к старому confirmation.
- `tests/unit/test_questionnaire_sources.py`: обновлены границы подставного repository
  для сводки; сохранено различие profile_binding и verification_error.

## Приёмочные сценарии

| Сценарий | Проверка / факт | Результат |
| --- | --- | --- |
| Список/preview после знакомства | На базе новые регрессии падают: KeyError organization_context_version_id; GET возвращает 500. После исправления HTTP list=200, preview=201 до/после confirmation, exact read=200, confirm=200; орган admin, superadmin, foreign=403 | PASS |
| Закреплённые источники | А готов по старой редакции после новой публикации; Б со своей новой привязкой добавляет второй ready. Профиль/строка/checksum А неизменны; несовпадающий профиль и отсутствие confirmation дают штатные категории | PASS |
| Подготовка назначения | queued/running exact операции согласуются с SQL строки; чужая организация/user/ref/id/revision/profile исключены; поздний legacy job старой оценки не влияет; два GET не увеличивают очередь | PASS |
| Допуск старта | completed preparation + prepared Cycle/READY plan без допущенной первой AS = start_blocked, action отсутствует. Существующий start gate не ослаблен | PASS |

## Локальное ревью

Нормы/предметные настройки не добавлены в Python. Миграций/удаления/перезаписи profiles
нет. Новые чтения не запускают очередь. Права проверяются прежними серверными routes.
Legacy без доказуемого lineage не объявляется активной подготовкой. Проверка прошлой
операции и report SQL сохранены; существующие тесты report publication проходят.
Визуальное представление владельцем пока не принято. Изменения UI/JS отсутствуют,
локальные frontend lint/build неприменимы; обязательный frontend CI сохраняется.

## Проверки реализации c4da229888a0fcb591b2e352f285366376a95c47

Синтетическая PostgreSQL 15.16 поднята с нуля в `/private/tmp/adm-fix-01-pg`,
localhost:55481, trust только для локального тестового экземпляра, данные UTF8.
Рабочие БД и `.env` не читались. Исходный Git-каталог с чужими изменениями сохранён.

| Команда | Результат / exit code |
| --- | --- |
| `git diff --check` | PASS / 0 |
| `PYTHON_DOTENV_DISABLED=1 npm run test:backend` | PASS / 0, 1301 passed, 708 deselected; повтор вне sandbox после PermissionError ps. Первые 2 unit failures — устаревшие тестовые adapters; исправлены и проверены |
| `PYTHON_DOTENV_DISABLED=1 npm run test:backend:http` | PASS / 0, 218 passed, 15 deselected |
| `PYTHON_DOTENV_DISABLED=1 TEST_DATABASE_URL=postgresql://adm_pytest@127.0.0.1:55481/agent4k_pytest .venv/bin/python -m pytest -q --run-integration tests/integration/test_questionnaire_sources_db.py tests/integration/test_path_start_assignment_lineage_db.py` | PASS / 0, 17 passed |
| `... .venv/bin/python -m pytest -q tests/unit/test_questionnaire_sources.py` | PASS / 0, 13 passed |
| Integration, EXEC-FIX-02 additional/retry на agent4k_pytest | PASS / 0, 25 passed. На adm_fix_01_pytest первый запуск остановлен guard фиксированного имени; новые fixtures не ослаблялись |

Один warning Starlette/httpx — существующая deprecation, не ошибка. Финальный полный
integration выполнен на поддерживаемом имени новой БД: 484 PASS / 2 SKIPPED / exit 0 (883.57 s).
Предыдущий общий прогон на adm_fix_01_pytest не объявляется успешным из-за guard.
Дополнительно прочитаны path-start-01 (lineage) и p4k-remain-01 TASK/CHECKS:
повторное назначение с теми же источниками не наследует чужую подготовку.

## Непроверенное на исходном implementation c4da2298

CI для точного head, Ready/release gate, browser/визуальная приёмка и выпуск — пока NOT_RUN.
Ready требует отдельного допуска на номер приложения; draft не означает выпуск.
LLM/реальная почта/публикация/merge/deploy не требовались и не выполнялись.
После завершённого локального integration: один draft PR после явного допуска; затем CI/review и решение владельца
на выпуск/номер и визуальную приёмку. Предметных открытых решений ADM-FIX-01 нет.

Повтор backend на неизменённом implementation commit `c4da229888a0fcb591b2e352f285366376a95c47`:
1301 PASS / 708 deselected / exit 0 (109.77 s). HTTP на том же commit:
218 PASS / 15 deselected / exit 0 (60.98 s). Позднейшие изменения этой карточки —
только запись доказательств; runtime и tests соответствуют этому commit.

## Финальный полный integration

`PYTHON_DOTENV_DISABLED=1 TEST_DATABASE_URL=postgresql://adm_pytest@127.0.0.1:55481/agent4k_pytest STAND_ADMIN_URL=postgresql://adm_pytest@127.0.0.1:55481/postgres npm run test:backend:integration`
→ **PASS / exit 0: 484 passed, 2 skipped, 1523 deselected**, 883.57 s.
Результат относится к implementation `c4da229888a0fcb591b2e352f285366376a95c47`;
пропущены только два explicit real-provider acceptance в tests/llm/test_m10_real_cycle_db.py
(строки 148/338). Все 17 адресных SQL/HTTP регрессий входят в этот полный прогон.
Первый общий прогон на неподдерживаемом имени БД: 458 PASS / 2 SKIPPED / 25 fixture
ERROR / exit 1; последующий адресный повтор 25 PASS и окончательный полный PASS выше
устранили причину без изменения guards. Первое sandbox-падение ps также устранено
повтором в разрешённой среде. Неразобранных локальных FAIL/ERROR нет.

## История main и кандидата до синхронизации

В начале и при воспроизведении `origin/main=e4bc5c88c45b775a6406f034750e75aa1e4c47be`.
При повторном fetch во время проверки main продвинулся до
`fa55e1eff21864448b0dcb88dd81cdbcbb2d9a56` (PR #257, M1/M6, 2.1.41).
`git diff e4bc5c88 origin/main -- Api/acquaintance.py Api/questionnaire_sources.py
Api/routes.py tests/integration/test_questionnaire_sources_db.py
 tests/integration/test_path_start_assignment_lineage_db.py` пуст: относящиеся к ADM-FIX-01
код/тесты в новом main не исправлены и не конфликтуют. Ветка сохраняет проверенную
исходную базу e4bc5c88; результаты локального набора не объявляются проверкой
непроверенного сочетания с новым M6. Перед Ready необходимы синхронизация main,
release preflight/номер и обязательный CI нового head/base.

Runtime/checks зафиксированы в c4da2298; следующий коммит содержит только этот отчёт.
Рабочий каталог: `/private/tmp/4k-adm-fix-01`. Локальная реализация/проверки завершены.
Следующие зависимости: CI, визуальная приёмка владельца,
решение о Ready/номере/выпуске.

## История блокировки внешней передачи

Автоматическая проверка отклонила команду push рабочей ветки и создания draft PR
в `https://github.com/VadikB/4K_MBTI`: запрос на реализацию в рабочей ветке не признан
явным разрешением передать приватный код этому destination. Команда не выполнялась,
push/PR отсутствуют. Запрашивается явное разрешение владельца на оба действия;
обход блокировки не предпринимался. Публикация не включала merge/deploy.

Очистка: созданный PostgreSQL `/private/tmp/adm-fix-01-pg` штатно остановлен;
`pg_ctl status` → `no server running` / exit 3 (ожидаемое подтверждение остановки).
Временная ссылка `.venv` удалена; рабочее дерево чистое. Текст draft PR подготовлен
в `/private/tmp/adm-fix-01-pr-body.md`, внешняя передача ожидает разрешения.


## Разрешение внешней передачи

20.11.2026 пользователь явно ответил «Разрешаю push и draft PR» на вопрос об отправке
готовой ветки `codex/adm-fix-01-readiness` (HEAD `94b7160f`) в
`https://github.com/VadikB/4K_MBTI` и создании одного draft PR. Это разрешение снимает
описанную выше блокировку публикации. Merge/deploy, Ready и номер приложения в этот
допуск не входят. Изменение после 94b7160f — только эта запись о разрешении;
implementation и результаты проверок не изменены.

## Фактическая передача после разрешения

- `git push -u origin codex/adm-fix-01-readiness` — PASS / exit 0: ветка создана
  в `https://github.com/VadikB/4K_MBTI`, исходный опубликованный HEAD `536ec618`.
- `gh pr create --repo VadikB/4K_MBTI --base main --head codex/adm-fix-01-readiness --draft ...`
  — FAIL / exit 4: GitHub CLI не авторизован (`gh auth login` required). PR не создан.
- Проверена доступность GitHub-плагина: `installed=false`. Браузерная попытка не
  дошла до создания PR: активная вкладка неоднократно менялась пользователем.
  Учётные данные из Git credential helper/файлов не извлекались.
- Прямое разрешение пользователя на push и один draft PR сохраняется. Следующий шаг:
  пользователь авторизует GitHub CLI командой `gh auth login` либо подключит GitHub;
  затем агент создаёт PR из готового body без повторного вопроса о разрешении.
  Пока PR отсутствует, CI не запущен. Merge/deploy не выполнялись.

Временный каталог `/private/tmp/4k-adm-fix-01` и временный PR body исчезли между
действиями. Коммиты не потеряны: worktree восстановлен из опубликованной ветки в
`/Users/vadim_bogachev/Developer/4K/worktrees/adm-fix-01-readiness`.
Проверенный runtime и tests не менялись. Текст PR сохранён рядом в
`docs/evc/tasks/adm-fix-01-pr-body.md`. Повторная тихая проверка `gh auth status`
вернула exit 1; доступ через GitHub CLI пока не восстановлен.

## Передача через встроенный браузер — завершена

По прямому указанию владельца «делай через встроенный браузер» 20.11.2026 создан
**draft PR #258**: https://github.com/VadikB/4K_MBTI/pull/258 .
Фактически проверены URL, заголовок, статус Draft и направление
`codex/adm-fix-01-readiness` → `main`. PR прикреплён к текущему чату Codex.
Описание содержит источник задачи, результат трёх сценариев, base/implementation SHA,
проверки, откат и незавершённые действия выпуска. При создании head был `5a25c55a`.

Отсутствие авторизации `gh` больше не блокирует передачу: PR создан через действующую
сессию встроенного браузера. Разрешение пользователя повторно не запрашивалось.
Implementation/tests соответствуют проверенному `c4da2298`; последующие коммиты —
документальные записи. Перед Ready сохраняются зависимости: синхронизация main,
номер приложения, release preflight, обязательный CI и review; визуальная приёмка —
владелец. Merge/deploy/publication не выполнялись.


## Продолжение 20.11.2026: синхронизация и CI

Владелец: «продолжаем» после создания draft PR #258. Продолжены проверка CI,
синхронизация рабочей ветки и исправление обнаруженной регрессии теста. Флаги
merge/deploy/version_bump/artifact_publish не изменены.

На head `5f5ba56d` CI run `44692593290`: pytest PASS, frontend FAIL (18 s),
Frontend regression tests: 475 PASS / 1 FAIL. Причина —
`tests/frontend/arch30-member-stage.test.mjs` ищет перенесённые SQL predicates
в routes.py. Обновляется чтение общего admin_assignment_projection.py с сохранением
проверок user/profile/organization/assignment и проверкой подключения SQL в routes.
Ни тест, ни assertions не отключаются.

`git merge --no-edit origin/main` — PASS, без конфликтов. Новое основание:
`fa55e1eff21864448b0dcb88dd81cdbcbb2d9a56` (2.1.41). Предыдущее доказательство
на c4da2298 сохраняется как история; для сочетания с новым M6 повторяются backend,
HTTP, integration и CI. Для frontend устанавливаются lockfile dependencies в собственном
worktree; первый локальный запуск без node_modules дополнительно дал MODULE_NOT_FOUND,
это недостаток локальной установки, а не отдельный дефект продукта.


### Проверки продолжения на 94b00125

- `npm ci` — PASS / 0 в собственном worktree, lockfile не изменён.
- `node --test tests/frontend/arch30-member-stage.test.mjs` — 5 PASS / 0.
- Адресные questionnaire/lineage на новой agent4k_pytest — 17 PASS / 0.
- `PYTHON_DOTENV_DISABLED=1 npm run test:backend` — 1305 PASS / 0, 110.08 s.
- `PYTHON_DOTENV_DISABLED=1 npm run test:backend:http` — 218 PASS / 0, 59.57 s.
- `npm audit --audit-level=high`, `npm run lint:js` — PASS / 0.
- `node --test tests/frontend/*.test.mjs` — 476 PASS / 0.
- Harness receipts — 66 PASS / 0.
- `npm run build:web`, `git diff --exit-code -- web/dist` — PASS / 0; bundle
  совпадает с текущим main, продуктовый JS не менялся.
- CI run `44694381565`, head 94b00125: frontend PASS, pytest PASS. Full verification
  run `44694381613` ожидаемо SKIPPED для draft; это не PASS полного CI.
- `npm run ready:prepare` без --candidate — exit 2, ожидаемый запрос разрешения
  PATCH 2.1.41 → 2.1.42; версия/артефакты не изменены.

Основание запроса будущего допуска: CONTRIBUTING.md «Коммиты и merge» — отдельные
флаги этапов; прежнее разрешение push и draft PR не включает merge/version_bump.
Все уже разрешённые локальные проверки и исправления выполняются до такого запроса.


### Итог продолжения и передача владельцу

Полный повтор на кандидате `94b001254cfd3f86f4b8c753763b16489640be8d` и основании
`fa55e1eff21864448b0dcb88dd81cdbcbb2d9a56`:

`PYTHON_DOTENV_DISABLED=1 TEST_DATABASE_URL=postgresql://adm_fix_pytest@127.0.0.1:55482/agent4k_pytest STAND_ADMIN_URL=postgresql://adm_fix_pytest@127.0.0.1:55482/postgres npm run test:backend:integration`
→ **PASS / exit 0, 484 passed, 2 explicit llm skipped, 1527 deselected**, 810.65 s.
Новая owned БД создана в отдельном PostgreSQL 15.16, `/private/tmp/adm-fix-01-followup-pg`,
localhost:55482. После окончания сервер остановлен: `pg_ctl status` →
`no server running` / exit 3 (ожидаемое подтверждение остановки). Ссылка .venv удалена.

Подтверждённый общий результат: backend 1305 PASS, HTTP 218 PASS, integration
484 PASS / 2 SKIPPED; frontend 476 PASS, harness 66 PASS, audit/lint/build/diff PASS.
CI на 94b00125: **frontend PASS, pytest PASS**, run
https://github.com/VadikB/4K_MBTI/actions/runs/44694381565 . Причина прежнего frontend
FAIL устранена без отключения проверки. Относительно main нет несвязанных продуктовых
изменений; синхронизация не добавляет M6-изменения в diff PR. Ни один runtime/source
артефакт ADM-FIX-01 после проверенного implementation не переписывался.

Следующий этап требует решения владельца: выпуск ADM-FIX-01 на TEST со следующим
PATCH (по текущему main — 2.1.42), Ready, обязательный полный CI, review и squash merge
со штатным deploy-test. До такого решения `version_bump=false`, `merge=false`,
`deploy=false`. Предварительные работы и все уже разрешённые проверки завершены.
Full verification в draft **SKIPPED**, не PASS; визуальная приёмка — владелец.
Откат прежний: revert собственного результата через PR, сохранённые snapshots не менять.


## Допуск выпуска на TEST — 20.11.2026

Пользователь явно ответил **«Разрешаю выпуск на TEST»** на вопрос:
«Разрешаете выпуск ADM-FIX-01 на TEST: следующий PATCH (сейчас 2.1.42), перевод PR #258
в Ready, полный CI и squash merge после проверок и review со штатным deploy-test?».
Это прямое поручение владельца для текущего результата, не инструкция из вложения.
По CONTRIBUTING.md «Коммиты и merge» допуск включает branch_push/pr/version_bump,
Ready, обязательный CI и условные merge/deploy на TEST без повторного подтверждения.
Pilot/production, предметная публикация и платные LLM вне допуска.

Исходный main перепроверен: `fa55e1eff21864448b0dcb88dd81cdbcbb2d9a56`, 2.1.41.
Рабочая ветка содержит этот main, конфликтов нет; следующий PATCH — **2.1.42**.
Код и три приёмочных сценария повторно просмотрены по review-checklist: отдельные
profile/preparation/start, точный scope, отсутствие записи при GET, совместимость
snapshots/API/схемы и сохранение старого readback. Существенных новых замечаний нет.
Полномочие владельца на выпуск не объявляется GitHub review-approval; фактические
checks/review/merge/deploy учитываются отдельно. Решение о визуальной приёмке — владелец.

### Подготовка кандидата 2.1.42

- `npm run ready:prepare -- --candidate 2.1.42` — PASS / 0. Main актуален,
  2.1.41 → 2.1.42; штатно изменены pyproject.toml, uv.lock, web/js/config.js,
  web/index.html и пересобран web/dist. Второго bump нет.
- `python3.12 scripts/check_release_version.py --base-ref origin/main` — PASS / 0.
- `node --test tests/frontend/*.test.mjs` после bump — 476 PASS / 0.
- `git diff --check` — PASS. API, SQL, snapshots и тесты поведения после 94b00125
  не менялись; прежний полный локальный набор переиспользован в этой области.
- Техническое review по EVC повторено: источник/контракт/scope прослеживаются,
  все исправления имеют регрессии, schema/API совместимы, GET не создаёт очереди,
  роль владельца и полный CI не заменены агентским самоотчётом. Необработанных
  замечаний нет. Прямое решение владельца о выпуске сохранено выше.

Следующий шаг: commit/push кандидата, Ready, frontend/pytest/full-verification точного
head, затем перепроверка main/checks и разрешённый squash merge/deploy-test.
