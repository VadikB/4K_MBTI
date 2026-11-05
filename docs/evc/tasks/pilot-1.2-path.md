# PATH-PILOT-RUN-01 — один контролируемый PATH программы1.2

## Результат, область и решение

Выполнено: **PASS**, exit0,376.508s, run `2ff983f12c67494b990b0f85284b8d70`.
Независимый offline CHECK/Node validator/повторная summary, primary byte hashes,
visual first-AS review и cleanup readback — PASS. Технический сквозной результат
получен в согласованном limited-pilot scope; человеческая приёмка отдельно.
Не повторять: paid допуск использован. Runner PID2719052 завершён, tool session33301 закрыта;
server evidence path-pilot-1.2-run-qxzr56r9, owned DB/state отсутствуют.
Пользователь ответил «идем дальше» на конкретный
вопрос об одном платном PATH, ориентир20 provider operations/около1.505 млн tokens
без гарантированного потолка. [Решение](../evidence/pilot-1.2-path/owner-decision.json).

Цель: существующим runner выполнить «суперадмин → первая AS» на runtime
e63eba67d77fb73f7fb9bb219bc3fe5d3807a909 /2.0.66, программе `specialist_pilot@1.2`, id2,
receipt SHA256 `09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b`.
Ветка `codex/pilot-1.2-path` от1ee2ec4; прошлые публикация и бесплатный bootstrap
сохранены, их исходная ветка не меняется. Main/test не меняются этой задачей.

## Источники и применимость

Повторно прочитаны README/CONTRIBUTING, полный существующий runner/browser PATH29,
playwright config(retries0), browser app/server/seed, профильassessment-first-case1.1,
pilot-plan-start-admission-contract v1. Неизменённые workflow/matrix/artifact recipe,
архитектурные context/Registry/M1v1.4(FROZEN/CURRENT=NO), Change01 manifest и
принятые exact P1–P3/M1–M4/T1 повторно используются из завершённой подготовки.
Bootstrap actual1.2:110 unit/PASS_BOOTSTRAP_ONLY,9 Cases/27 original QA, минимальные
counts1/0 и cleanup PASS. Полный M2=61, план39/22 вне,55 условий, маршрут/время
сохраняются. Никакого нового human review, содержания или нормы агент не вводит.

## План и проверки

1. Новый чистый серверный execution checkout из Git e63, без копирования .env
   или ручной загрузки product code; зависимости подключить как ignored links.
2. Read-only actual published1.2 source и scoped schema сравнить с receipt/baseline;
   статус/refs/checksums/QA неизменны. Рабочая БД не цель теста или cleanup.
3. Machine preflight READY; exact selector и code identity чистого checkout,
   без component fixture/gateway. Один существующий runner invocation, retries0.
4. Generation/tester/challenger/штатный repair, конечная admission PASS либо
   PASS_WITH_WARNINGS при admitted=true; сохраняются binding/время/прочие gates.
5. При допуске: explicit start201, first AS server+DOM, exact candidate/snapshot/
   presented payload,0 оценочных ответов. При отказе: terminal check IDs/statuses/
   safe reasons/candidate/operation/batch refs, фактический шаг и остановка без rerun.
6. До owned cleanup сохранить primary receipts; при недоказанном terminal export
   cleanup-deferred и сохранить БД. После штатного marker destroy — readback/summary.
7. Независимая offline проверка и доступный пакет evidence/diff/SHA, локальный
   EVC commit; branch/main/CI/deploy указать раздельно.

## Границы, стоп-условия и откат

Разрешён только один оплачиваемый сценарий; transport retries/repair внутри него
остаются по существующим правилам. Браузерных или ручных повторов ради PASS нет.
Нельзя менять prompts, admission, repair, M0–M8/CURRENT, опубликованные Cases/QA,
программу/подключения постоянной БД; новых публикаций/push/PR/merge/deploy нет.
Любой drift/readiness/source/ownership mismatch блокирует paid launch. До запуска
все восемь stop categories EVC не открыты в этом scope: смысл/API/схема/потери/
источники/контур/чувствительные данные/восстановление не меняются, явный paid допуск есть.
Это не разрешение произвольной AS/LIMITED или уменьшения полного M2.

