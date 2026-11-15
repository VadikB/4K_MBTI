# P4K-SYN-LIMITS-01 — REPORT

Редакция задания 1.0 от 14.11.2026. Проверен неизменённый код
`68a52a7c21bfe7759d2522a644ad194f7d111f4e` / продукт `2.1.7`.
**Аудит выполнен с явно указанными NOT_RUN/PARTIAL. Допуск полного controlled
либо реального оценивания не подтверждён. Продукт не изменён.**

Найдены три конкретных пробела проверенного контура: предел AS не ограничивает
ASK-loop; локальные JSON/transport retries не образуют сохраняемый общий бюджет
операции на проверенной границе; cleanup `test_stand_check.check()` не завершает
всё дерево процессов. Есть штатный отказ при конфликте controlled/real и запрет
удаления при неизвестном execution export. Эти частные свойства не являются
PASS продукта или всего профиля.

## База, профиль и воспроизводимость

- Исходный основной checkout: `codex/tg-student-channel-api`,
  `bc63a8ee4a21c36a124dd0040bd44a9f9cccefed`, с чужими изменениями.
  Их исходный список — [workspace-before.txt](workspace-before.txt).
- Исследование начиналось на этом HEAD, затем до проб выбран свежий main:
  `68a52a7c21bfe7759d2522a644ad194f7d111f4e`. Все динамические пробы относятся
  только к нему. Base=tested HEAD; собственных code commits/diff нет.
- Изолированный checkout: `/private/tmp/p4k-syn-limits-01-20261115`, detached HEAD,
  перед пробами чистый. Промежуточно просмотренный локальный `origin/main`
  `b0bf7a4e…` не выдаётся за актуальный main и не тестировался.
- Первое `git ls-remote origin refs/heads/main` внутри sandbox: exit128,
  `Could not resolve host`. `socket.getaddrinfo` внутри sandbox отказал, вне
  sandbox вернул адрес. Однократная успешная сверка remote main вне sandbox
  вернула `68a52a7c…`; затем `git fetch --no-tags origin 68a52a7c…` получил
  точный объект. Причина исходной ошибки — ограничение sandbox, не доказанная
  неисправность DNS Mac. Рабочая ветка пользователя не переключалась.
- Runner `scripts/assessment_first_case.py`: `assessment-first-case/1.1`;
  выбранные completion helpers: `assessment-execution-contour/2`,
  `tests/browser/fixtures/assessment-completion-profile.mjs`;
  отдельный lifecycle runner — `scripts/test_stand_check.py`.
  Версия runner также зафиксирована точным SHA-256, а не только строковым label.
- Python3.12.13 из существующего `.venv`, Node v25.5.0. Ничего не устанавливалось.
  [identity.json](identity.json) содержит source/runner hashes и сверку manifest;
  [static-evidence.txt](static-evidence.txt) — адресные строки именно tested SHA.

## Карта существующих ограничителей

Значения относятся к коду/defaults tested SHA; рабочие `.env` не читались.
Наличие настройки отделено от выполненного пути. «Не найдено» ограничено
перечисленными файлами, не является утверждением обо всех сервисах компании.

