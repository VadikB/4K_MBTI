# PATH-PILOT-HARNESS-01 — передача бесплатной доработки

05.11.2026. Scope — существующий синтетический инструмент, не новый продуктовый
runtime. Основание — ответ владельца «да» на исправление seed и точной версии.
Подготовка программы сохранена отдельным commit f211e7184e226b202529e14caf6e2f54478601fa;
runtime baseline/main —3385145201d5d365e08e9e8a6a6fb7e12a0aa258 /2.0.65.

## Реализация

| Требование | Реализация | Доказательство / ограничение |
| --- | --- | --- |
| SEED-01 | Program table добавлена в точный allowlist `reserve_release_ids`; только isolated prefix и свободный диапазон ID | Позитивная регрессия первоначально FAIL для program table,3 других таблицы PASS; исправленный позитив и прежние/новые негативы PASS. VERIFY отдельно извлекает baseline-функцию из неизменяемого3385145 и воспроизводит отказ до SQL |
| Exact source, без latest | В существующий runner добавлены `--program-receipt`, `--program-receipt-sha256`, `--program-version` | Все три обязательны для внешнего источника; проверка до env-file/preflight/DB; повторная проверка в seed. Legacy1.1 byte pin сохранён |
| Привязка browser | Вместо литерала1.1 сверяются выбранные id/code/version/assignment/status/config/catalog/definition checksum до/после start | Общий `verifyPublishedProgram`, Node positives для1.1 и synthetic-next-version, drift каждого поля до/после — отказ |
| Доказательства после cleanup | Exact receipt bytes сохраняются с fsync/readback; compact ref — в state/run, исходный source — в provenance | Summary читает сохранённую копию и SHA/version, а не внешний путь; подмена/утрата bytes/refs и drift readback дают FAIL |
| Прежний admission | verifyPreparation/verifyFirstCase по-прежнему проверяют обязательные стадии, terminal candidate, AS/lineage/time/start0answers | PASS_WITH_WARNINGS не обходит FAIL/INCOMPLETE/unadmitted/missing-stage или любые прежние негативы; продуктовая политика не менялась |
| Повторяемость/очистка | Новый owned bootstrap для1.1, другой для synthetic future metadata; третий — negative source | Минимум users1/остальное0; исходные27 Case QA JSON/checksums совпадают. Три owner-verified cleanup без FORCE |

Изменены scripts/assessment_first_case.py, source/seed/input/browser fixtures и
адресные Python/Node/integration tests. Api/, web/, assessment_definitions/,
pyproject.toml и uv.lock не изменены. Профиль и tests/README отражают CLI и ограничения.
Никаких новых prompts, admission/repair rules, M0–M8 или публикации CURRENT.

## Различие доказательств

Future metadata использует строку **synthetic-next-version**, ID3 и точный
snapshot как **синтетическую модель метаинформации**, а не как состоявшуюся
публикацию1.2. Исходное Case QA копируется из прежнего опубликованного receipt,
новый human review не выдумывается. Назначения/профили/Cycles в bootstrap не создаются.

Component-only PATH29 выполняется с provider disabled и явной upstream plan-policy
подстановкой прежнего профиля. Он проверяет отсутствие регрессии сценария, но не
реальный opt-in пилот, generation/tester/challenger или полный PATH. В real/full PATH
такая подстановка по-прежнему запрещена. Положительный unit summary также проверяется
на явно синтетических AS/stage/start DTO, не выдаётся за продуктовый PASS.

Файлы первоначального offline-проекта f211e71 сохранены. Его VERIFY предназначен
для той исторической базы и ожидаемого дефекта, не для текущего исправленного кода.
Новый [VERIFY.py](../evidence/pilot-program-harness/VERIFY.py) проверяет before/after,
неизменность1.1/product sources и связи трёх owned receipts без DB/.env/LLM imports.

## Проверки и evidence

Точные команды/stdout/exit и hashes исполняемых файлов находятся в
[evidence](../evidence/pilot-program-harness/). Локальный минимум EVC:
backend, Node regression, настоящий isolated bootstrap/integration, component browser,
diff и docs/CLI checks. HTTP/product SQL проверки из PR170 применимы только к
неизменённому Api3385145, а не доказательство нового harness CI. Новый обязательный
remote CI не запускался: push/PR пока не разрешены.

Итог: **backend906 PASS**,334 deselected (один прежний Starlette warning);
**Node66 PASS**, **integration3 PASS**, **component browser1 PASS**.
Последние browser/Node и backend относятся к окончательным файлам; bootstrap3 —
к тому же неизменённому source/seed/Python input path. JSON, docs-ссылки и diff PASS.
Инфраструктурный cleanup:0 owned databases/0 app connections перед остановкой
точного task-labeled Docker; AutoRemove/absence подтверждены отдельно.

Доказательства записаны до/после owned cleanup. Рабочая БД из server `.env` не
читалась и не менялась; вместо неё создан отдельный Docker PostgreSQL на случайном
localhost-порту. Provider credentials не использовались; реальные provider calls0.
Code tests могут исполняться до коммита: их точное содержимое связывается SHA256
файлов в probe/readback и после коммита; старый Git HEAD в precommit probe не
выдаётся за commit уже изменённого кода.

## Остаток и откат

Публикация specialist_pilot@1.2 не выполнялась: номер остаётся проектом.
Требуются отдельные разрешения по плану выпуска на version/publication/retirement,
подключение постоянных организаций (если потребуется) и один оплачиваемый PATH.
Новому runner всё ещё нужен настоящий exact-version source receipt после публикации;
готовность harness его не заменяет и не даёт автоматического допуска LIMITED.
Платный PATH/продуктовая приёмка — NOT_RUN, PREP-DIAG-01 root_cause=UNKNOWN отдельно.

Откат локальной доработки — адресный revert harness; published sources/snapshots
не переписывать. Созданные DB/state удаляются только штатным owner-verified destroy;
не переносить bootstrap-данные в постоянную БД. Новые migrations отсутствуют.
Main/test остаются на последнем принятом2.0.65; новый код только в локальной ветке,
новый CI/review/merge/deploy не объявляются выполненными.