Откат: остановить только процесс собственного run; удалить только marker-owned
БД после доказанного export. Не удалять чужие worktrees/deploy assets/env-backup.
При неясном исходе — сохранить evidence/state и остановиться, не повторять generation.
PREP-DIAG-01 остаётся UNKNOWN и не связывается с текущим содержательным исходом.

## Текущие независимые флаги

branch_push=false,pr=false,merge=false,deploy=false,version_bump=false,
artifact_publish=false,paid_path=true(one authorized invocation),
working_db_writes=false,owned_db_create_and_cleanup=true.

Подготовка: [prepared](../evidence/pilot-1.2-path/prepared.json),
сервер `/home/vadim_bogachev/evidence/path-pilot-1.2-run-qxzr56r9`,
execution checkout `/home/vadim_bogachev/worktrees/path-pilot-1.2-48afa8a7874c4ba48141b4621b6c52bd`.
Только ignored dependency links, без .env и post-deploy assets; полный Git status пуст.
Запуск — существующий runner через one-shot operator с exclusive paid-launch.json,
fresh source reconciliation непосредственно перед ним; не новый runtime/API.

Состояние —[STATE](pilot-program-release/STATE.md); точный итоговый commit — в Git/пакете.

## Фактический результат и первичные доказательства

Сценарий выполнен существующими UI/entry/API/owned PostgreSQL без предсозданных
org/admin/участника/назначения/профиля/AS: source-provenance.initial_counts подтверждает
users1, organizations/memberships/assignments/profiles/cycles0. Суперадмин создал
организацию, подключил exact1.2 и назначил администратора; отдельные browser contexts,
контролируемая почта@example.test, администратор подтвердил анкету/добавил участника/
назначил оценку; участник прошёл знакомство и реальную подготовку. Mail sink и
задержка worker — только заявленные harness boundaries, не подстановка результата.

Source chain: e63 runner/seed → published `specialist_pilot@1.2`/id2 → config11
`specialist_pilot_v1` → catalog2 `specialist-pilot@1.0` →9 точных CaseVersions/27 QA
→ functional CASE.SPEC.02 → реальные generation/tester/challenger/repair → final AS.
Source receipt bytes SHA09892e38…; ProgramDefinition b4e8270f…, snapshot daa715b1…,
proposal883c025c… подтверждены. Полные версии/checksums/QA JSON — в первичных файлах;
origin original human_review сохранён, нового human review этот run не подтверждает.

| Факт | Проверенное значение |
| --- | --- |
| Preparation operation / attempts |9d99628f-6e6a-4292-b5b5-4055eb7c6b11 /1 |
| Cycle |b1bf61bf-4b03-43e9-982f-fdae8221c166 |
| Конечная AS |c89539de-2d53-4a70-b887-7a5a217df64a, active |
| Admission |PASS, admitted_for_participant=true, штатный repair использован |
| Конечные стадии |generation_repair + tester5 batches + challenger4 batches; required check IDs и exact batch/operation refs сохранены |
| Перед стартом |can_start=true/reasons[], exact snapshot/proposal/binding, plan LIMITED |
| План/время |полный M2=61, planned39/outside22, uncovered_planned=[], маршрут02→03→04→07→05→01→06→08;7200/259200s |
| Явный start |HTTP201, AS.started_at2026-11-05T18:48:06.934426+00:00; Cycle/Session start тоже сохранены |
| Предъявление |та же AS/candidate/snapshot, owner runtime GET200, introduction совпала с DOM, PNG сохранён |
| Оценочные ответы |0; финальный participant state profiles1/cycles1/started1/operations1 |

