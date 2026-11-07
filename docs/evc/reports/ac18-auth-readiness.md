# AC18-AUTH-READY-01 — локальное исправление readiness и диагностики входа

Обновление07.11: отдельный полный branch-run на38bf8244 — PASS с первой AS,
явнымstart201 и0ответов, без нового deploy. Первоисточники сохранены
[здесь](../evidence/ac18-branch38-path/README.md); начата отдельная
[подготовка единого выпуска](ac18-final-release.md). Таблица ниже относится к
предыдущему локальному этапу, а не отменяет последующий branch-PASS.

## Результат и раздельные статусы

Реализация: `c4a6a0cb1e28cda7a4188ac8d4efef33c237999c`, отдельная локальная ветка
`codex/ac18-auth-readiness`. Готовность формы не подменяется видимостью старого
token input. Auth pending скрывает/блокирует ввод и submit до server validation;
success включает штатную форму, отказ оставляет её скрытой. Валидация имеет
собственный счётчик и проверяет существующее поколение auth, не увеличивая счётчик
родительской reset-операции. Последние login/reset/401 guards сохраняются.

| Контур | Фактический статус |
| --- | --- |
| Реальный AC18 на339aff9 | FAIL; общий AC18 BLOCKED; первая AS/start NOT_RUN |
| Локальное исправление | PASS бесплатных проверок; implementation c4a6a0cb, не выпущен |
| CI нового diff | NOT_RUN: push/PR не разрешены |
| origin/main |339aff9034ff005bc20d072876b3fbef4f834c5e /2.0.74 |
| Test deployment |339aff9 /2.0.74; данный fix NOT_DEPLOYED |

Версия не повышалась. Все release flags=false, нового full PATH/LLM нет.

## Два разных установленных факта

1. Разрешённый после Resolved one-shot run `2835475f27a64c89b273887ee3e38a76`:
   start11:06:00МСК, finish11:06:24МСК, ровно один runner, exit1.
   Ожидание: admin password step2. Факт: step1 через5s. Email confirm HTTP200;
   password-register не начат. Preparation operation/Cycle/AS отсутствуют,
   оценочных ответов0, provider не достигнут. Историческая причина run UNKNOWN.
2. На исходном UI независимо подтверждена readiness-гонка. `main.js` показывал
   форму с one-time-code до ответа confirm/reset validation; поздняя конфигурация
   меняла name/type и очищала ввод. Два deterministic before-теста — FAIL именно
   на visible вместо hidden. Исправление устраняет этот установленный дефект.
   Его причинная идентичность последнему run — **NOT_PROVEN**, поскольку нет
   browser timing trace, а исходный failure.png снят с пустой вкладки участника.

Нельзя объявлять новый дефект причиной старого HTTP500, questionnaire timeout
или PREP-DIAG-01. Последний по-прежнему отдельный исторический UNKNOWN.

## Harness и диагностика

`waitForPasswordCreationForm` ждёт видимую включённую форму, `new-password`,
password type/autocomplete, step1, кнопку «Продолжить» и **точный** ожидаемый email.
Это не успешный auth resolver и не обход серверной регистрации.

PATH29 перед каждым актором выбирает activePage/activeActor; catch сохраняет
failure-context.json и PNG именно этой вкладки даже при отсутствии HTTP endpoint.
Контекст — allowlist: actor/step, pathname, имена query-ключей без значений,
заголовок/статус/ошибка, имя/type/disabled/наличие ввода, но не его значение.
Credential inputs маскируются на PNG. JSON использует существующий fsync/readback
`persistReceipt`. Оба helper входят в code-identity. Терминальные server receipts,
экспорт до cleanup и текущая cleanup-защита не ослаблены.

## Проверки и применимость

База перед реализацией: свежий fetch origin/main339aff9, отдельный worktree.
README/CONTRIBUTING/EVC/AGENTS и источники указаны в [карточке](../tasks/ac18-auth-readiness.md).
Порядок source-to-rule: принятая UX-02 server-validation before password →
pending UI guards → real JS/browser regressions; методологического изменения нет.

