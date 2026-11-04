# PATH-START-2DC — итог одного контролируемого прогона

Отчёт 05.11.2026; допуск и исполнение начаты 04.11.2026. Результат:
**LLM/admission PASS, весь PATH FAIL_PLAN_NOT_READY**. Один реальный запуск,
не новый выпуск. Отказ продукта на explicit start не заявляется: start POST
не выполнялся, runner остановился раньше на собственной проверке `PLAN_NOT_READY`.

## Идентичность и источник

Исполняемый SHA `2dc98c6b5b2637c6c505a90686e82f5e4274e763`, приложение 2.0.64,
clean detached server checkout. Run `96abd1c7e28e4316bcceb069520273e6`, evidence
directory UUID `04e09d64-c7a8-4226-a511-f4a0168b6d53`. Новая БД —
`product4k_pytest_96abd1c7e28e4316bcceb069520273e6`, owner marker проверен штатно.
Main/permanent test после эксперимента остались на том же SHA/версии, tracked
clean, service active, readiness HTTP 200. Service venv/данные не менялись.

Цепочка: existing runner `--program-source published-pilot` →
`specialist_pilot@1.1` (ID1, checksum
`07576484b6c6467fd5fc7047cb1686a2f952532a893660375984373bab87f58c`) →
configuration11 `specialist_pilot_v1` → catalog2 `specialist-pilot@1.0`
`0008d020cbeb8b06ef5d38ad1eaf136fab8dc42728d98c2d5ec275476a6c25a0` →
исходные 9 FROZEN CaseVersions/27 QA → функциональная подготовка CASE.SPEC.02 v0.6.
Оригинальные QA origins/checksums и решение владельца 30.10.2026 переиспользованы;
synthetic human_review substitution не применялась. Это не новый human review,
методологический допуск или публикация программы/CURRENT.

Полные primary refs/checksums: `../evidence/path-start-2dc98c6-run/run/`
`source-provenance.json` и `source-to-runtime-receipt.json`. Исторические указания
старых handoff на main7221671 или только PATH-ветку не применяются к новому запуску.

## Фактическая цепочка и граница успеха

| Этап | Проверено этим запуском | Итог |
| --- | --- | --- |
| PS-01 | Один исходный superadmin; создание новой org, подключение exact program, добавление admin; отдельные сессии и test mail sink | PASS проверенный маршрут |
| PS-02 | Администратор подтверждает анкету; реальный UI GET503 после confirmation не отменяет её; retry возвращает готовность назначения | PASS, `ps02-read-error.json/png` |
| PS-03 | Новый участник с должностью, exact assignment/binding/role/questionnaire revision, собственное приглашение/вход | PASS проверенный маршрут |
| PS-04 профиль | Assignment1 → binding1 → questionnaire1 → frozen profile1 → preparation requested_profile1 → Cycle assignment1/profile1; checksums и оба времени связаны | PASS evidence links; не расширение покрытия |
| PS-04 LLM | Generation + tester5 + challenger4, конечный admission PASS/admitted=true, compiled Case и AS сохранены | PASS именно этого кандидата |
| PS-04 план | План сохранён как LIMITED; UI показывает «Можно приступать», 8 ситуаций и 60 минут; validator требует READY | FAIL_PLAN_NOT_READY / зарегистрировано ниже |
| PS-05 | Explicit start, HTTP201, фактическое предъявление AS, post-start readback | NOT_RUN; не объявлять PASS |

Начальные counts: users1; organizations/memberships/profiles/cycles/assignments0.
Однократный bootstrap не содержит готовых назначений/профилей/AS. В конце оценочных
ответов0; Cycle/Session/AS started_at=null. Три ознакомительных ответа не являются
оценочными Turns.

Preparation operation `1d994d19-9ada-4dcb-92b9-4f4e41a096e0`, status completed,
attempts1; error_code/error_message=null. Candidate checksum
`3e463f784a5b3b56049395dc862172e8cc14a747ef5b625a59df7fa3b1b4db8b`;
compiled Case `48643770a33f442f9b5ff82f767a64156b38a95e60ad75358ea225cacdf72e27`;
input snapshot `66c9e96a40263f0a06b6d7b8640c3954b5c86d9e3cc475d71b15479e1fdc2b02`.
Saved AS `9aedb9b7-6354-4280-9ee9-18a2dfa2a0e5`, admitted;
snapshot `4751289c13ff2501d08910201ea69d48e6fe883d10d2c700f5b86ad547e104e3`.
Связь candidate → compiled Case → saved AS и snapshot/execution refs подтверждена
отдельной offline проверкой без подмены статуса плана; предъявленной AS пока нет.

Cycle `00ac04eb-b6bc-4d05-9139-b3ae5f46e232`; Session
`d99bc674-a892-4c02-922d-49e9e3f8afee`; оба prepared. Plan
`0655fa35-c970-40a9-aad7-2e40c9b74fd2`, revision
`49282e8c-5c53-4884-9c04-bc445484048f` / 1, checksum
`39feedea984a6a10ea498d86012c7f09126caa36100cffa00defec80ca4716b5`.
Effective time 3600 sec / calendar259200 sec, одинаковые в assigned timing и Cycle,
источник method_default m7_cycle_plan@1.0.0 с checksum
`9e4f5a3c0b6838407bbb16174f7f37b10f1022242b3d1088c51df31f014bd0ef`.
Увеличение времени не исправляет покрытие автоматически.

