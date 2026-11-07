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