| Команда / проверка | Факт |
| --- | --- |
| before: Playwright auth-r03, grep `AC18 auth readiness: .*cannot submit` |2 ожидаемых FAIL на исходном UI |
| первая targeted серия после fix |5 PASS; предварительный результат, не final suite |
| `node --test tests/frontend/*.test.mjs` |146 PASS, JUnit frontend-final.xml |
| `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 PYTHONPATH=. <project-venv>/python -m pytest -q -m 'not integration and not e2e and not llm'` |956 PASS /354 deselected |
| те же env + `pytest -q -m e2e tests/e2e` |108 PASS /12 deselected |
| `npm run lint:js`, `git diff --check` |PASS |
| `npm run build:web` и сравнение всех JS hashes до/после повторной сборки |45 files, byte-identical PASS |
| полный auth-r03 +auth-recovery |первый126 PASS/1 ошибка нового test expectation URL; final127 PASS, flaky0/retries0 |

Первый запуск before-tests остановился на синтаксической опечатке нового теста;
он не считается отрицательным доказательством продукта. После исправления
получены настоящие2 FAIL. В первом широком прогоне ошибочное ожидание query
игнорировало штатную очистку URL после email request. Исправлен только тест:
он теперь задаёт synthetic query непосредственно перед safe-capture и проверяет
отсутствие обоих значений (query token и password) в JSON. Исходные результаты
сохранены, не переписаны в PASS. Автоматические retries=0.

Backend/HTTP относятся к неизменённым Python/Api bytes окончательной реализации;
после них менялись только JS test expectation/документы. Browser использует
явно synthetic HTTP, без PostgreSQL, внешней почты/LLM: это не real PATH и не
повтор AC06/07/09/10 actual PostgreSQL acceptance. Integration NOT_RUN,
поскольку server auth/SQL/schema/data не менялись; auth-строка матрицы закрывается
backend+HTTP контрактами и browser UI-регрессиями. Нового CI/release gate нет —
это локальный рабочий commit, не Ready-for-review/release кандидат.

Визуально проверены pending без доступной формы, step2 registration390 и
reset1440, masked failure capture. Это не визуальная приёмка первой AS.
Широкий browser по старому пути перезаписал две tracked картинки adm-status-01.
Новые test-generated bytes сохранены отдельно в пакете, исторические PNG возвращены
к исходным HEAD bytes. Ни история evidence, ни чужая работа не включены в diff.

Offline `VERIFY.py` PASS:31 original run files, final127/146/956/108 results,
negative runner остаётся FAIL, AC18 BLOCKED; новых network/DB/LLM calls0.
Первичные тестовые результаты и безопасные выдержки —
[evidence](../evidence/ac18-auth-readiness/README.md).

## Первичный negative run и очистка

Содержимое безопасной выгрузки31 файла проверяется manifest SHA256:
run/code/source provenance, pinned release bytes, failure/failure-receipt,
completion/process/runner result, PNG/viewport и fresh preflight/readbacks.
Raw server.log/runner log/state/.env/cookies/generated passwords не экспортируются.
Полный доступный пакет передаётся отдельно с offline VERIFY.py, patch и Git bundle.

Owned DB `product4k_pytest_2835475f27a64c89b273887ee3e38a76` удалена штатно,
owner_verified=true, force=false. Независимый maintenance postgres:55432 READ ONLY
readback11:09:29МСК: DB0, connections0, secret state absent, порт свободен.
Failure/source receipts по mtime сохранены **до** cleanup; это дополнение к
существующему fsync/readback кода. Повторный cleanup не выполнялся.

Перед actual launch были два SSH banner timeout **до аутентификации**. Каждый
незапуск проверен independent readback: output/guard/PID/run отсутствовали.
Затем существующее SSH-соединение переиспользовано, создан exclusive launch guard,
ровно один actual runner. Транспортные попытки не считаются дополнительными run.
Resolved провайдера и отсутствие текущего инцидента повторно проверены на сервере
непосредственно перед запуском; прежний authorization уже израсходован.
Heartbeat `ac18-deepseek` остановлен (PAUSED), автоматических повторов нет.

## Риски, откат и следующий шаг

Api/assessment_definitions/package metadata и опубликованные источники неизменны.
Схема/данные/рабочая БД/.env/prompts/admission/repair не менялись.
Чужой root worktree и три его untracked документа сохранены.
Данный fix не доказывает отсутствие всех прочих причин прежнего отказа.

Откат — revert только нового локального implementation commit; миграций нет.
Затем потребуется отдельный release допуск (версия/PR/CI/review, далее merge/test)
и новый конкретный допуск AC18 на **окончательном выпущенном SHA**. Нельзя
проверить изменённый локальный UI, продолжая называть базой339aff9 или прошлый PASS.
