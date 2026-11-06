# AC18: синтетические ИТ-данные анкеты

Основание: запрос владельца «заполни по своему усмотрению из сферы ИТ и пойдем дальше».
Base/main `61f34aa2151a4f9364eac28bf33895d10f91d50b`, приложение 2.0.71.
Ветка `codex/ac18-questionnaire-it-inputs`; чужая корневая ветка и три untracked docs не затрагиваются.

## Результат и границы

Заполнить и подтвердить синтетическую анкету вымышленной ИТ-компании в новой
изолированной PostgreSQL через реальные UI/HTTP, сохранить readback и удалить только
owned-БД. Прежняя AC18-среда уже удалена; её единственный отрицательный результат
не переписывается. Нового real-provider PATH или возобновления старого run нет.

Источник тестовых значений — выбор агента по прямому разрешению владельца;
`tests/browser/fixtures/questionnaire-it-synthetic-v1.json`, v1, synthetic only.
Не сведения о реальной компании, не human QA и не допуск целевого пилота.
Используется существующий ADM28 synthetic seed, без изменения server/UI/runner,
опубликованных материалов, M0–M8, admission или repair. Нет нового runtime.

## Источники и решения

Прочитаны AGENTS, README, CONTRIBUTING, agent-workflow, verification-matrix,
artifact-recipe, task-template; архитектурный context1.0, Registry, Change01 README,
manifest, M1 v1.4 (FROZEN/CURRENT=NO; понятийное основание не меняется).
Применимые потребители: `web/js/screens/admin/organizations.js` (draft/load/render/form),
`Api/questionnaire_sources.py`, `scripts/test_stand.py`, `scripts/adm28_browser_fixture.py`,
`tests/browser/adm28-real.spec.mjs`, `tests/browser/fixtures/path-viewports.mjs`;
профиль `assessment-first-case/1.1`, tests/README и browser/README.
Исторический пакет AC18 `61f34aa` сохранён отдельно.

Наблюдение: прежний runner уже вызывал fill всех 12 полей, затем три оказались пустыми.
Повторное присвоение данных не доказывает устранение причины. Новый probe использует
явную завершённую инициализацию карточки перед вводом; это не скрытый product fix.
AC18-QUESTIONNAIRE-DIAG-01 и AC18-TIMEOUT-CLEANUP-DIAG-01 пока UNKNOWN;
PREP-DIAG-01 остаётся отдельным историческим UNKNOWN.

Стоп-условия: изменение предметной нормы/публичного контракта/схемы/постоянных данных/
прав/артефактного контура — нет; расширение до нового платного PATH/выпуска — да,
не входит. Откат: удалить только новые test/docs файлы, без миграций.

## Проверки и состояние

Завершено: бесплатный actual HTTP/PostgreSQL probe анкеты, 12 полей, 4 ширины,
preview201/confirm200, reload, SQL read-only/rollback, отсутствие preparation/Cycle/AS/ответов.
LLM и реальные письма запрещены. Новый кластер localhost, test/pytest в имени БД,
точный owner marker и штатный `test_stand.py destroy`, без FORCE.
Проверки синтаксиса Python/Node и diff/check PASS. Первая бесплатная попытка
остановилась на ошибочной проверке probe: ожидался preview200, продукт штатно
создал revision с201. Ошибка probe исправлена по фактическому HTTP-контракту;
все12 полей и4 ширины до этого прошли, первая owned-БД штатно удалена.
Вторая попытка выполнила confirm200, GET и reload всех12 полей, но probe ошибочно
требовал глобальный profiles=0: существующий E10.2 seed заранее создаёт2 профиля
других синтетических участников (`scripts/test_stand_seed.py:144–155`). Теперь
probe сохраняет SQL baseline до запуска UI и сравнивает неизменность counts,
требует ровно одну новую questionnaire revision. Это уточнение области доказательства,
не изменение продукта. Вторая owned-БД также штатно удалена.
Существующие продуктовые проверки 2.0.71 не объявляются проверками новых test файлов.

Все действия выпуска false: branch_push, pr, merge, deploy, version_bump,
artifact_publish. CI не запускается; main/test сохраняются 61f34aa/2.0.71.
Только test fixtures/probe/helper/docs, поэтому сборка frontend и миграции неприменимы.

## Итоговая проверка и передача

- `STAND_ADMIN_URL=postgresql://postgres@127.0.0.1:55438/postgres BROWSER_PYTHON=/Users/vadim_bogachev/Developer/4K/.venv/bin/python P4K_EVIDENCE_DIRECTORY=.test-stand/questionnaire-it-20261106 node_modules/.bin/playwright test tests/browser/questionnaire-it-inputs.spec.mjs --workers=1` → **1 PASS**, 35.4s, exit0.
- `node --test tests/frontend/path-start-questionnaire.test.mjs` → **8 PASS**, exit0.
- `/Users/vadim_bogachev/Developer/4K/.venv/bin/python -m pytest tests/unit/test_questionnaire_sources.py -q` → **11 PASS**, exit0.
- `node --check tests/browser/questionnaire-it-inputs.spec.mjs`, Python `py_compile`, `git diff --check` → **PASS**.