| Ограничение | Код / значение | Область, подтверждение и пробел |
| --- | --- | --- |
| Общий deadline run | Python entrypoint `assessment_first_case.main`: `subprocess.run(npx…)` без timeout. PATH29 `test.setTimeout`: 240000 ms либо 900000 ms для real/controlled | Playwright ограничивает отдельный test, не самостоятельным deadline Python coordinator. Полный запуск не выполнялся. Короткого 5–10 s профиля нет; L01 NOT_RUN |
| Таймауты действий | PATH29 subprocess180 s, readiness30 s, preparation45/600 s; completion `waitRuntime`120 s, report180 s, HTTP-response ожидания30 s, click15 s. `test_stand_check`: CLI150 s, startup45 s, shutdown20 s. Gateway default120 s; `_strict_json_call` передаёт300 s | Это разные локальные ожидания, не единый бюджет run. Проверяемые значения превышают внешние30 s, поэтому длительное ожидание не запускалось |
| Отсутствие прогресса | `product_cycle_preparation_queue`: heartbeat30 s продлевает locked_at; stale lease10 min; completion заново начинает локальный timer при каждом `waitRuntime` | Heartbeat не доказывает нового сохранённого события. Отдельный no-progress deadline в просмотренном driver/runner не найден. БД worker не запускался |
| Шаги / AS / Turns / ASK / переходы | Completion default `maxSituations=12`; в L02 штатный параметр2. `seen` отклоняет повтор AS между outer-loop iterations. `test_stand.drain_browser_orchestration`:50 steps | Внутренний ASK-loop счётчика не имеет; maxSituations не ограничивает ответы внутри AS. L02:1095 ASK-ответов/одна AS, остановка только извне. Общий лимит Turns/переходов run не найден. Продуктовые ограничения конкретного Case и время Cycle не приравниваются к лимиту driver |
| Transport / SDK / JSON retry | Gateway использует urllib, не retry SDK; до K попыток по K ключам. `_strict_json_call`:2 chat-вызова при malformed JSON | L04: K=2, timeout+malformed JSON дали4 transport попытки на вход. `retry_policy.acceptance_max_attempts=1` в provider manifest не является исполняемым общим лимитом: gateway обходит список ключей |
| Challenger / repair | `m5_functional_generation_service.prepare`: одна ветвь generation repair + повтор tester; tester/challenger могут вызывать `_strict_json_call` | Статически конечная ветвь, но её вложенные вызовы не списывают найденный общий operation budget. Полный prepare/repair не запускался; не выдаётся за поведенческую проверку repair |
| Queue retry и restart | Legacy `assessment_preparation_queue`: default max_attempts3, lease900 s, heartbeat, exp-backoff до60 s. Новый product queue: attempts увеличивается, stale requeue после10 min, attempt_token fence | У product `_claim` нет проверки общего max attempts/calls/cost. Fence защищает право записи текущей попытки, не отменяет уже отправленный запрос. Restart/crash и DB-idempotency не проверялись; разные очереди не смешиваются |
| Повтор всего теста | `playwright.config.mjs`: retries0, workers1; Python runner собственного retry browser не содержит | Статическая настройка. Два входа L04 — контролируемый вход одной пробы, не перезапуск продуктового теста |
| Общий бюджет операции | `_strict_json_call` хранит failures в локальном списке; gateway trace имеет transport_attempts на один chat. Operation ID используется как routing key | L04: один ID,4→8 fake попыток при втором входе. Общего сохраняемого/reserved счётчика на этой границе нет. Общая стоимость, лимиты tokens/денег и durable queue целиком не доказаны |
| Tokens / стоимость / уже отправленные запросы | Provider draft1.0.0 defaults max_tokens12000; конкретные callers передают свои значения, в L04 max_tokens20. Summarizer считает завершённые запросы из log и предупреждает о неполном usage malformed-ответов | max_tokens — предел одного ответа, не бюджета операции. В L04 fake usage9 ×4 ответов сохранён в диагностике отдельно; это не платёж/стоимость. Timeout не доказывает отсутствие расхода реального запроса |
| Параллельность | Gateway BoundedSemaphore max(1,deepseek_max_concurrency), default10 на instance; queue wait default30 s. Preparation default2; legacy queue threads1 | Нет доказанного общего межпроцессного cost reservation. Существующий `test_deepseek_capacity.py::test_concurrency_queue_returns_clear_overload_error` проверяет semaphore overload, а не operation budget reservation; прочитан, PASS не переиспользуется и новый конкурентный стенд не строился |
| Остановка process tree | PATH29: SIGTERM server PID,5 s, затем SIGKILL и ожидание exit; closes browser contexts. `test_stand_check`: terminate+wait20 только одного Popen | L05 на actual check() сохранил потомка PID7503 после native cleanup. Внешний supervisor завершил свою process group. Python top-level runner не содержит собственного signal/finally teardown для всего дерева |
| Docker / restart policy | Рассмотренный локальный test_stand работает через явный localhost PostgreSQL, не запускает Docker | Контейнеров аудита нет; restart policy N/A. CI PostgreSQL services и job deadlines10/25/20 min, full-verification15/15/2 min — внешние CI-границы, не проверенный локальный cleanup. Restart/crash временного Docker NOT_RUN |
| Export / удаление / итог | `readExecutionExport`: context, persistReceipt/fsync/readback/hash; `destroyOwnedStandIfAdmitted` отказывает при неизвестном terminal export. PATH29 сохраняет cleanup-deferred, останавливает server, затем cleanup gate. Stand destroy: target/owner marker, DROP без FORCE, проверка отсутствия, удаление state | L06: ошибка readback,0 destroy commands, файл диагностики остался; summarizer FAIL даже при process_exit0. Это helper/spy и файловая проверка, не сохранность настоящей БД |
| Аварийное восстановление STATE | test_stand хранит run_id/DB/marker/connection; штатный destroy требует owner/target, запрещает FORCE | В записываемом state нет process-tree registry. Crash-recovery по реальному saved STATE не исполнялся. Диагностический l05-state не является новой защитой штатного runner |