## Реальный LLM и существенные ограничения

DeepSeek `deepseek-flash`: 10 уникальных provider operations / 10 HTTP completions,
все transport attempts1 completed, JSON parse failures0. Generation1, tester5,
challenger4; prompt710759 + completion36791 = **747550 tokens**.
Blocking/incomplete/protocol arrays пусты. Это реальные вызовы именно этой
preparation operation, не provider probe или подставной gateway.

Repair не использовался. Поэтому реальное исполнение исправленного repair и
причинная связь PR #169 с успехом не доказаны. Старые пять content FAIL не
воспроизвелись у нового кандидата, но это не доказательство стабильного качества
всех Cases. Исторический PREP-DIAG-01 остаётся UNKNOWN, без нового объяснения.

## PATH-PLAN-01 — текущая точка остановки, не готовое решение

Статус OPEN_CONTRACT_RECONCILIATION. Факт: `failure.json` step
`real_llm_preparation`, actual `PLAN_NOT_READY: LIMITED !== READY`, process exit1,
completion failed и итог runner FAIL. Ложного PASS нет. Assertion находится в
`tests/browser/fixtures/preparation-receipt.mjs:36`; он выполнен **до start**.

Код `Api/m7_cycle_planner.py` задаёт READY при пустом uncovered, LIMITED при
непустом uncovered и наличии маршрута, NO_ROUTE при отсутствии маршрута. Бюджет
сам по себе не определяет этот статус. Текущий onboarding отправляет K1–K4;
offline source audit показывает полный M2 target set61 и union target IDs девяти
точных Cases39: как минимум22 Indicators отсутствуют даже при допуске всех Cases.
Хеши всех девяти исходных JSON с двумя техническими FROZEN status совпали с release
receipt. Это объясняет ограничение покрытия, но **не является восстановлением**
удалённого frozen plan. Полные route/catalog reasons/uncovered_target_ids в этом
terminal export отсутствуют; их точное содержимое остаётся UNKNOWN.

`Api/m10_product_flow.py:start_prepared` и `Api/m7_cycle_planner.py:present`
не содержат отдельного запрета по строке LIMITED; действуют проверки owner,
assignment/profile, prepared AS/admission/revision/time. Нельзя сообщать, что
продукт отказал на start: запрос не сделан. Нельзя автоматически назвать
требование READY ошибкой теста и ослабить его: нужно сверить смысл допустимого
плана конкретной пилотной программы, контракт API/UI и test expectation.

M7 v1.3 §§2.2/4.1/4.3/5.1 различает целевой состав, плановое покрытие, известные
ограничения и допустимый начальный маршрут; сокращение обязательного состава
требует предварительного обоснования. Здесь targets/M2/Case/admission/плановые
статусы не менялись и READY не подставлялся. Нового нормативного решения нет.

Следующая отдельная **бесплатная** задача: согласовать/проверить контракт READY /
LIMITED / NO_ROUTE между PM-04, API/UI и validator, расширить safe export причин/
полного frozen plan и дать регрессии без LLM. Если исправление требует смены цели,
состава или допуска — это отдельное решение владельца, не технический fallback.
Второй paid PATH не разрешён текущим допуском и не выполнялся.

## Evidence, cleanup, проверки и состояния

14 первичных файлов переданы явным allowlist; state/.env/passwords/tokens, сырые
provider prompts/responses и server/stdout logs не передавались. Все terminal
receipts mode0600. Source-to-runtime и failure-receipt имеют одинаковый SHA-256
`a6ebace530e69d3f0efb33b0f95e89b0c743d8ae30d8baa471705e8109004d05`.
Server mtime/hash audit подтверждает оба terminal файла **до** cleanup receipt;
persistReceipt использует fsync и byte-for-byte readback. Cleanup owner_verified,
database_absent/state_absent=true, force=false. Данные удалённой owned-БД уже
недоступны; из недостающих сведений не делаются утверждения. Постоянная БД не цель.

`node docs/evc/evidence/path-start-2dc98c6-run/VERIFY.mjs` — PASS_OFFLINE_EVIDENCE_AUDIT,
exit0: исполненный code identity/file hashes, negative runner/completion/exit,
ожидаемая ошибка неизменённого validator, admission/stages/candidate→saved AS,
нулевой start/ответы, source/QA27/checksums9, порядок export/cleanup и static
coverage22. Это **не** PATH PASS и не независимая содержательная оценка AS.
`git diff --check` PASS. Продуктовых/методологических изменений нет; новый backend/
CI/release N/A, источник main2dc98c6 уже прошёл выпускной CI отдельно.

Раздельные статусы: отчётная ветка local-only (plan commit96a0635 + итог/evidence);
новый CI NOT_RUN, PR нет; main2dc98c6 / 2.0.64 не изменён; permanent test тот же
SHA/version, active/ready200. Нового deploy/version bump/publication нет.
Восстановление БД не расследуется, защита permanent DB сохранена. Откат кода N/A;
единственная owned-БД удалена штатно после доказательств, её содержимое не
сохранялось для восстановления. Подтверждённые прежние ZIP/история неизменны.