Candidate checksum `f1887b7d304d147fbe177c7a48345456a2436f8a5774ac82090e5684abc805bc`;
AS snapshot `2b100e91f4d4eaae491c0b8da29d9cc8d2c9e64a92f45de876e827bd8ce41d49`;
presented participant payload `95dbb61a65f387fafbe6a6a0a91005871b707ca0889b5d257f578abd8d018897`.
Эти разные объекты не приравниваются по hash. Node проверил однотипные ссылки,
candidate→compiled Case→saved AS→presented AS и до/после start. Collector пересчитал
internal bodies при чтении БД; скрытые full candidate/plan bodies не экспортировались
и offline заново не реконструировались. Диагностическая projection имеет свой hash.

Первичные файлы под [server-evidence](../evidence/pilot-1.2-path/server-evidence/outcome.json):
[run](../evidence/pilot-1.2-path/server-evidence/run/6364c771-80c7-4013-bad0-6fd7cc2db545/run.json),
[source-provenance](../evidence/pilot-1.2-path/server-evidence/run/6364c771-80c7-4013-bad0-6fd7cc2db545/source-provenance.json),
[before start](../evidence/pilot-1.2-path/server-evidence/run/6364c771-80c7-4013-bad0-6fd7cc2db545/source-to-runtime-receipt.json),
[first AS readback](../evidence/pilot-1.2-path/server-evidence/run/6364c771-80c7-4013-bad0-6fd7cc2db545/first-case-receipt.json),
[screenshot](../evidence/pilot-1.2-path/server-evidence/run/6364c771-80c7-4013-bad0-6fd7cc2db545/first-case.png),
[runner-result](../evidence/pilot-1.2-path/server-evidence/run/runner-result.normalized.json),
[cleanup](../evidence/pilot-1.2-path/server-evidence/cleanup-readback.json).
Evidence directory UUID6364c771… — не run_id2ff983f1…; связи проверены по содержимому.

## Расход, сохранность и применимость проверок

20 уникальных provider operations,21 completed HTTP request,1 JSON retry внутри
штатного транспорта. Repair reference не удваивает operation count. Retained usage:
prompt1,447,496 + completion76,220 =**1,523,716 tokens**. Usage первого malformed
JSON-ответа продуктовый trace не сохранил: это не полный биллинговый итог/потолок.
Raw server/controller logs не экспортировались. В пакете server.log — явно заявленная
safe projection только duration_ms/routing_key; исходный raw hash, правила и hash
экспорта —[sidecar](../evidence/pilot-1.2-path/server-evidence/server-log-export.json).
Оригинальные JSON/PNG скопированы побайтово,34 primary files; ZIP926711 bytes,
SHA256 `4077a3e2b8f6193aec7f92fc78d7bf344a91b1d6ef55c2745fc46378a94a6f64`.

До cleanup receipt persistence выполнил write/fsync/readback; terminal operation
completed и first-case receipt сохранены до остановки backend и marker destroy.
После: completion/process-result/hash + offline summary PASS; maintenance SELECT
подтвердил exact owned DB/state absent, active connections0, без FORCE. Private state,
ключи и пароли не экспортированы. Рабочая БД только read-only pre/post; source/schema
и число её подключений1.2(0) совпали, published1.1/Cases/QA/правила не менялись.
Clean execution checkout e63 пуст по Git status до и после;11 runtime byte hashes
совпали с immutable Git. Deploy checkout/untracked assets/env-backup не трогали.
Execution checkout сохранён для аудита, это код/ignored links, не оставленная тестовая БД.

`CHECK.py` — PASS_OFFLINE_ACTUAL_PATH: настоящий summary и Node validator на локальных
сохранённых файлах,34 hashes/11 runtime objects, schema/source/cleanup/readiness/refs,
без sockets/DB/новых provider calls. `-O` запрещён. Свежие harness/source/summary/stand
pytest —**110 PASS** (10.11s), Node receipt/persistence —**66 PASS**. Visual review PNG:
видны первая AS/вводная/пустое поле ответа, без auth error; не новая содержательная QA.
Команды/stdout/exit/ограничения —[verification](../evidence/pilot-1.2-path/verification.json).
Backend908/HTTP108/integration220 и CI PR171 переиспользуются только для неизменённого
runtime e63; заново полный набор не запускался. Нового CI нет, новый paid run не нужен.