## L01–L06: ожидаемое, фактическое и предел доказательства

| Проба | Ограничитель / ожидание | Фактическое и статус | Первичное доказательство / границы |
| --- | --- | --- | --- |
| L01 | Общий срок есть в Playwright test; отдельный no-progress limit не найден. Неизменный processing должен закончиться native отказом | **NOT_RUN** динамически:120 s minimum wait не помещается во внешний30 s и короткой настройки нет. Локальный timeout не объявляется общим deadline | [L01.json](L01.json), static-evidence. Wall/exit не измерены, продуктовый FAIL не присваивается отсутствующей среде/короткому профилю |
| L02 | maxSituations2; ожидался конечный общий лимит повторов | **FAIL в driver ASK-loop**: чередовались уже повторяющиеся q1/q2 внутри одной AS, terminal отсутствует. Принято1095 ASK answers,1096 assessee turns с первым ответом; native причины остановки нет, прервал внешний timeout2 s | [L02-counter.json](L02-counter.json), [L02-recovery.json](L02-recovery.json), resources.jsonl. Actual driver + минимальный page adapter, без backend/БД. Повтор q1/q2 проверяет цикл ASK; replay одного неизменного ID отдельно не проверялся. Wall/exit не сохранены из-за ошибки supervisor; точное измерение не придумывается |
| L03 | Native profile должен отвергнуть real в controlled режиме до отправки | **PARTIAL**, проверенная ветвь **PASS**: actual PATH29 callback отверг simultaneous real+controlled с `CONTROLLED_PROVIDER_REQUIRES_PUBLISHED_OWNED_PATH`; backend/browser не запускались, independent interceptor0 | [L03.json](L03.json), [L03-guard.json](L03-guard.json), L03.log. Actual callback выполнен через vm с заменой импортов/Playwright registration, guards не переписаны. Missing controlled adapter и Python app-install path после owned DB gate — NOT_RUN; универсальный запрет внешних вызовов не доказан |
| L04 | Локальные retries конечны; общий operation budget должен учитывать их и повторный вход | **FAIL на проверенной границе**, остальное **PARTIAL**:2 transport×2 JSON=4 искусственные попытки; тот же ID при повторном входе получил ещё4. Оба входа прекратились `M5_FUNCTIONAL_PROVIDER_JSON_INVALID`. Внешний timeout не потребовался | [L04.json](L04.json), [L04-guard.json](L04-guard.json). Реальные `_strict_json_call` и gateway, urllib заменён искусственным транспортом до вызова. Repair/challenger полного prepare, durable queue re-entry, tokens/cost/reservation целиком не выполнялись; их глобальное поведение не выводится только из счётчика8 |
| L05 | Native interrupt должен остановить свой parent и потомков | **FAIL для process tree**, **PARTIAL для crash/STATE**: actual SIGINT после saved child PID; native check() остановил parent7502 (exit−15), descendant7503 ещё существовал по kill(pid,0). Только внешний supervisor уничтожил группу7500; после cleanup PID/PGID отсутствуют | [L05.json](L05.json), [diagnostics/l05-state.json](diagnostics/l05-state.json), [resources-final.json](resources-final.json). Actual finally+real own process tree; команды create/bootstrap/seed/smoke/destroy и HTTP — spies. Отдельный native ps до внешнего kill не записан; наличие PID не подменяется универсальной метрикой CPU. PostgreSQL/Docker и аварийное SIGKILL recovery не проверены |
| L06 | Readback failure при unknown должен запретить удаление и PASS | **PARTIAL**, helper gate и честный итог **PASS**: `EXECUTION_EXPORT_READBACK_MISMATCH`; cleanup deferred; destroy commands=[]; испорченный export сохранён. При process_exit0 summarizer дал FAIL/exit1 | [L06-export.json](L06-export.json), [L06-summary-verified.json](L06-summary-verified.json), [L06-verify.log](L06-verify.log). Реальные helper и summarizer; сохранность реальной БД/состояния Cycle — NOT_RUN. Полный validator suite не запускался; summarizer штатно вызвал свой validator только на отрицательном файловом входе |

