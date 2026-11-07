# PROVIDER-ROLES-01 — контракт модели и инфраструктурное окружение

## Результат и решение владельца

07.11.2026: владелец уточнил: «настройки не “чинить”, а развести роли — контракт
управляет моделью, `.env` — секретами/инфраструктурой; и зафиксировать это явно».
Это основание локальной реализации, не разрешение менять серверный `.env`, выполнять
restart, bump/push/PR/merge/deploy, публикацию программы или платный AC18.

База — свежий `origin/main` `44802660b47851f98e7b62ddb5a5f8275308569c`,
версия2.0.73/PR178. Ветка `codex/provider-contract-env-roles`, отдельный worktree.
Чужая `codex/tg-bot-educational-cycle-context` и три её untracked документа сохранены.

## Область и совместимость

- Новая операция получает модель из уже используемого versioned provider contract;
  начатая — из собственного сохранённого snapshot. `.env` не выбирает модель.
- `DEEPSEEK_MODEL`, оставшийся в старом окружении, игнорируется как obsolete;
  диагностируется только присутствие, значение не печатается и не копируется в stand.
- Сохраняются credentials, endpoint/сетевые настройки, concurrency, isolated DB/owner
  guards и fail-closed при недоступном/невалидном обязательном контракте.
- Не меняются provider manifest1.0.0 (draft), prompts, admission/repair, API, схема,
  опубликованные определения, snapshots, QA, методология и CURRENT.
- `settings.deepseek_model` сохраняется как read-only compatibility view контракта,
  не самостоятельная настройка. Явная модель gateway от frozen operation сохраняется.

## Источники и прослеживаемость

Прочитано/повторно использовано на указанной базе: `AGENTS.md`, `README.md`,
`CONTRIBUTING.md`, EVC workflow/matrix/artifact recipe/task template/review checklist;
архитектурные context1.0/Registry, M1v1.4 README (FROZEN/CURRENT=NO), Change01 README,
SourceSet manifest и И-1/И-6 исходного текста; runtime snapshot contract,
artifact-debt register, Task10-13 provider contract. M0 unavailable не закрывается;
новая предметная норма не вводится.

Решение владельца + Change01 И-6 → обязательный provider manifest/snapshot →
`Api/config.py`, gateway, existing runner/stand → offline unit/HTTP регрессии.
Потребители проверены: PM03 preparation queue уже явно использует frozen provider;
M5 rule engine сохраняет operation model; legacy gateways/M6 v1 новые snapshots
раньше читали env-backed `settings.deepseek_model`. Новые форматы не создаются.

Подтверждённый пробел: три env templates выбирают модель, config читает env,
runner требует наличие model env и stand передаёт её, хотя PM03 использует контракт.
Старый sidecar ошибочно приравнивал глобальное несовпадение к отказу PM03;
исторический блокер не переписывается. PREP-DIAG-01: UNKNOWN; прежний timeout
и причинная связь с Q-DRAFT остаются UNKNOWN/NOT_PROVEN соответственно.

## Стоп-условия и выпуск

Все восемь стоп-условий workflow — нет: предметный смысл/схема/публичный API,
миграция/удаление, источник правила, новый формат, чувствительные границы,
откат и область имеют неизменные либо явно заданные основания выше.
Зависимый выпуск требует нового прямого решения. Все release flags=false:
`branch_push`, `pr`, `merge`, `deploy`, `version_bump`, `artifact_publish`.

## План и проверки

1. Зафиксировать ownership регрессии на исходной базе (red).
2. Развести model selection и инфраструктурную allowlist; обновить инструкции.
3. Адресные регрессии + backend минимум матрицы + HTTP-контракты; без LLM/рабочей БД.
4. Локальный commit, запись состояния и передача. CI и новый deployed AC18 — отдельно.

Критерии: отсутствие/любое legacy значение DEEPSEEK_MODEL не управляет запросом;
модель/версия/checksum контракта видны в preflight без секретов; обязательный
контракт нельзя заменить env fallback; stand переносит только инфраструктурные
provider поля; frozen explicit model не подменяется; templates не выбирают модель.

Integration/real-provider/browser PATH не заменяются unit success. SQL не меняется;
необходимость DB integration оценить после diff. Откат — revert только данной
локальной реализации; сохранённые данные и серверный `.env` восстанавливать не нужно,
так как они не меняются.

