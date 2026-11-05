# Финальная читающая сверка схемы

05.11.2026, выполнено до release/main. Основание — разрешение владельца на сверку
серверного Agent4K-Test/.env без активации, затем «ок спасибо идем дальше».
Runtime handoff38dd551 / tested199e7c3 не изменён; это отдельный evidence sidecar.

Результат **EXACT_SCOPED_SCHEMA_MATCH**: все32 таблицы затронутого пути,
353 колонки с типами/nullability/defaults,191 constraint,84 index,16 trigger с
состоянием и MD5 определения функции совпадают с независимым empty bootstrap.
Общий canonical metadata SHA-256:
`c18922b95d6223262d23cc6edf1c060ac66b9f84243feee076d32baae586a065`.
`missing/changed/extra=[]`. Это проверка указанной области, не всех объектов БД,
данных, опубликованных программ или методологического/AS admission.

## Способ выполнения и безопасность

`READ_SCHEMA.py` передан серверному Python через SSH stdin, без записи/установки
файлов на сервере. Прямой psycopg, `default_transaction_read_only=on`, repeatable read,
statement_timeout15s/lock_timeout2s, затем rollback. Все семь SQL — SELECT/SHOW
только pg_catalog. Приложение не импортировалось, bootstrap/ensure/seed/publish не
вызывались. `.env` использован как данные для подключения внутри процесса;
пароли/ключи/параметры соединения не печатались и не попали в evidence.

Фактическая команда (из feature worktree):

```sh
ssh -i /Users/vadim_bogachev/.ssh/mws_key -o BatchMode=yes -o ConnectTimeout=10 \
  vadim_bogachev@178.236.26.203 \
  '/home/vadim_bogachev/projects/Agent4K-Test/.venv/bin/python - --env-file /home/vadim_bogachev/projects/Agent4K-Test/.env --checkout /home/vadim_bogachev/projects/Agent4K-Test' \
  < docs/evc/evidence/path-pilot-schema-readback/READ_SCHEMA.py \
  > docs/evc/evidence/path-pilot-schema-readback/working-schema.json
```

Эталон — существующий `scripts/test_stand.py create/bootstrap`, код38dd551, **новая
собственная локальная** PostgreSQL16 pytest-БД в tmpfs контейнере74c38b5e….
Без seed/запуска приложения/аккаунтов/LLM. Та же программа читает metadata эталона
после проверки owner marker; сравнение выполняется offline через `COMPARE.py`.
После сохранения metadata выполнен штатный marker-protected destroy без FORCE,
state удалён; затем точный контейнер остановлен/AutoRemove. Удалены только временные
эталонные данные, воспроизводимые bootstrap; evidence сохранено. Рабочая БД не менялась.

## Первичные доказательства и воспроизведение

- `working-schema.json` / `expected-schema.json` — metadata receipts, READ ONLY flags,
  время, хеш; server checkout SHA только в рабочем readback.
- `comparison.json` — точное сопоставление всех записей и пустые дельты.
- `CHECK.py` / `regression.json` — позитив,11 negative schema mutations и4 unsafe/hash
  record negatives; проверка7 read-only SQL literals/отсутствия Api imports. Только offline.
- `owned-db-cleanup.json` / `result.json` — lifecycle/ownership и сводный итог.

Для независимой проверки после распаковки, без БД/сети/ключей:

```sh
python3 COMPARE.py expected-schema.json working-schema.json
python3 CHECK.py
shasum -a 256 -c SHA256SUMS
```

Сборщик требует psycopg/dotenv, уже установленные на проверенных машинах. Offline
compare/regression — Python standard library; текущая проверка Python3.12.13.
`schema_migration_required_by_this_change=false` относится только к этому результату:
runtime сохраняет новый JSON в существующих колонках. Не разрешает автоматически
новую программу/настройки или изменение любых published definitions.

## Раздельные статусы

Remote main свежим `git ls-remote`:2dc98c6/2.0.64. Серверный checkout тот же.
Новый runtime не устанавливался, process/version readback отдельно NOT_RUN.
Ветка содержит готовый локальный T1; CI NOT_RUN, push/PR/merge/deploy/version bump
не выполнялись. Публикация/активация новой программы и paid PATH остаются отдельными
решениями. PREP-DIAG-01: историческая первопричина UNKNOWN, не изменена сверкой схемы.

Следующий шаг — R1: согласовать release version и полномочия push/PR→CI→merge/test.
Наличие совместимой схемы не заменяет обязательный CI/review или приёмку runtime.