## Сопоставление исходных AC01…18 без расширения результатов

Ниже текущий положительный маршрут; исторические FAIL не переименованы.
`REUSED` — прежние проверки неизменённого кода/CI PR171, не новая негативная ветвь
в этом оплачиваемом run. Эта таблица не является автоматической приёмкой всех AC.

| AC | Текущий факт / доказательство | Граница / остаток |
| --- | --- | --- |
|01 |PASS: пустая marker-owned DB, minimal counts1/0, source-provenance, cleanup |Не рабочая DB |
|02 |PASS положительный UI create org и последующие reload |Repeat/error create branches не воспроизводились в этом run; REUSED contracts |
|03 |PASS: exact published1.2/config11/catalog2/role2,9 Cases/27 QA/15 source artifact hashes |Не новый human review/CURRENT |
|04 |PASS: UI connection и exact connection1 в owned binding |Не подключение существующей организации test |
|05 |REUSED R10/CI slow/error/null/foreign/lost-reply contracts |Полная отрицательная матрица не повторялась этим positive run |
|06 |PASS admin login в отдельном context, scoped questionnaire/assignment |Foreign/403 negatives REUSED |
|07 |PASS confirmed questionnaire, injected GET503/unknown readiness/retry |ps02-read-error.json/png; подтверждение не отменялось |
|08 |PASS specialist_expert/должность участника; source role exact |UI-перечень всех шести BaseRoles не asserted этим run, не объявлен новым PASS |
|09 |PASS создание точного назначения/refs |Повтор assignment/atomic denial REUSED SQL/HTTP |
|10 |REUSED denial/rollback/source negatives |Positive run не создаёт принудительно отказ назначения |
|11 |PASS owned invitation/participant identity,3 отдельных contexts + fresh re-login |Контролируемая почта, не внешняя доставка |
|12 |PASS acquaintance validation/save/reload/edit/lost prepare reply/two tabs |Синтетические ответы знакомства, не оценочные |
|13 |PASS frozen profile/exact checksums/allowlisted lineage до/после |Raw personal/profile bodies не экспортированы |
|14 |PASS реальные generation/tester/challenger/repair/admission |Один Case, не общая надёжность генерации; PREP-DIAG UNKNOWN |
|15 |PASS operation→assignment/profile/Cycle/plan refs |Tenant/foreign negatives REUSED |
|16 |PASS exact accepted LIMITED binding,61/39/22,оба времени до start |Не любой LIMITED; planned≠observed |
|17 |PASS start201/та же AS/runtime+DOM/0 answers |Start двойной click, один Cycle; дальнейшее оценивание не выполнялось |
|18 |PASS exact clean e63/browser run/screenshots/receipts/cleanup/offline checks |Новый docs/evidence commit не имеет нового CI; человеческая приёмка отдельно |

## Передача, остаток и следующий шаг

Задача исполнения в согласованном positive scope завершена; новых продуктовых
исправлений нет. Ветка `codex/pilot-1.2-path` от1ee2ec4 содержит только этот EVC/evidence
результат и актуализацию описаний; runtime/Api/scripts/assessment_definitions неизменны.
Main/test e63/2.0.66, CI runtime PR171 PASS, deploy42047619768 PASS; нового PR/CI/
merge/deploy/version bump/publication нет. Итоговый SHA/diff/bundle — в пакете.
PREP-DIAG-01 остаётся UNKNOWN. Транзитный readiness blocker при operation=running
не является терминальным дефектом: после completed can_start=true/reasons[].
Успех не устанавливает причину исторического INCOMPLETE или пяти прежних content FAIL.

Следующий минимальный шаг — человеческая приёмка evidence. Новая генерация,
подключение рабочей организации, распространение приёмки на все отрицательные AC,
review/merge/deploy либо дальнейшее оценивание требуют отдельного задания/полномочий.
Статусы относятся только к приведённым доказательствам, без автоматического
закрытия исходных AC или объявления наблюдёнными39 целей. Допуск использован одним run.
