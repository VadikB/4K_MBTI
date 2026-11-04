# Постоянный профиль синтетических прогонов Codex

Версия `assessment-first-case/1.1`, 04.11.2026. Область — настройка и диагностика
пути «суперадмин → первый Case» в новой owned-БД. PATH-START-01 не передан в
исполнение. Методологическое согласование, CURRENT, приёмка пилотной программы,
merge и deploy этим профилем не объявляются.

## Подключение к заданиям

Профиль подключён из `AGENTS.md` и `tests/README.md`. Для явно согласованного
синтетического задания Codex применяет его без повторного ручного создания
аккаунтов или ввода credentials. В задании достаточно указать профиль и отличия.
Он сам не создаёт новые задания и не запускает периодические проверки.

## Машина и однократные доступы

Проверенная машина: `vadim_bogachev@178.236.26.203`, Linux. Нужны Python 3.12 с
`requirements.txt`/`requirements-test.txt`, Node/npm с `npm ci`, Chromium Playwright
и системные библиотеки (`npx playwright install chromium`), PostgreSQL на localhost
с правом CREATE/DROP собственной БД, свободный порт 18861 и HTTPS-доступ к DeepSeek.

SSH key подключается один раз средствами машины, без копирования в репозиторий.
Owner-only файл доступа (`0600`) передаётся через `--env-file`; runner читает его
как dotenv-данные и копирует только allowlist. Нужны `DEEPSEEK_API_KEYS` (или
`DEEPSEEK_API_KEY`), `DEEPSEEK_MODEL=deepseek-flash`. Допустимы ключи `_2/_3`,
`DEEPSEEK_BASE_URL`, `DEEPSEEK_MAX_CONCURRENCY`.
`STAND_ADMIN_URL` передаётся через окружение: только localhost maintenance DB
(`postgres`, `agent4k_pytest`, `task11_pytest`). Для проверенной машины URL
строится в памяти из `DB_USER`/`DB_PASSWORD` защищённого env-файла и явно выбранного
порта `--db-admin-port 55432`. Рабочая DB_NAME не используется.

Доступы не печатаются и не включаются в Git/evidence. State с одноразовыми паролем
и DB connection создаётся с правами `0600` и удаляется при cleanup; его нельзя
прикладывать в CI. Почтовые action tokens живут в памяти тестового приёмника.
Пароли аккаунтов генерируются и подставляются автоматически.

## Команда

Из checkout с реализацией профиля:

```sh
/home/vadim_bogachev/projects/Agent4K-Test/.venv/bin/python \
  scripts/assessment_first_case.py \
  --env-file /home/vadim_bogachev/projects/Agent4K-Test/.env \
  --python /home/vadim_bogachev/projects/Agent4K-Test/.venv/bin/python \
  --directory /home/vadim_bogachev/evidence/assessment-contour-final
```

`--preflight-only` проверяет PostgreSQL connect/CREATEDB, запуск Chromium, Python,
Node, provider configuration и фактический порт. READY относится к машине;
BLOCKED сохраняет причины в `preflight.json` и возвращает exit 2. Реальный provider
проверяется в основном прогоне; preflight не расходует tokens.

Та же команда с `--check-bootstrap` создаёт новую owned-БД, выполняет bootstrap,
минимальный seed, выгружает источники и штатно удаляет БД без LLM. Этот режим
проверяет повторяемость lifecycle и не заявляет прохождение browser-пути.

## Сценарий и границы подмен

Runner переиспользует `scripts/test_stand.py` и PATH29 browser-сценарий.
Bootstrap создаёт схему и существующие базовые определения. Full-path seed отдельно
создаёт только тестового суперадмина и точные исходные артефакты. Проверяет users=1,
organizations/memberships/assignments/profiles/cycles=0. Общий E10.2 seed не вызывается.

В отдельных browser contexts суперадмин создаёт организацию, подключает программу
и добавляет администратора; администратор подтверждает email, устанавливает пароль,
подтверждает анкету, добавляет участника с должностью и назначает оценку; участник
принимает приглашение, задаёт пароль, проходит знакомство и штатную подготовку.
Mail sink принимает только `@example.test`; внешняя доставка людям не проверяется.
Reload, повторный вход, две вкладки и потеря ответа prepare проверяют повторное
чтение и отсутствие дублирования preparation job.

Тестовая задержка worker служит проверке loading/reload; после снятия задержки
исполняется реальная очередь. Real-provider: `--gateway 0 --provider real`.
Готовые profile/Cycle/AS/admission DTO не подставляются. Оценочных ответов runner
не отправляет. После явного старта время идёт по M7 до остановки приложения и cleanup.

## Источники и синтетический допуск

Программа `path29-browser-specialist/1.0` ссылается на отдельный
`path-start-functional-diagnostic/1.0`, один `CASE.SPEC.02 v0.6`, пакет
`functional-personalization/0.5`, runtime `functional-personalization-runtime/1.2.0`.
Файлы пакетов остаются WORKING/runtime disabled. В disposable DB-копии всех девяти
Cases меняются ровно `/status` и `/author_case/Status` на FROZEN; содержательный текст
и индикаторы не меняются. Это техника из `tests/llm/test_m10_real_cycle_db.py`.

`source-provenance.json` сохраняет полный импортированный Case JSON, исходные и
импортированные checksums, все отличия пакета, QA evidence JSON/checksum и решение
admission. Контракт `m5_catalog_integrity/1.0.0` требует scopes `case_format`,
`case_dialogue`, `assessment_situation`, eligibility `user_admission`, usage scope
`assessment`, origin type `human_review`. Поэтому fixture-строки технически
используют этот origin type, но явно помечены `synthetic=true`,
`methodology_approval=false`, actor `synthetic-fixture:assessment-first-case/1.1`.
Это тестовые assertions изолированного контракта, не запись о состоявшемся
человеческом/методологическом review. Реальный LLM-tester заново проверяет каждую AS;
PASS входных fixtures не заменяет его admission.

