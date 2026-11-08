# AC18-FIX-02 — итоговая сверка пакета и опубликованного frontend

Статус на момент подготовки: локальный кандидат отчёта и адресной регрессии.
Публикация ветки и PR учитываются отдельно; merge и deploy в рамках этой задачи
не выполнялись. Основание —
`P4K_AC18_FIX_02_Preparation_Start_2026-11-07.zip`, `START_CODEX.txt`,
`TASK.txt`, `SOURCES.md`, `VISUAL_ACCEPTANCE.txt`, редакция 1.0 от 07.11.2026.
Срез проверки: `origin/main@1c0d7025ce905e4ca719be9ebaf4662f2c37c4f3`,
продукт `2.0.82`, после squash-merge PR #192 и успешного `deploy-test` #877.

## Результат и граница

PR #182–192 последовательно вошли в `main`; кандидатный полный CI PR #192
завершился 9 успешными проверками при ожидаемом пропуске `deploy-test` на PR.
После merge workflow #877 и его `deploy-test` — PASS. Разрешённый один
real-provider PATH на `main@5eb1250a` / `2.0.82` — PASS для одного
положительного синтетического сценария до первой AS с нулём оценочных ответов.
Он не воспроизводил исторический отказ или repair.

Адресный просмотр после выпуска теперь запускает существующие browser-сценарии
против **опубликованного** `https://test.4k-assistant.ru` вместо локального
статического сервера. Все `/users/**` ответы для UI-сценариев перехвачены
синтетическими fixtures; не перехваченные записи блокируются до сети.
Отдельный read-only тест проверяет публичную версию и SHA-256 отдаваемого
`/web/dist/main.js` против файла точного checkout. Это проверка опубликованного
frontend и действий браузера, **не** сквозной тест реального участника на
рабочей БД стенда и **не** новый LLM-вызов.