Primary evidence: `.test-stand/questionnaire-it-20261106/952934fb-469b-4003-abc3-de2e99a7b122/`
в этой рабочей копии: run, baseline, filled-fields, http-readback, database-readback,
result, cleanup, 4 PNG/viewport receipt и PNG подтверждённой анкеты.
Run ID `bc4a58afad824f7cb167dc10186af0f6`.
`result.status=PASS_QUESTIONNAIRE_ONLY`; preview201, confirm200, штатный GET200,
все12 полей после reload совпадают. Сохранённая SQL revision совпадает с HTTP JSON.
Questionnaire revisions0→1, profiles2→2 (чужой synthetic seed), assignments/preparation/
Cycle/AS/turns0→0. Нет prepare/start запросов. Новых provider operations0.

Штатный destroy подтвердил exact owner, database_absent/state_absent=true, force=false.
Независимый maintenance readback вернул0 test-БД. Удалены только данные трёх новых
синтетических probe-БД (две первые попытки с ошибками нового теста также сохранены).
Артефакты сохранены; исходные AC18 evidence не менялись. Временный контейнер
PostgreSQL16 `4k-questionnaire-it-pytest-20261106-a219` остановлен после сверки
его task label; постоянного тома не было, `--rm` удалил только его слой.

SHA256 тестового содержания:

- fixture: `06b03f226c660dfbc5792d88d3718b38565bf83ba274d635c0a8f206b051eef9`;
- browser probe: `b605ba9c6a28a2ce13abb547656fb645edc7041eac7de329a0ec4e72769711da`;
- SQL readback helper: `1e968994c0c795d2beba4a2bdc976d590279844aec71173f9ca71d3b0ad5db30`.

Команда выше проверена с локальной dependency-ссылкой `node_modules` на root
workspace. Ссылка не часть изменения; без неё тот же исполняемый файл доступен
как `/Users/vadim_bogachev/Developer/4K/node_modules/.bin/playwright`.

Тестовая синхронизация здесь — завершённое сохранение карточки до заполнения.
Это проверяет выбранные значения и реальное подтверждение, но не доказывает,
что исходный late-render/timeout дефект устранён. Точные причины исторических
AC18-QUESTIONNAIRE-DIAG-01 и AC18-TIMEOUT-CLEANUP-DIAG-01 остаются UNKNOWN.
Постоянный PATH29 runner не изменён и не получает новые входы автоматически;
fixture сохранена для следующей отдельно согласованной работы.

Следующий минимальный шаг: бесплатное детерминированное воспроизведение потери
черновика и timeout cleanup, затем отдельное решение об исправлении/выпуске.
Новый платный AC18, push/PR/merge/deploy не выполнялись.

## Продолжение: диагностика потери черновика

Разрешение владельца «делаем» после предложения бесплатно воспроизвести причину
потери полей. Активный шаг: управляемая задержка **реального** GET сохранённых анкет,
ввод первых3/всех12 полей до ответа и контроль ввода после ответа. Реальные backend,
PostgreSQL16 и текущий dist2.0.71; response/resolver/Connection/DOM не подменяются.
Наблюдается замена узла и значения полей, native validity, отсутствие preview POST,
отсутствие confirmation и SQL частичных записей. После фиксации — явное повторное
заполнение для проверки штатного preview/confirm и owner cleanup.

Источники дополнительно: `web/js/wiring.js` (submit/input),
`loadAdminOrganizations` → `loadQuestionnaireRevisions` → `renderAdminOrganizations`,
`captureFormDraft`/`restoreFormDraft`, код `receipt-file.mjs`.
Кандидат причины: после асинхронного GET вызывается полная перерисовка без сохранения
текущего ввода; последний draft capture выполнялся при переключении вкладки до ввода.
Пока это гипотеза, не утверждение о точной хронологии прежнего AC18.
Новые diagnostic tests запускаются только отдельным config и не входят в стандартный
зелёный acceptance: successful diagnostic сохраняет `product_status=FAIL_…` при
воспроизведённом дефекте. Нормы/критерии/admission не меняются.
Исправление product UI/runner, timeout cleanup, версия, PR/CI/merge/deploy и LLM
в этом диагностическом шаге не выполняются. Main после свежего fetch61f34aa;
ветка на e9330ed6, посторонние изменения не затронуты.

Диагностика завершена: [отчёт](../reports/ac18-questionnaire-draft-diagnosis.md).
4 actual HTTP/PostgreSQL scenarios, exit0/2.7min:3 воспроизводят продуктовый FAIL
потери ввода,1 контроль PASS после завершения GET. Это не AC18 PASS.
Все4 owned-БД штатно удалены, независимый maintenance count0, одноразовый контейнер
остановлен. Primary JSON/PNG без секретов сохранены в
`docs/evc/evidence/ac18-questionnaire-draft-diagnosis/`.
Q-DRAFT-01 имеет воспроизведённый механизм; точная причинная идентичность со старым
AC18 не доказана. Исторические root UNKNOWN и timeout cleanup UNKNOWN не меняются.
Текущий шаг не исправляет продукт; следующий зависимый шаг ожидает отдельного
согласования узкой UI-правки и регрессий. Все флаги выпуска false, LLM0.