## Выполненная проверка и доказательства

- Red:15 ownership checks →13 FAIL/2 PASS, exit1 до реализации. В первоначальной
  попытке port availability не отделена от sandbox; окончательные unit используют
  явный stub только порта. Это не13 отдельных продуктовых дефектов.
- Адресные units →52 PASS, exit0.
- Полный backend marker set →956 PASS/354 deselected, exit0.
- HTTP contracts →108 PASS/12 deselected, exit0; synthetic dependencies, не actual PG.
- Дополнительный offline readback со старой synthetic env-моделью: contract/default
  gateway/compat settings/new M6 snapshots=`deepseek-flash`; explicit frozen model
  сохранена; DB/provider calls0.
- `git diff --check` PASS; артефакты/методология/source files/manifest, release files
  и frontend неизменны относительно базы (scoped `git diff --exit-code` PASS).

Полные команды, первичные JUnit, хеши и offline checker:
[evidence](../evidence/provider-contract-env-roles/README.md).
Provider manifest SHA256 `a9b20456f413a8828ee2cca47356490ae98844542c8ad31c015f937abe951c8c`
не менялся. Исправлен выбор модели, а не содержимое/допуск пакета. ART-06 (смешанные
предметные функции legacy client) этим не закрывается и не расширяется fallback.

Первый staged diff-check/commit hook остановил передачу из-за trailing spaces в
сгенерированном negative JUnit. Primary сохранён без изменения bytes в `red.zip`,
в checker добавлена проверка uncompressed hash. Hook/проверки не ослаблялись;
после упаковки staged diff проверяется повторно.

## Изменённые файлы и эксплуатационные риски

`Api/config.py`: read-only model view контракта вместо env; gateway: safe model-source
metadata; runner: credentials/contract checks, ignored legacy presence, infra-only
allowlist и расширенная code identity; stand: модель не переносится. Три env templates
теперь не задают модель; README/профиль/tests инструкции явно разделяют роли.
Регрессии и evidence — новые локальные файлы. Управляющие EVC-документы не менялись.

Это намеренное изменение новых default gateway calls при будущем выпуске: они
выбирают существующий контракт, а не старую env-строку. Frozen операции сохраняют
явную модель; существующие identity guards/ограничения поддержки старых snapshots
не отменяются. Нет массовой миграции или обещания работоспособности неподдерживаемой
исторической identity. Данные/схема не меняются, sensitive values не выводятся.

## Непроверенное и состояние передачи

Implementation commit `1666f92114c3118305324309bc3e922643865c23`; к нему применимы
targeted52/backend956/HTTP108. Handoff после него — только STATE/task/evidence
metadata; runtime/templates/profile/tests остаются с теми же18 проверяемыми hashes.
Final staged diff-check и штатный commit hook PASS после byte-preserving упаковки.

Локальная реализация и бесплатные проверки завершены. Свежий origin/main перед
передачей по `git ls-remote` —44802660/2.0.73. Remote CI NOT_RUN (нет push/PR),
новая версия не назначалась. Этот diff NOT_DEPLOYED; свежий readback существующего
test здесь NOT_RUN. Серверный `.env` и сервис не менялись, доступ к серверу не нужен.
Actual machine preflight нового кандидата, PostgreSQL integration, browser/real PATH
не запускались. SQL/UI не меняются; actual machine и real-provider AC18 остаются
непроверенными, unit/HTTP ими не подменяются. Warning Starlette/httpx предсуществующий.

Следующий минимальный шаг — человеческая приёмка локальной реализации, затем отдельное
решение выпуска/номера/PR и обязательный CI. Merge/deploy — отдельно. Только после
deploy/readback и бесплатного preflight на окончательном SHA — отдельный допуск одного
платного AC18. Восстановление/замена DEEPSEEK_MODEL в рабочем `.env` не нужны.
Прежний 2072 sidecar не применять к новому коду: его obsolete глобальное сравнение
явно снято этим решением, сам исторический evidence не переписывается.

## R1 — начата подготовка выпуска, ожидается номер

