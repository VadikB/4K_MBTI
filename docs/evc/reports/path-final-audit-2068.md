# PATH-START-01 — итоговая сверка 18 AC на выпуске 2.0.68

## Итог

**Полная приёмка PATH пока не подтверждена.** В выбранном проверенном наборе:
13 AC имеют достаточное накопленное доказательство в указанной области;
5 составных AC — NOT_RUN из-за конкретных недоказанных подпунктов. Это не пять
новых продуктовых дефектов и не утверждение об отсутствии тестов во всём проекте.
Впервые отдельно воспроизведён AUTH-DIAG-01: lazy cleanup после401 стирает ошибку.
Историческая причина PREP-DIAG-01 по-прежнему UNKNOWN, необходимые детали утрачены.

Задача аудита и доступные две диагностики выполнены; ни человеческая приёмка
всего PATH, ни новый full real-provider run, ни исправление продукта здесь не выполнены.
[Точная машинная матрица](../evidence/path-final-audit/audit-matrix.json).

## Основания и применимость

- [PATH1.3, точные полученные байты](../evidence/path-final-audit/path-start-1.3.txt),
 04.11.2026, §§5–6/9–10; SHA256 — source-identities.json. Текст задания задаёт
 критерии, не новое разрешение на платные операции вместо поздних ограничений.