### Время, команды и ошибки диагностического входа

Точные argv/start/PID/PGID/таймауты — [resources.jsonl](resources.jsonl);
wall/exit/teardown — [probes.json](probes.json). Время в нём UTC, здесь Москва:
L02 старт10:00:55; L03–L06 старт10:01:45–10:01:47.
L03 wall0.4330 s; L04 1.3309 s; L05 0.3906 s; L06 0.5820 s;
адресный L06-verify0.4641 s. Это длительность subprocess с внешним teardown,
не время участника. Остальные native процессы закончились до внешнего timeout.
Диагностические scripts возвращают0 при успешном сборе evidence, даже если
проверяемое свойство FAIL; код0 этих scripts не является PASS продукта.

Команды из tested worktree:

```sh
python3 /Users/vadim_bogachev/Developer/4K/docs/evc/evidence/p4k-syn-limits-01-2026-11-15/diagnostics/run.py
python3 /Users/vadim_bogachev/Developer/4K/docs/evc/evidence/p4k-syn-limits-01-2026-11-15/diagnostics/run.py L06-verify
```

Первый supervisor после teardown L02 не смог вызвать `/bin/ps` в sandbox,
exit1; L02 уже обнаружил дефект и **не повторялся**. Исправлено только сохранение
метаданных supervisor и пропуск уже запускавшихся проб. Продолжение вне sandbox
запустило только L03–L06, по одному разу. Отсутствие7387 проверено отдельно.
Точный exit/wall L02 потерян, поле null; configured2 s не называется измерением.
Сумма recorded wall L03–L06 и адресного repeat3.2006 s; L02 имел внешний2 s
и bounded teardown. Даже с диагностическими накладными расходами активные
пробы существенно меньше10 min; полных/длительных наборов не было.

Для L06 разрешён один адресный повтор **только summarizer**, исправивший
недостаточный диагностический вход: сначала был передан process_exit1,
что само могло вызвать FAIL. При повторе передан0, сохранены прежние файлы
export/cleanup; результат всё равно FAIL/exit1. Исходная summary сохранена
в L06-summary.json, уточнённая — L06-summary-verified.json. Продукт не исправлялся,
readback fault и полный маршрут повторно не исполнялись.

## Что остановил сам контур, а что внешний предохранитель

- **Native**: guard conflicting real+controlled; два локальных JSON-attempts
  каждого входа L04; непосредственный parent в L05; запрет destroy и FAIL
  summarizer при unknown/corrupt evidence в L06.
- **Только внешний supervisor**: бесконечное продолжение ASK в L02 и остаточный
  process tree в L05. Это подтверждает безопасность этой диагностики, не
  исправность штатного общего ограничителя.
- **Не установлено динамически**: общий deadline/no-progress L01, пропавший
  controlled adapter, общий durable operation budget, crash/STATE recovery,
  реальный DB-retention при export failure.

## Ноль реальных обращений и ресурсная сверка

Реальные LLM=0, mail=0 **для собственных диагностических процессов этого аудита**.
Перед импортом provider Python sitecustomize запретил socket.connect/DNS и чтение
`.env`; env построен по allowlist и содержит только synthetic значения.
Node preload запретил net/http/https/fetch до импорта проверяемого модуля.
L04 не делает HTTP: восемь вызовов — искусственный `urlopen`,4 malformed-ответа
и4 синтетических TimeoutError. Глобальный Python guard при этом оставался активен.
Счётчики L03/L04/L05/L06 guards равны0; external обращения не отправлялись.
Письма не создавались, диагностические сценарии не вызывали mail adapter; socket guard
дополнительно запрещает SMTP-сеть. Это не аудит чужих фоновых процессов машины.
L02 завершён сигналом, exit-hook guard-файл не появился: ноль здесь основан
на preload и полностью локальном page adapter, а не на отсутствующем counter.

