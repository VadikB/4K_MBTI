# Проверки P4K-W02-02

База: `68a52a7c21bfe7759d2522a644ad194f7d111f4e`, PR #221, 2.1.7.
Кандидат: 2.1.8. Проверенные байты: [checked-content.json](evidence/checked-content.json).
Immutable candidate/tested SHA, PR head и CI записываются после фиксации в локальный
`RELEASE_STATUS.json`; эта квитанция не меняет проверяемый head.

## Результаты

| Проверка | Результат и первичное свидетельство |
| --- | --- |
| `npm run ready:prepare -- --candidate 2.1.8` | PASS: свежий main, штатный PATCH, release/build. [Лог](evidence/ready-prepare.log.gz) |
| `npm run lint:js` | PASS, exit 0. [Лог](evidence/lint-final.log.gz) |
| `npm run build:web` | PASS, exit 0; generated dist включён. [Лог](evidence/build-final.log.gz) |
| `node --test tests/frontend/*.test.mjs` | 325 PASS, exit 0. [Лог](evidence/frontend-final.log.gz) |
| `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 npm run test:backend` | 1093 PASS, 572 deselected (integration/e2e/llm), exit 0. [Лог](evidence/backend.log.gz) |
| Штатный controlled browser runner, точные args в runner.json | Browser05: 45 PASS / 1 test race FAIL; только исправленный тест повторён browser06: 1 PASS. Browser07: 3 visual PASS на том же runtime. Первичные [browser05](evidence/browser05/browser.log.gz), [browser06](evidence/browser06/browser.log.gz), [browser07](evidence/browser07/browser.log.gz) |
| Actual HTTP / owned PostgreSQL | 9 PASS + 1 PASS, без LLM/писем. [pg01](evidence/pg01/pytest.log.gz), [pg02](evidence/pg02/pytest.log.gz); точные selections — resources.json |
| `python3.12 scripts/check_release_version.py --base-ref origin/main` | PASS: 2.1.8 |
| `git diff --check` | PASS |
| GitHub mandatory CI exact PR head | На момент локальной фиксации PENDING; итог — RELEASE_STATUS.json и checks PR |

## Приёмочные критерии и пределы доказательства

| AC | Технический результат |
| --- | --- |
| AC01 | PASS. 18 состояний: ready, preparing, organization, unassigned, expired, loading, load-error, network, service, failed retry true/false, access, conflict, blocked, missing, start-unknown, start-retry, history. Production frontend с фиксированными HTTP-проекциями, безопасными текстами без контакта; кнопки retry/check/start/history/logout проверены. Состояние expired подставлено как контрактный fixture, рабочее назначение не истекалось искусственно. |
| AC02 | PASS. 5 ситуаций / 75 минут / 48 часов вместо 8/60/72; название из конфигурации текущего назначения. Серверный admission плюс маршрут и оба временных параметра обязательны. Blocked/missing/running не отправляют Start. SQL/HTTP подтверждает сохранённый plan binding и отказы. |
| AC03 | PASS. Check делает GET acquaintance + GET прежней preparation operation, без resolve/prepare/start. Retry требует свежего server retry_allowed, повторно проверяется после resolve. Lost prepare/reload, retry true/false и assignment refusal проверены настоящими frontend-вызовами. |
| AC04 | PASS TECH. Завершённое знакомство → сохранённая история → готовность → явный старт → та же первая AS, один Cycle, 0 оценочных ответов. W02-01 controlled path 1440 сохранён. Browser использует HTTP fixtures; SQL/HTTP отдельно доказывает assignment/profile/plan/Cycle/Session/AS и 0 assessee turns. Это два проверенных слоя, не единая живая browser→БД→AI сессия. Ответы знакомства не Evidence. |
| AC05 | PASS TECH. Потерянный receipt после эффекта: REMAIN05 browser + actual HTTP/SQL lost receipt. Эффект отсутствует: browser lost-before/reload/readback/same-key explicit retry + новый actual HTTP/SQL unstarted readback. Одна AS, один интервал времени, прежний ключ; admission/cancel/foreign отказы сохраняются. |
| AC06 | PASS TECH. 1440×1024 и 390×844: ready/organization/start-unknown; 320 px: длинный текст, footer, keyboard focus и scroll reachability, horizontal overflow 0. Общие W02 tokens, Onest, primary #18B8C6. Снимки browser07 просмотрены Codex; человеческая визуальная приёмка TEST отдельно PENDING. |

Новая backend-дельта — только `assessment_name`: `name` из точно связанной
`assessment_configurations`, без новых настроек, схемы, прав и команды.
Она проверена REMAIN04 actual HTTP/SQL, включая отсутствие имени без binding.
`product-cycle-start/preparation`, transport/fencing, очередь и серверный admission
не менялись от main 68a52a7 (преемник REMAIN05 #219). Исторические protocol65/PG23
из REMAIN05 остаются историческими и не названы свежим PASS. Затронутый HTTP/SQL
набор исполнен заново. Новой очереди и платного прогона нет.

## Диагностика и остановка ресурсов

- Начальный targeted frontend FAIL: извлечение actual handler по прежней сигнатуре
  `advance()`; исправлен parser теста. Итоговый полный набор 325 PASS.
- Browser01: sandbox localhost `listen EPERM`, NOT_RUN_ENV. Browser02: 2 PASS,
  затем no-progress timeout 92.7 s из-за locator старого имени кнопки после network.
  Продукт не исправлялся для обхода ожидания; locator переведён на стабильный id.
- Browser03: 29 PASS / 1 fixture race FAIL (сбой GET включался до первоначальной
  загрузки). Browser04: 40 PASS / 5 устаревших copy/DOM oracles. Исправлены точные
  ожидания W02, без удаления guards и проверок поведения.
- Browser05: 45 PASS / 1 FAIL нового incomplete-теста: click вернулся раньше
  асинхронного GET. Добавлены bounded expect.poll и ожидание enabled; browser06 PASS.
  Эти причины и исходные FAIL сохранены; это не повтор одного FAIL до случайного PASS.
- Все browser runs: 1 worker, retries=0, 600 s total / 90 s no-progress, штатный
  teardown + owned process group TERM/KILL. Фактические resources/results — в папках runs.
  Browser02 первоначальная квитанция group_absent=false проверяется отдельно после reap.
- PG01/02: новые собственные clusters, localhost:55503, `agent4k_pytest`, роль
  stand_owner; оба `stop_exit=0`, port_closed=true, postmaster_pid_absent=true.
  Чужой PostgreSQL:55432 не использовался. [pg01 cleanup](evidence/pg01/cleanup.json),
  [pg02 cleanup](evidence/pg02/cleanup.json). Итоговая сверка — cleanup-final.json.

## Review, риски и откат

Проверены diff, scope/identity/idempotency guards, read-only check, server-only retry,
отказ при смене назначения, отсутствие старта по загрузке и секретов в evidence.
Backend/публичные команды/опубликованные snapshots/ответы/права не меняют смысла.
Предметные prompts, генератор, M6/M8 и будущие карточки не затронуты.
Юридические URL в main отсутствуют: существующие подписи footer сохранены без
выдуманных ссылок. Техническое состояние программы не объявлено методологическим PASS.

CI и человеческое review обязательны; merge/deploy не выполнялись. Фактическая версия
TEST этой задачей не подтверждается. После merge двух блоков человек проверяет
целый путь на компьютере и телефоне на фактическом TEST.
Откат: revert собственного PR штатным процессом, без удаления данных и снимков.