- Продукт/main/test: `946a46cb71e5ca5cc99778f036807d6c193188dc` /2.0.68,
 tree48d193a72cca655c5580adcdaade9f6936f6265d, равен принятому head63a24cf.
 [Закрытие PR173](https://github.com/VadikB/4K_MBTI/pull/173#issuecomment-6671510137),
 [release](../evidence/path-final-audit/release2068.json),
 [readback](../evidence/path-final-audit/release2068-server-readback.json).
- Реальный целый PATH: e63eba67d77fb73f7fb9bb219bc3fe5d3807a909 /2.0.66,
 run2ff983f12c67494b990b0f85284b8d70, отдельная marker-owned PostgreSQL,
 настоящие UI/entry/API/provider. Mail sink и synthetic acquaintance inputs
 объявлены; org/admin/member/assignment/profile/AS не предсозданы.
- Профиль assessment-first-case/1.1 и runner не настраивались заново.11 recorded
 runner/runtime-input files побайтово совпали с текущими; Api/scripts/definitions
 не изменились между e63 и946. Это применимость технических доказательств,
 **не** равенство всей UI сборки и не замена whole run на окончательном SHA.
 [Идентичность](../evidence/path-final-audit/source-identities.json).
- Полный M2=61; принятый конкретный LIMITED-план39/22,55 observation conditions,
 маршрут02→03→04→07→05→01→06→08.39 planned не становятся observed;
 опубликованные9 Cases/27 прежних QA не получили нового human review/CURRENT.

## Проверки и уровни

P — [реальный PATH,34 primary files](../evidence/pilot-1.2-path/server-evidence/outcome.json),
 [до start](../evidence/pilot-1.2-path/server-evidence/run/6364c771-80c7-4013-bad0-6fd7cc2db545/source-to-runtime-receipt.json),
 [AS/start](../evidence/pilot-1.2-path/server-evidence/run/6364c771-80c7-4013-bad0-6fd7cc2db545/first-case-receipt.json),
 [provenance](../evidence/pilot-1.2-path/server-evidence/run/6364c771-80c7-4013-bad0-6fd7cc2db545/source-provenance.json),
 [cleanup](../evidence/pilot-1.2-path/server-evidence/cleanup-readback.json).
 Независимый существующий CHECK.py повторён offline: PASS,34 hashes/11 runtime
 objects, настоящий receipt validator/summary, sockets/DB/new provider0.
 [Новый вывод](../evidence/path-final-audit/offline-path-check.json).

B — [AC02/05 before/after](../evidence/path-ac02-ac05/README.md): clean before3/2,
 after17 PASS, реальные HTML/entry/dist, HTTP synthetic. AC02 SQL2 — настоящие
 route/DDL/UNIQUE/commit/rollback; auth/list projection synthetic. Последний
 [candidate68 browser115 PASS](../evidence/path-ac02-ac05-release-2068/browser.json),
 retries0. Изначальный full114/1 сохранён, не переименован в PASS.

H — HTTP25/role5, PostgreSQL lineage3/подтверждение/ownership и unit contracts:
 точные tests указаны ниже, backend/схема неизменны. CI PR173 —
 [unit908/HTTP108](https://github.com/VadikB/4K_MBTI/actions/runs/42120322342),
 [integration/5 browser lanes/full gate](https://github.com/VadikB/4K_MBTI/actions/runs/42120322358).
 Не выдавать job PASS за независимую запись каждого отсутствующего negative case.

R — [deploy-test PASS22s](https://github.com/VadikB/4K_MBTI/actions/runs/42123348506/job/127581116570),
 server HEAD/service/version/HTML+45 assets disk/loopback/public PASS. Это не новый
 целый synthetic process после deploy.1277 retained untracked assets штатно
 сохранены; tracked source clean, полный clean server worktree не заявляется.

## Одна матрица AC01–18

PASS означает проверенные подпункты критерия в явно названном накопленном
scope/SHA, не новый whole run946. REUSED — проверка неизменённого основания.
NOT_RUN означает недостающую доказанность хотя бы одного обязательного подпункта,
не автоматически дефект. Владельцы технических пробелов — архитектор; решение
о дополнительном платном run/принятии результата — владелец продукта.

| AC / PS и требование1.3 | Реализация / SHA и выполненная проверка | Первичное evidence / подмены | Статус, точный остаток / владелец |
| --- | --- | --- | --- |
| AC01 / PS01: minimal bootstrap, ownership | e63 actual P counts users1/остальные0; current runner11 hashes равны; marker cleanup | P provenance/run/cleanup, offline CHECK; только owned DB, не рабочая | PASS; новый whole946 не запускался — AC18 |
| AC02 / PS01: create/reload/repeat без дубля | P positive + B3 stateful browser +2 real HTTP/PG UNIQUE/rollback на неизменённом backend; UI946 regression | clean-before/after-selection, ac02-integration.txt; SQL auth/list projection synthetic | PASS в этих уровнях; не второй full PATH |
| AC03 / PS01: exact published9 Cases/допуск/immutable | published specialist_pilot1.2/id2/config11/catalog2/role2; receipt09892e38…; P/CHECK refs и9 Cases/27 QA | published-release-source внутри P, исходные QA scope/origin; не diagnostic seed | PASS; нового human source review/CURRENT нет и не заявлено |
| AC04 / PS01: connection GET/reload, пустая анкета не блокирует | P connection1 и scoped GET; B R10 lost PUT/reopen/pending questionnaire на946 | source-to-runtime receipt; auth-r03.spec R10 actual entry/synthetic HTTP | PASS; рабочую организацию не подключали |
| AC05 / PS01: finite/unknown/retry/foreign |12 fault combinations +2 foreign-org,17 targeted/115 full; exact org+program/same operation_id/15s | B raw JSON/PNG, candidate68; только transport responses synthetic | PASS; не настоящие outages постоянного сервера |
| AC06 / PS02: own admin + запрет direct connect/foreign scope | P admin separate context PASS; related membership/role HTTP REUSED | P identity/context; tests/e2e/test_arch30_membership_http.py и test_m3_role_profile_selection_http.py — смежные guards | NOT_RUN: exact ordinary-admin program-connect HTTP и чужая org mutation в выбранном primary наборе независимо не подтверждены; архитектор |
| AC07 / PS02: confirmed exact revision, stale/foreign, error GET | P confirmed/retry503; B unknown/error/readback; PG questionnaire confirm idempotency REUSED | P receipt; B JSON; tests/integration/test_questionnaire_sources_db.py | NOT_RUN: stale/foreign revision именно confirmation route не подтверждены отдельным primary результатом; архитектор |
| AC08 / PS03: participant fields,6 BaseRoles, specialist_expert | P должность/роль; позже все6 options из M3 fixture asserted; недоступные5 не назначаются | B/browser и tests/unit/test_m3_base_roles.py; role fixture технический | PASS; не новый допуск5 ролей и не нормативное расширение |
| AC09 / PS03: one atomic assignment/repeat/lost reply | P exact assignment/binding PASS; H idempotent/conflicting operation/non-member без fake rows | tests/e2e/test_adm27_assignment_http.py использует fake Connection и fake binding | NOT_RUN: whole double-click/lost reply/reload + действительная PG atomicity/0 лишних Cycle не следуют из mock; архитектор |
| AC10 / PS03: exact denials, no partial SQL | H program/role/questionnaire error codes проверены, P positive binding | Та же HTTP fixture подменяет resolver/readiness/connection; это не SQL negative matrix | NOT_RUN: полный SQL no-partial набор deny source/scope/questionnaire здесь не подтверждён; архитектор |
| AC11 / PS04: own session/identity, чужие IDs не открываются | P participant/fresh login; profile ownership HTTP+owned SQL и AS foreign-session REUSED | tests/integration/test_profile_access_owned_stand.py и test_m5_cycle_runtime_db.py; auth contexts synthetic controlled users | PASS для ownership/fail-closed; новый AUTH-DIAG-01 — отдельный UX failure, не доказательство unauthorized access |
| AC12 / PS04: acquaintance persistence/точные причины | P save/confirm/refresh/relogin/edit/lost prepare/two tabs; readiness HTTP и W02 DB REUSED | P screenshots/receipts; tests/e2e/test_path_start_readiness_http.py; no assessment answers | PASS; текущий whole946 не утверждается |
| AC13 / PS04: frozen profile before generation/no PII | P exact profile/source/checksum; M4 identity-excluding unit и неизменённая profile→generation граница | tests/unit/test_m4_personalized_profile.py; raw full prompts/profile bodies намеренно не экспортировались | PASS на совокупности contract/source/receipt, не независимое чтение сырых prompts |
| AC14 / PS04: auto-prep/LLM/final admission/read-only UI/PREP | P20 operations, repair + tester5/challenger4, final AS admittedPASS; ST-R4 renderer B; PREP адресно пересмотрен | P provider refs/candidate→saved→presented; PREP card и текущая unit-регрессия11 PASS | PASS для фактического e63 route и адресного рассмотрения PREP; historical root UNKNOWN, не надёжность всех генераций |
| AC15 / PS04: exact assignment/profile/revision/job SQL |3 actual SQL lineage tests: same config/different revision, foreign later job, unknown legacy; CI existing integration REUSED | tests/integration/test_path_start_assignment_lineage_db.py: извлечённый actual projection SQL, synthetic schema/rows | PASS этого SQL-контракта; fixtures не выданы за whole E2E |
| AC16 / PS05: no early start, actual gate/two times | P before-start can_start=true/reasons[], exact admitted LIMITED binding61/39/22;7200/259200 | before/start receipts и plan checksums; оба времени от accepted source | PASS; любой LIMITED не разрешён автоматически, planned≠observed |
| AC17 / PS05: explicit start, same AS,0 answers/idempotency | P HTTP201, Cycle/Session times, та жеAS c89539de…, DOM introduction, repeated click/reload; current runner unchanged | P first-case-receipt/PNG и actual validator offline PASS | PASS реального e63 run, не новый whole946; дальнейшие ответы/оценивание вне scope |
| AC18 / PS01–05: whole final SHA/post-deploy/independent/viewport | R release946 PASS; B4 widths1440/320/390/768 и exact current assets; независимый P replay | release/readback/CI и current audit; real provider P=e63/2.0.66, не946/2.0.68 | NOT_RUN: whole process на final SHA/после deploy отсутствует; плюс AUTH-DIAG-01 needs fix/review; архитектор + владелец продукта |

## Восстановимая трасса и повторение

В P: org1 → connection1(program2@1.2/config11/catalog2) → admin2 →
questionnaire revision1/context1 confirmed → participant3/role version2 →
assignment1/ref specialist-pilot/binding1 → acquaintance confirmation1 →
profile1/checksum084a8ffc… frozen2026-11-05T18:42:21.053775 →
preparation9d99628f-6e6a-4292-b5b5-4055eb7c6b11 →
Cycle b1bf61bf-4b03-43e9-982f-fdae8221c166 →
Session3543f43f-e7f1-42ce-bc4f-f71275e57c46 →
AS c89539de-2d53-4a70-b887-7a5a217df64a/start2026-11-05T18:48:06.934426+00:00.
Это ссылки разных объектов, не требование равенства всех checksum.
После start readiness «уже не prepared» не отменяет сохранённый before gate.

Существующая команда профиля с точным selector1.2, ранее проверенным в P:
ниже рецепт для будущего разрешённого run, **здесь не запускалась**. Новый evidence
каталог обязателен, доверенные доступы используются на машине без вывода секретов.

```sh
PYTHONPATH=. .venv/bin/python scripts/assessment_first_case.py \
  --env-file /home/vadim_bogachev/projects/Agent4K-Test/.env \
  --python /home/vadim_bogachev/projects/Agent4K-Test/.venv/bin/python \
  --directory /home/vadim_bogachev/evidence/NEW_OWNED_RUN_DIRECTORY \
  --program-source published-pilot --db-admin-port 55432 \
  --program-receipt /home/vadim_bogachev/evidence/pilot-program-1.2-wryr3q10/published-release-source.json \
  --program-receipt-sha256 09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b \
  --program-version 1.2
```

## Итоги двух диагностик

[PREP-DIAG-01](../tasks/prep-diag-01-review.md): aggregateINCOMPLETE, no AS/start,
0 answers доказаны; конкретные checks/reasons утрачены. Root UNKNOWN,
историческое расследование BLOCKED_BY_MISSING_PRIMARY_CHECK_DETAILS. Экспортёр
ныне сохраняет детали;11 fresh unit PASS. Это не новый продуктовый PREP defect.

[AUTH-DIAG-01](../tasks/path-auth-diagnostic.md): opt-in controlled transport
test **1 FAIL**, exit1/retries0. До загрузки chat — error есть; после resetChat —
пусто. Продукт не менялся. Новая причинная цепочка доказана; её связь со старым
единичным114/1 **NOT_ESTABLISHED**, старый root UNKNOWN сохраняется.

## Передача и минимальные следующие действия

1. Исправить установленную auth cleanup/error race отдельным техническим шагом,
   сохранив epoch/fail-closed; delayed/fast/concurrent401/late-session regressions.
2. Закрыть точные proof gaps AC06/07/09/10 адресными HTTP/owned PG/browser проверками
   либо предъявить уже существующие первичные результаты. Нехватку доказательства
   не выдавать за новый дефект или требование новой методологии.
3. После готовности к приёмке решить с владельцем объём final/post-deploy whole
   run. Новый платный запуск пока не разрешён и не выполнялся; проверка AC18
   остаётся NOT_RUN. Отдельное решение не может ретроактивно изменить SHA старого P.

Main/test946/2.0.68 и их CI/deploy PASS переиспользованы из закрытого выпуска.
Локальная новая ветка — только аудит/opt-in negative test, новый CI NOT_RUN;
push/PR/version/merge/deploy/публикация/активация/paid LLM/рабочая БД false.
Это отчёт агента, не human acceptance и не baseline. Политики/допуск/repair/M0–M8
не менялись. Откат — revert новой docs/test delta, без данных/опубликованных версий.