Финальная проверка10:05:29+03:00: все8 зарегистрированных PID отсутствуют;
все6 собственных PGID отсутствуют по signal0 и адресному ps; ps exit1/пусто
означает отсутствие перечисленных PID. [resources-final.json](resources-final.json).
В каждом завершённом supervisor teardown занял около0.15 s; L02 stop выполнен
до сбоя ps. Не было killall/prune/чужого Compose. Контейнеры/БД/volume/browser/
server/worker/listening ports не создавались. Нельзя называть это проверкой
удаления реальной БД либо отсутствия чужих ресурсов.

Сохранены только эта папка evidence и detached worktree. В L05-fixture/state.json
и L06-run лежат **синтетические файловые входы**, не DB state с credentials.
Флаг database_preserved в отрицательном L06 fixture описывает тестируемую команду,
не утверждает существование настоящей БД. Остаточных вычислений аудита нет;
диагностика сохранена. Итог: `DATA_RETAINED_COMPUTE_STOPPED` в файловой области.

## Источники, версии, пробелы и связь с архитектурой

Прочитаны AGENTS, README, CONTRIBUTING, workflow, verification matrix, artifact
recipe, task template/review checklist; context/registry; decision-register
редакции08.11 и применимые SYN-CONTOUR-OWNERSHIP/PATH-START-01-SCOPE с первичными
профилем/handoff. STATE просмотрен для границы текущих задач; разрешения старых
paid PATH, публикаций или соседних карточек не применялись к этому аудиту.

Адресно прочитаны Change01 README и относящиеся к задаче фрагменты И-1–И-7 (PM и время,
исполнение/ошибки), M1 README и §§M1.5–M1.6/M1.9–M1.10, M7 §§5.3–5.5 и9.1–9.3,
ADR-002 C-34/45/46 и хранение/ошибки, change01-traceability по завершению/Results.
Контуры runtime, tests и CI перечислены в identity/static-evidence; быстрые
test source файлы прочитаны для выбора входов, их прежний PASS не заявляется reuse.

| Источник | Версия / статус / проверенная идентичность |
| --- | --- |
| Product Architecture context/registry | v1.0, WORKING вход Change01; без нового CURRENT |
| Change01 source.pdf | 1.0/01 WORKING; SHA-256 `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081`, совпал с manifest |
| M1 source.docx | v1.4 FROZEN/CURRENT=NO; SHA-256 `5fa5ab5735dfe57fac6ef3c93aca50d149fbd7abd365edf80d362c10e2d7a975`, совпал |
| M7 original DOCX | v1.3 FROZEN/CURRENT=NO; SHA-256 `50a0d53a3aaf6258957ecc6d9e89f27d922bfbe4cd55668185d475c87f4e2f10`, совпал; адресные разделы прочитаны по registered derived/M7-v1.3.md |
| Task SourceSet | docs/methodology/source-sets/2026-10-01/manifest.json; не M0 CURRENT Manifest |
| P4K.DEV.PRINCIPLES | v1.0/10.10.2026, доступная копия Downloads/P4K_UX_Fixes_2026-10-20/reference/P4K_Product_Development_Principles.txt, прочитана; hash в identity, отдельной записи в SourceSet нет |
| Common Glossary Reconciliation WORKING30.09 | Именованный оригинал не найден в checked repository tree и доступном списке Downloads; версия/содержание не реконструировались. PM/LU/AS/Cycle используются по явному заданию, Change01 и M1, не выдаются за сверку отсутствующего глоссария |
| P4K_Task_Setting_Analysis_and_Rules_2026-11-14.docx | Не найден по адресному поиску имён в репозитории и Downloads. Его нормы не реконструированы. Прямые ограничения данного TASK применены самостоятельно; полнота сверки с отсутствующим документом не заявляется |

Область поиска не включала вскрытие всех личных архивов, чатов или credentials.
В README Change01 осталось историческое указание отсутствия M7: actual manifest
и дополнение Registry уже регистрируют файл. Использована фактическая запись
manifest, не присвоен новый статус источнику/пакету/runtime.