| ID | Итог на текущем `main` | Граница доказательства |
| --- | --- | --- |
| P2-AC01 | **PARTIAL / историческая причина UNKNOWN**: invalid JSON, missing/incomplete/foreign review и корректный ответ различаются; batch/check и candidate checksum защищены #188–189 | Первичные provider responses/trace операции `64344f28-e9de-4bcc-9173-27376a33ea0b` не были доступны в переданных evidence. Точную причину именно её `INCOMPLETE` не установили; новый PASS её не объясняет. |
| P2-AC02 | **PASS**: обязательный `INCOMPLETE/FAIL` закрывает admission; сохранённый отказ и owned HTTP/PG readback проверены #188 | Синтетические ответы, не повтор исторического провайдера. |
| P2-AC03 | **PASS**: queued/running/failed/unknown/ready и reload, безопасная причина отказа после reload (#183, #186) | UI mock HTTP + адресный HTTP/PG; физический браузер не проверен. |
| P2-AC04 | **PASS**: lost prepare response сначала owned GET (#185); fail-closed retry после технического отказа (#187), без скрытой новой операции | Синтетические browser/HTTP/PG и прежние queue-регрессии. |
| P2-AC05 | **PASS**: lost start/readback/reload сохраняют ключ, Cycle, AS и исходное время (#182, #190); отдельный HTTP/PG proof #191 | Browser и SQL/HTTP доказательства соединены по контракту, но не одна живая сессия на `test`. |
| P2-AC06 | **PASS**: сервер повторно проверяет scope/admission; чужая организация и stale READY отклоняются | Адресная изолированная PostgreSQL-регрессия #182/191. |
| P2-AC07 | **PASS технически**, визуальные кадры/сценарии #183 приняты владельцем | Chromium 1440/768/390/320; физический телефон, Safari/Firefox — NOT_RUN. |
| P2-AC08 | **PASS адресного опубликованного frontend-readback**: версия `2.0.82`, main.js SHA-256 `88490b3cb2637c9c6d258e8056fc00b6f82104feb85a5dec907f0bb71442c73e`; 5 browser-сценариев на опубликованных assets | API в этих пяти сценариях синтетический. Живая сессия реального участника на `test` — NOT_RUN; этот пункт не выдаётся за full PATH. |

`PREP-DIAG-01` — отдельный исторический UNKNOWN; ни текущий отчёт, ни
операцию `64344f28-…` с ним не объединяют. Применимость прежних проверок:
локальные/CI результаты PR #182–191 относятся к их точным head и неизменённым
контрактам, full CI #192 — к итоговому сочетанию `main@5eb1250a` плюс только
документационный diff. Новый browser-readback выше использует checkout
`main@1c0d7025`, но не меняет продуктовый runtime.

## Источники и решения

Повторно использованы прочитанные в этой сессии `README.md`, `CONTRIBUTING.md`,
`AGENTS.md`, EVC workflow, verification matrix, artifact recipe, task template,
review checklist, Product Architecture 1.0/context/Registry и Change 01 с
task manifest. Адресно прочитаны пакетные `START_CODEX.txt`, `TASK.txt`,
`VISUAL_ACCEPTANCE.txt`, [визуальные evidence](../evidence/ac18-fix02-preparation-start/README.md),
[отчёт одного провайдера](ac18-fix-02-real-provider-verification.md),
`docs/evc/assessment-first-case-profile.md`, `tests/browser/auth-r03.spec.mjs`,
`playwright.config.mjs` и отчёты #185–191. M1 v1.4 остаётся FROZEN/CURRENT=NO;
новую предметную норму проверка не вводит.

Прослеживаемость: P2-AC07/08 → принятый T1 first-start/readback и participant
projection → опубликованный frontend `web/index.html`/`web/dist/main.js` →
синтетические browser-действия и exact asset/version readback. PM-03 готовит AS,
PM-04 исполняет; тест не меняет их контракт или владение данными.

Стоп-условия EVC для текущего test/docs diff: смысл — нет; публичный API/PM/схема —
нет; миграция/удаление данных — нет; конфликт обязательных источников — нет;
новый артефактный контур — нет; передача чувствительных данных/права — нет;
небезопасный откат — нет; выход за область — нет. Для вывода о первопричине
исторической операции есть **блокер доказательств**: отсутствуют первичные trace.
Владелец 07.11.2026 принял визуальный комплект #183, 08.11.2026 разрешил один
платный PATH и отдельно принял/слил #192. Эти решения не означают приёмку
содержания всех будущих AS или разрешение нового платного прогона.

## Проверки

- `node --check tests/browser/auth-r03.spec.mjs` — PASS.
- `git diff --check` — PASS.
- `npm run lint:js` — PASS; `npm run build:web` — PASS, tracked `web/dist`
  не изменился.
- `./node_modules/.bin/playwright test tests/browser/auth-r03.spec.mjs -g 'AC18-FIX-02' --workers=1`
  — PASS: 4 сценария, опубликованный тест ожидаемо skipped без origin. Первая
  sandbox-попытка — `NOT_RUN_ENV` (`listen EPERM`), повтор с доступом к localhost — PASS.
- `AC18_FIX02_PUBLISHED_ORIGIN=https://test.4k-assistant.ru ./node_modules/.bin/playwright test tests/browser/auth-r03.spec.mjs -g 'AC18-FIX-02' --workers=1`
  — PASS: 5/5 на опубликованном frontend. Первая sandbox-попытка —
  `NOT_RUN_ENV` (macOS Chromium MachPort permission), повтор с доступом — PASS.
  Публичный `/users/version` вернул `2.0.82`, отдаваемый `main.js` совпал
  по SHA-256 с локальным файлом `main@1c0d7025`.
- Backend/HTTP/PG и real-provider **не повторялись**: продуктовый код не менялся;
  действуют указанные точные прежние CI и evidence. Физические устройства и
  живая сессия на shared `test` — NOT_RUN.

## Риск, откат и передача

Изменены только browser-тест и этот отчёт; методология, prompts, опубликованные
definitions/snapshots, runtime, конфигурация, публичный API, схема и данные не
менялись. Тестовый браузер не использует реальные cookies/credentials; synthetic
fixtures остаются fixtures, не доказательством качества AS. Откат — revert
test/docs diff; сохранённые Cycle/AS/ответы и сырые первичные evidence не трогать.

Следующий шаг: review кандидата в отдельном PR.
Для закрытия причины операции `64344f28-…` нужен доступный первичный provider
response/trace именно этой операции; без него честный статус — UNKNOWN.
Флаги на момент подготовки отчёта: `branch_push=false`, `pr=false`,
`merge=false`, `deploy=false`, `version_bump=false`,
`artifact_publish=false`, `llm=false`. Актуальный статус публикации — в PR.