## Обязательные доказательства

- Generation, все final tester и challenger batches принадлежат одной preparation
  operation; после repair проверяются конечный кандидат и его новый admission
  PASS либо PASS_WITH_WARNINGS при `admitted_for_participant=true` — по существующему
  продуктовому контракту. INCOMPLETE, FAIL, REVIEW_REQUIRED и недопущенная AS
  запрещают успешный результат. Продуктовые правила admission не меняются.
- Operations считаются по уникальному `operation_id`: повторная ссылка на repair
  не удваивает tokens/число вызовов. Лимиты продукта не расширяются.
- Сравниваются однотипные объекты: candidate с accepted candidate; compiled Case с
  `AS.case_ref`; snapshot с пересчитанным snapshot checksum; execution payload с
  execution ref; participant payload с предъявленным payload. Разные объекты не
  обязаны иметь одинаковый hash.
  Контракт генератора хеширует compact sorted UTF-8 JSON без завершающего LF;
  Case/package/QA/snapshot/participant payload используют `m5_case_runtime` с LF.
- После start HTTP 201 сохраняются Cycle/Session/AS start times, AS ID, тот же
  candidate/snapshot, независимый owner runtime GET, совпадение introduction с DOM,
  screenshot и фактические 0 assessee turns в БД.
- `failure.json`/`failure-receipt.json` содержат первый неуспешный шаг. Provider или
  admission FAIL сохраняется без fallback. Продуктовый дефект регистрируется для
  будущего пакета; настройка не включает скрытое исправление продукта.

## Evidence и очистка

Каждый запуск получает новый UUID и `product4k_pytest_<uuid>` с точным owner marker.
Evidence: `run.json`, `source-provenance.json`, pre-start receipt,
`first-case-receipt.json` либо failure, screenshots и `cleanup.json`.
`code-identity.json` фиксирует HEAD/branch/main/status и SHA-256 исполняемых файлов;
`runner-result.json` — итог, exit code и пути.
После всех browser assertions и штатного cleanup записывается `completion.json`:
run ID, status, exit code и SHA-256 конкретного финального receipt. Родительский
runner отдельно записывает `process-result.json` с фактическим exit дочернего
процесса только для созданных этим вызовом run ID. Ошибка teardown/timeout не
превращается в PASS из-за уже существующего receipt.

Сводка допускает PASS только при нулевом exit, успешном completion с совпадающим
run ID/hash, отсутствии failure/failure-receipt/cleanup-deferred, валидных pre-start
и first-case receipts, screenshot и cleanup именно этой owned-БД. Browser и сводка
используют один `preparation-receipt.mjs`: стадии, admission конечного кандидата,
однотипные hashes, цепочка candidate → saved AS → presented AS, start и 0 ответов.
Пустые/повреждённые JSON и недоступный validator дают FAIL с безопасными
`validation_errors`. Нулевой exit процесса без доказанного результата тоже даёт
ненулевой exit runner. Пустой набор запусков — FAIL; bootstrap остаётся отдельным
`PASS_BOOTSTRAP_ONLY`, не browser PASS. Для offline summary также нужен Node.

`--summarize-only` пересобирает `runner-result.normalized.json` по сохранённым
evidence без доступа к БД/LLM. Сводка отдельно считает уникальные операции и
завершённые HTTP-вызовы из безопасных строк server log. Tokens доступны для
сохранённых ответов; расход предыдущего malformed JSON-ответа продуктовый trace
не сохраняет, поэтому при JSON retry общая стоимость не заявляется полной.
Исторические evidence не переписываются. Старый receipt без completion/process
record не получает новый PASS при нормализации: завершение не доказано по новому
контракту. Прежние факты lifecycle/export проверяются по сохранённым первичным
доказательствам, а не дорисованным completion. Исторический PREP-DIAG-01 — UNKNOWN;
ошибки harness не доказывают причину его INCOMPLETE.

После сохранения evidence runner останавливает только свой server, вызывает
`test_stand.py destroy`, проверяет точный owner marker и отсутствие БД, удаляет state.
Без FORCE, без удаления чужих БД/общих пользователей. При ошибке cleanup результат
не считается чистым успехом; сохранённый state используется штатным destroy после
устранения причины.

Для уже начатой подготовки cleanup разрешён только после записи и readback terminal
receipt (`completed`/`failed`). Общий модуль `tests/browser/fixtures/receipt-file.mjs`
выполняет write/fsync/readback до удаления БД. Если выгрузка не сохранена или операция
ещё running, приложение останавливается, но owned-БД/state сохраняются;
`cleanup-deferred.json` содержит причину и путь к state без его секретного содержимого.

Бесплатная регрессия экспортёра:

```sh
STAND_ADMIN_URL='<localhost maintenance URL из защищённого окружения>' \
  /path/to/python tests/assessment_first_case_export_regression.py \
  --directory /path/to/new/export-regression
```

Регрессия создаёт новую owned-БД и явно вставляет синтетическую failed operation:
это подстановка отрицательного результата только для проверки DB collector →
check IDs/statuses/safe reasons/candidate refs → общий write/fsync/readback → DROP →
повторное чтение того же файла. Реальный LLM и продуктовая генерация здесь не
исполняются. Результаты этой регрессии не объясняют причину PREP-DIAG-01.

Откат — возврат адресных изменений runner/tests/ссылок; схемы и опубликованные
источники не мигрируются. Отчёт: `docs/evc/tasks/assessment-first-case-contour.md`.