| Правило → PM / контракт | Фактический код → проверка |
| --- | --- |
| M1.5, Change01 И-3: PM-03 готовит AS, C-34 передаёт её PM-04 | `m5_functional_generation_service` + gateway: L04 проверяет технические retries подготовки; не проверяет качество/admission новой AS |
| M1.6: конец сценария, закрытие AS и Cycle различны; PM-04, C-45/C-46 | Completion driver и cleanup gate: L02 выявляет отсутствие runner ASK-limit; L06 не вызывает destroy при unknown. Это не доказательство серверного автомата AS/Cycle |
| M1.9/M7.5.3: учитываемое время и календарный срок фиксируются отдельно; C-46 | `waitRuntime`/Playwright deadlines технические, не механизм изменения participant budget; L01 static/NOT_RUN, M7 DB-time не запускался |
| M7.9: QA подтверждает только фактически проверенную область | SHA/hash/синтетические входы и таблица L01–L06; helper PASS не выдаётся за пилот, GC, полный PATH/Report или методологическую приёмку |

Compaction: **NOT_RUN**, журнал конкретной сессии и применимые пороги не
предоставлены. Личные чаты/config не искались, конфигурация не менялась.

## Необходимые следующие исправления — без реализации

1. Определить и реализовать в существующем runner общий deadline и самостоятельный
   предел отсутствия сохранённого прогресса с коротким настраиваемым test profile.
   Отдельный владелец технического решения; не менять время участника/Cycle.
2. Ограничить общий счётчик driver steps/ASK/переходов внутри AS, включая
   повторение прежних ASK; сохранять причину остановки и текущий receipt.
3. Согласовать существующий operation-wide budget через transport/JSON retry/
   repair/queue/restart: attempts, отправленные calls, reserved usage и предел
   tokens/cost; доказать повторный вход и параллельное резервирование. Счётчик
   самого аудита не является такой реализацией.
4. Дополнить штатный bounded teardown всего собственного дерева процессов и
   восстановление по saved STATE; отдельно проверить сигнал/аварию и фактический
   readback. Не переносить гарантию supervisor на product runner.
5. Допроверить missing controlled adapter fail-closed на actual app-install path
   и unknown export на owned DB с фактическим retention/readback; до этого
   сохранить PARTIAL. Уже подтверждённые conflict/cleanup guards не переделывать.

Это перечень для следующих отдельных задач, не полномочие начать исправления.
Для снятия непроверенности источников нужен доступ к двум отсутствующим
именованным документам; основной технический аудит этим не продолжать.

## Приёмка, проверки и передача

Подтверждена только безопасная короткая диагностика существующих функций
completion/cleanup/provider retry на фиксированном SHA, под **внешним** bounded
supervisor и independent network deny. Штатный controlled PATH/EXEC/Report целиком
не аттестован; отсутствие общего прогресса/ASK/budget/process-tree доказательства
мешает техническому допуску дорогого/реального run. Этот отчёт такого допуска не
выдаёт. Исторические audit FAIL/PASS не переносились как новые результаты.

Изменённые пути: только новая папка `docs/evc/evidence/p4k-syn-limits-01-2026-11-15/`:
REPORT, diagnostic inputs, JSON/logs/источники проверок. Продукт, tests suites,
AGENTS/workflows, schemas и опубликованные snapshots не изменялись.
Новых предметных артефактов/долга ART/миграций нет; реестры не редактировались.

Локальная матрица применена как документальный аудит: diff/ссылки/согласованность
и синтаксис собственных диагностических файлов; итог в verification.json.
Полные backend/frontend/integration/browser suites, llm, CI/release — **NOT_RUN
по явному запрету TASK**, не заменяют обязательный CI будущего PR. PR/commit нет.
Самопроверка review checklist: scope/источники/чужие изменения сохранены,
сырые FAIL и пробелы не скрыты, source→code→probe записаны; product acceptance
и независимое human review не присваиваются.

Риски: конфиг/схема/deploy/API не менялись; безопасность ограничена синтетическими
входами/deny guards; остаточные вычисления отсутствуют. Откат — убрать только
собственные evidence/позже собственный detached worktree по адресному решению,
без удаления данных пользователя. Следующий минимальный шаг: владелец принимает
аудит и выбирает отдельную задачу по найденным ограничениям. Текущий план завершён;
открытых решений для сдачи этого отчёта нет. **STOP**, соседние работы не начаты.

## Сохранённая запись плана до первого запуска