После локальной передачи19bc6ad0 владелец: «делаем». Начата подготовка выпуска;
07.11 свежий remote main повторно подтверждён44802660/2.0.73. Первый read-only
запрос не запустился из-за timeout automatic permission review; один повтор PASS.
Штатный `PYTHON_DOTENV_DISABLED=1 npm run ready:prepare` обновил origin/main,
проверил актуальную базу и остановился с exit2:
`requires an approved patch candidate: 2.0.73 → 2.0.74`.
Это ожидаемый version gate, не новый дефект продукта. Номер не назначен,
build/push/PR/CI/merge/deploy/БД/LLM не запускались; после preflight дерево чистое.
18 hashes/4 JUnit повторно PASS. Первичный результат:
[release-preflight.json](../evidence/provider-contract-env-roles/release-preflight.json).

Активный шаг — решение владельца: PATCH2.0.74 и scope push/PR/обязательный CI/review.
Merge/deploy, публикация программы, изменение серверного `.env` и платный AC18
в этот запрос не входят. До ответа все release flags остаются false.
Новые R1 docs/evidence — локальные незакоммиченные записи поверх19bc6ad0;
проверенные implementation bytes не изменены.

## R2 — разрешена подготовка кандидата2.0.74 для PR/CI/review

07.11 владелец ответил «да» на конкретный вопрос: «2.0.74 (PATCH): bump → push ветки
→ PR → обязательный CI → человеческое review». Основание — сообщение текущего чата,
не текст документа/страницы. Разрешены `version_bump=true`, `branch_push=true`,
`pr=true`. По-прежнему `merge=false`, `deploy=false`, `artifact_publish=false`;
серверный `.env`/рабочая БД/публикация программы/платный AC18 исключены.

Порядок: штатный ready preflight с approved candidate и fresh origin/main;
lint/frontend/release+harness regression/evidence checks; reuse backend956/HTTP108
только при неизменности функциональных source bytes; commit/push/Ready PR;
mandatory frontend/pytest/full-verification точного head/base; человеческое review.
Новый commit после CI требует новых проверок; status-only коммиты после зелёного CI
не создаются. При изменении main/номера — штатный gate и адресная переоценка.

README/CONTRIBUTING, workflow/matrix/recipe, source/Registry/Change01/manifest/M1,
профиль и код контракта повторно используются как неизменённые; release scripts,
PR template, CI workflows и текущая карточка перечитаны. Новых источников/норм
или стоп-условий не выявлено. Только release metadata/build не даёт допуска AC18.
Откат локального кандидата — адресный revert release commit; действующий main/test,
артефакты и сохранённые данные не меняются. В будущем rollback выпуска — штатный PR,
не откат/редактирование snapshots или рабочего `.env`.

В новом worktree нет `.env`. Игнорируемые каталоги `.venv`/`node_modules` содержат
ссылки на уже установленные локальные зависимости, package-lock byte-identical;
установки нет. Первичные outer symlinks видны как untracked, поэтому они заменены
только на эти собственные каталоги/вложенные ссылки; shared dependency files не менялись.
Активный шаг — подготовка и бесплатные release-проверки; CI/human review ожидаются.

### R2: локальный кандидат проверен, готов к push/PR

Canonical ready preparation и повтор2.0.74 PASS,49 metadata/assets hashes идентичны,
release gate PASS. Новые frontend145/receipt66/Python116 PASS; lint/diff/source
checks PASS. Source1666f921 API/scripts/tests/templates/README/profile/артефакты
byte-identical;956 backend/108 HTTP применимы в этой области. От19bc6ad0 меняются
только approved release metadata/build и R1/R2 docs/evidence. Source definitions и
рабочая БД не менялись. Полный mandatory CI **ещё не выполнялся**, human review
NOT_DONE. Primary hashes/JUnit/commands/offline checker:
[release2074](../evidence/provider-contract-env-roles/release-2074/README.md).

Самостоятельное review diff агентом: env больше не authority модели, default и
новые M6 snapshots читают обязательный контракт, explicit frozen model не заменяется;
invalid/missing contract fail-closed, credentials по allowlist без экспорта значений,
source selector/admission/repair/cleanup не ослабляются. Упаковка negative JUnit
byte-preserving, не скрытие ошибок. Это не человеческое code review.

Следующий активный шаг — commit/push/Ready PR с точным head, затем mandatory CI.
Состояние CI публикуется в PR без изменения candidate commit. Старый общий
`.env` model mismatch не используется как самостоятельный product blocker PM03.
AC18 только на будущем окончательном deployed SHA после отдельного разрешения.