started_at: 2026-11-15T09:52:30+03:00 (консервативно от первого действия).
deadline: 2026-11-15T10:37:30+03:00; исследования завершить до 10:27:30.
Один исполнитель; бюджет 45 минут, последние 10 — отчёт/остановка.
Отметка09:52:30 использована как консервативное начало бюджета; точное время
первого действия не было измерено. Первое инструментальное чтение часов —
09:53:05+03:00. Пробы завершены к10:04:32, ресурсная сверка —10:05:29;
отчёт и проверка evidence завершены около10:11. Бюджет не исчерпан.

## План и полномочия

Основание: прямой запрос пользователя выполнить P4K-SYN-LIMITS-01 rev1.0.
Результат: карта ограничений, L01–L06, первичные evidence и проверка остановки.
Исключено: изменение продукта/источников/норм, полный PATH/EXEC/Report, БД, реальные
LLM/письма, установка платформ, CI, commit/push/PR/merge/deploy/version bump/publication.
Все флаги выпуска false. Технические пределы диагностики не меняют время Cycle.

1. Завершено: разведка Git и источников; чистый изолированный worktree.
2. Активно: карта и подготовка адресных проб, без runtime-изменений.
3. Далее: однократные короткие пробы, отчёт и ресурсная сверка; STOP.

Стоп-условия EVC: восемь ответов «нет»: смысл, API/PM/схема, миграция/удаление,
предметные значения, формат runtime-артефакта, чувствительные данные/права,
откат runtime и выход за scope не меняются. Недостающие документы обозначаются,
их нормы не реконструируются. Решений о реализации не принимается.
Откат: удалить только собственную новую папку evidence после передачи; чужие
изменения и проверяемый код не трогать. Worktree сохраняется для воспроизводимости.

## Ресурсы до первого запуска

run_id: P4K-SYN-LIMITS-01-20261115-095230; владелец: текущий исполнитель аудита.
Основной checkout: /Users/vadim_bogachev/Developer/4K, ветка codex/tg-student-channel-api,
HEAD bc63a8ee4a21c36a124dd0040bd44a9f9cccefed, грязный; изменения пользователя не трогать.
Tested checkout: /private/tmp/p4k-syn-limits-01-20261115, detached
68a52a7c21bfe7759d2522a644ad194f7d111f4e; перед диагностикой чистый.
Свежий main сверён однократно вне sandbox; равен tested SHA. Локальный origin/main
до сверки b0bf7a4e8e4f0fe70c400525a373b9822229dfdc; fetch точного SHA не меняет
рабочую ветку и не присваивает baseline. Первичная DNS-ошибка — sandbox.
DB/container/browser/server/worker/volume/порты: не созданы; исходные чужие ресурсы
не исследуются и не останавливаются. В L05 разрешён только свой короткий process tree.
PID/PGID записывает supervisor в resources.jsonl сразу после Popen и до ожидания.
Каждая проба получает отдельную session/process group, timeout <=30 секунд;
остановка только os.killpg(свой PGID,SIGTERM), затем при необходимости SIGKILL,
проверка извне. Окно teardown <=30 секунд. Команды и результаты — probes.json.
Синтетический L05 STATE — diagnostics/l05-state.json, без credentials; volume нет.
Сеть и почта запрещены до импорта провайдера; окружение дочерних процессов строится
по allowlist, .env не читается. Внешний supervisor — защита аудита, не штатный лимит.

## Предварительно записанные пределы

- L01: waitRuntime=120000 ms, report wait=180000 ms; PATH29=240000/900000 ms.
  Настройки 5–10 секунд у этих путей нет: динамический L01 NOT_RUN по бюджету.
- L02: maxSituations=2 (штатный параметр; default12); внутренний ASK-loop без счётчика.
  Внешний timeout 2 s; повторяются ASK q1/q2 внутри одной AS, terminal не наступает.
- L03: controlled+real конфликт; штатный guard до запуска backend/browser.
  Независимый network guard обязателен; missing adapter отдельно не доказывается.
- L04: два синтетических ключа, transport до 2 попыток/chat, JSON до 2 chat/вход,
  один повторный вход с тем же operation ID как часть одной пробы. Общий бюджет
  operation в проверяемой функции не задан. Repair/queue/конкуренция отдельно.
- L05: check() terminate/wait20 s; дочерний короткий процесс с потомком;
  SIGINT после подтверждённого запуска, внешний timeout 10 s.
- L06: штатный fault=readback, cleanup gate, summarize_runs; timeout10 s.
  Spy не доказывает сохранность реальной БД; БД не создаётся.
