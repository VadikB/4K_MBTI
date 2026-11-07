# PATH-START-01 — от новой организации до первого Case

## Текущий сквозной результат05.11.2026

Один отдельно разрешённый PATH ограниченного пилота1.2 — **PASS** на main/test
e63eba67d77fb73f7fb9bb219bc3fe5d3807a909 /2.0.66. Run2ff983f12c67494b990b0f85284b8d70,
admission конечной AS PASS после штатного repair; explicit start201, server readback,
та же AS в DOM/screenshot,0 оценочных ответов. Exact plan LIMITED допущен по принятому
P/M snapshot1.2; полный M2=61 сохранён. Owned cleanup и независимый offline CHECK PASS.
[Текущий отчёт и scope AC01…18](pilot-1.2-path.md). Публикация1.2/выпуск runtime были
отдельными ранее разрешёнными шагами; этот run не менял рабочую БД/методологию/правила.

Ниже — исторические run/исправления/матрица на7221671/a8d8fcf. Их PM03 FAIL/BLOCKED
не переименовываются в PASS; положительный исход1.2 подтверждён новым evidence.
Один положительный маршрут не закрывает автоматически все расширенные негативные
ветви AC и UI-проверку шести BaseRoles; точная применимость указана в текущем отчёте.
PREP-DIAG-01 остаётся отдельным историческим UNKNOWN, причинный вывод не сделан.

## Выпуск независимых исправлений — 04.11.2026

Владелец ответом «да» в текущем чате явно согласовал последовательный выпуск:
2.0.63 для PR #168, затем 2.0.64 для PM03-REPAIR-CONTRACT / PR #169 после
переноса на фактический main. Это приёмка и выпуск независимых исправлений,
не признание полного PATH успешным и не допуск нового LLM-прогона.
Текущие флаги: `branch_push=true`, `pr=true`, `merge=true`, `deploy=true`
(только test), `version_bump=true` (PATCH 2.0.63), `artifact_publish=false`.
Прежние false/NOT_RUN ниже сохраняют историю передачи до этого решения.

База перед выпуском: свежий main `7221671fbd9b16192a86b04b6eec36773f2dbf99`,
2.0.62; clean PATH head `11b2a94e164b97b95a0ef8f9a806ab2becf2b1a9`.
Read-only test: тот же SHA/версия, tracked clean, service active, readiness HTTP 200.
Шаги: canonical `npm run ready:prepare -- --candidate 2.0.63`; commit/push;
Ready; обязательные frontend/pytest/full-verification точного head; squash merge
без bypass; штатный deploy-test и серверный/public readback. До их выполнения
CI/main/deploy отдельно не объявляются успешными. При изменении базы — новый
preflight и актуальные проверки. Pilot, схемы, предметные артефакты и постоянная
БД не изменяются; автотесты — только CI/owned isolated test DB.

При первой release-подготовке поведение Api/web на 136b858/11b2a94
переиспользовалось побайтово; менялись только номер, производный dist, разрешение
и STATE. Найденная в CI регрессия и её адресное исправление описаны ниже.
Дополнительно выполняются diff/links, lint, frontend и release gate;
полный CI повторяется на конечном head. Исторический пакет 11b2a94 не переписывается.
Откат: штатный deploy-script восстанавливает предыдущий commit/assets/config при
неуспешном smoke; после успешного выпуска — отдельный revert PR, не rollback БД.
Нормы, admission/repair и защита cleanup сохраняются; PREP-DIAG-01 UNKNOWN.

Локальная подготовка 2.0.63: canonical preflight PASS (exit 0), `npm run lint:js`
PASS, `node --test tests/frontend/*.test.mjs` — 139 PASS / 0 FAIL. Версии
pyproject/uv.lock/frontend/index согласованы, dist пересобран штатно. Api/tests/
исходный UI-код после принятого 11b2a94 не менялись; backend757/HTTP108/PG209
и адресные collector4 применимы в ранее указанной области, не заменяют новый CI.

### Регрессия ST-R1, найденная обязательным CI

На release head `32c0b28e6687c70de2aa6be248b8dedb25fbf3c5`:
[Full verification 41902176961](https://github.com/VadikB/4K_MBTI/actions/runs/41902176961)
FAIL; integration PASS, четыре runtime browser полосы PASS, fast browser 95 PASS /
4 FAIL. Все четыре — существующие PROGRAM01 R06 проверки локального статуса
отмены после 409, потери ответа, 403/500. Это собственная регрессия ST-R1:
исключение dialog actions из capture tracker убрало не только ранний loading,
но и `operationAnchor`; сообщения отображались глобально, а не рядом с действием.
Не является причиной PM-03 content FAIL или PREP-DIAG-01.

Новая проверка dialog → подтверждённая команда с задержанным synthetic 500 и
усиление отказа проверяют отсутствие раннего busy, локальные loading/terminal,
ровно один POST и восстановление кнопки. До исправления на dist 32c0b28 команда
`npx playwright test tests/browser/auth-r03.spec.mjs --grep 'PATH-START ST-R1|PROGRAM01 R06'`
дала 5 FAIL / 4 PASS, exit 1. Fixtures/HTTP полностью синтетические; БД и LLM нет.

Адресное исправление: для cancel/revoke/delete capture сохраняет anchor без
loading; loading начинается только в подтверждённом command handler. Карточка/
открытие отчёта остаются local-only. Существующие cancellation idempotency,
readback, identity guards и серверные права не меняются. Версия остаётся 2.0.63,
повторный preflight идемпотентен (PASS, без нового bump). Весь auth/admin browser
набор проверен заново: `npx playwright test tests/browser/auth-r03.spec.mjs` —
98 PASS / 0 FAIL, exit 0, 1.4 min. Lint и frontend139 PASS, diff PASS. Backend и
DB source после 32c0b28 неизменны; их предыдущие проверки применимы, новый полный
CI всё равно обязателен. Safe summary и точные file SHA:
`docs/evc/evidence/path-start-01/release-2.0.63/st-r1-regression.json`.

## Результат, основание и область

Статус: BLOCKED_PM03; независимые исправления передаются отдельно от полного PATH.
Решение владельца 04.11.2026: «Передать исправления PATH с точным блокером;
доработку генерации согласовать отдельным заданием». Новые LLM-прогоны, изменение
prompts/admission/repair и выпуск кода в этот шаг не входят.
Исполнение начато прямой командой владельца «делаем» с
приложенным заданием редакции 1.3 от 04.11.2026. Файл задаёт требования, а не
самостоятельные полномочия: исторические разрешения/результаты сверяются с Git,
доступными решениями и фактической средой перед зависимым действием.

Вход: `P4K_PATH_START_01_Assignment_to_First_Case_2026-11-04.txt`, SHA-256
`29ada88402576a5cb36a89df12039f1a45bcfc58c41385a733ffef3c7b933749`.
Область: PS-01…05 и AC01…18 — настоящие UI/entry/API/PostgreSQL, новая owned-БД,
точная утверждённая программа, реальные LLM generation/tester/challenger, штатный
admission и первый явный start/предъявление AS при 0 оценочных ответов.
Не входят дальнейшее решение/оценивание/Results, общие purge/transfer/cancel races,
новые методологические нормы, DB-PERSIST-01 и новый выпуск кода без отдельного допуска.

## База и источники

- Новая ветка `codex/path-start-01`, base/fetched main
  `7221671fbd9b16192a86b04b6eec36773f2dbf99`, приложение 2.0.62, PR #167 merged.
  Root checkout имеет три посторонних untracked документа; они не меняются.
- Профиль `assessment-first-case/1.1` и `scripts/assessment_first_case.py` уже в main.
  Принятый 2f0a5a0/ZIP, 49 Python/27 Node, ложный PASS и PASS_WITH_WARNINGS не
  реализуются заново. Однокейсовая synthetic QA fixture не становится источником PATH.
- Переиспользованы неизменённые README/CONTRIBUTING/AGENTS, EVC workflow/matrix/
  artifact recipe/review; прочитаны task-template, ADR-002 C-23/24/34, ADR-003,
  context/Registry/Change01/SourceSet и существующий профиль/runner/seed.
- M1 v1.4 FROZEN/CURRENT=NO, M3/M4 v1.0, M5 v1.1; M7 v1.3 §§2.4/5.1 и начало
  §5.3 прочитаны в `docs/methodology/source-sets/2026-10-01/derived/M7-v1.3.md`.
  План/профиль/два эффективных времени фиксируются до первого старта; календарное
  окно начинается первой Session. M6/M8 — только границы, не новая реализация.
- Прочитаны ARCH30-ADD01 (решение состава от 30.10.2026), PROGRAM01/R03,
  `scripts/plan_specialist_program_release.py`, текущие PATH29 inputs и места
  questionnaire load/readiness/operations/actions/assignment lineage.
- PM-02: роли/контекст/PersonalizedProfile; PM-03: источник/генерация/допуск AS;
  PM-04: план/маршрут/время/start. Фактические LU и изменённые потребители уточняются
  по найденному разрыву, а не назначаются будущей модели заранее.

## Первая разведка и зависимости

В root обнаружены отдельные пользовательские документы публикации
`docs/evc/tasks/program01-test-recovery-2026-11-04.md` и safe receipt рядом в
`docs/evc/evidence/`. Они сообщают о выполненной публикации, а не NOT_RUN:
`specialist_pilot@1.1`, program DB ID 1,
checksum `07576484b6c6467fd5fc7047cb1686a2f952532a893660375984373bab87f58c`;
configuration `specialist_pilot_v1` ID 11; catalog `specialist-pilot@1.0` ID 2,
checksum `0008d020cbeb8b06ef5d38ad1eaf136fab8dc42728d98c2d5ec275476a6c25a0`;
`specialist_expert@1` ID 2, checksum
`c5c2234f9fdd237e14024ea6939e3bc5561fd27bf4fac416a52196dec79cbe8f`.
Это пока входное свидетельство отдельной операции, не новый PATH readback.
Повторная публикация запрещена до сверки существующего результата; неизвестные
текущие IDs/target/QA не угадываются. UI readback постоянного test пока не доказан.

Исторический PREP-DIAG-01 сохраняется UNKNOWN. Новый run не реконструирует его
checks. Сначала сохраняется исходный разрыв целевого пути, затем исправления и
отдельный полный повтор на конечном SHA. Published определения не переписываются.

## План и состояние

1. DONE: read-only сверка test/публикации/QA/release refs и DB target/ownership;
   обновление handoff/STATE. Конкурирующая программа не создавалась.
2. DONE: адаптация существующего runner/seed/assertions к exact nine-case release;
   минимальный bootstrap, безопасные terminal export/completion/cleanup. Без готовых
   org/admin/member/questionnaire/assignment/profile/AS/start в начальной загрузке.
3. DONE до admission FAIL: исходная диагностика PS-01…05 и отрицательные UI/HTTP/DB проверки; сохранён первый
   разрыв до исправления соответствующего продукта; независимые части не блокировать.
4. DONE для доказанных PG-R1/R2, ST-R1/R3/R4: адресные исправления и регрессии. PG-R3 — сквозной остаток. Исправления только при
   подтверждённом текущем поведении; регрессии; не переделывать R01/R02/R03/R10.
5. BLOCKED: полный итоговый run/start на новых owned-данных. Решение владельца:
   передать независимые исправления с точным PM-03 blocker, генерацию согласовать
   отдельным заданием. Активно только оформление передачи/draft PR после локального
   минимума. Deployed acceptance отдельно.

## Флаги, стоп-условия, безопасность и откат

`branch_push=true` после локальных проверок, `pr=true` для одного результата;
`merge=false`, `deploy=false`, `version_bump=false`, `artifact_publish=false`
для PATH. Прежняя публикация целевой программы — отдельное основание; её готовый
результат переиспользуется, не производится новая нормативная публикация.

Восемь стоп-условий EVC: (1) новый смысл — нет; (2) несовместимый API/схема —
пока нет, при необходимости анализ/решение до реализации; (3) миграция/чужое
удаление — нет; (4) источник — зависит от точного readback, запрещает только
зависимый seed/run при mismatch; (5) новый контур — нет; (6) новые права/передача
PII — нет, запрещены; (7) отсутствие отката — нет; (8) выход за область — нет.
Новый методологический конфликт не решается prompt/fallback/смягчением admission.

Не читать/выгружать секреты и пользовательскую историю. Только служебный release
metadata readback постоянной БД; все автотесты/прогоны — owned test/pytest DB.
Перед записью проверяются фактические target/marker; cleanup только своей БД,
без FORCE и после terminal fsync/readback. Running/ошибка export сохраняют DB/state.
Откат: адресный revert кода без потери bindings/snapshots; disposable cleanup отдельно.

## Проверки

Применимый минимум: backend/unit + HTTP; настоящая isolated PostgreSQL для
атомарности/повторов/assignment lineage; frontend regressions/lint/build/dist при
изменении frontend; browser 1440/320/390/768 и ровно обоснованные real-provider runs.
Обязательный CI относится к новому окончательному head. Платный прогон не повторяется
на каждой ширине или ради случайного PASS. Нормы retry/repair не расширяются.

## Единая матрица AC01…18

Статусы не заимствуются из SYN/PR #167. Код передачи — `136b858` и последующие
документальные/evidence-коммиты этой ветки; `a8d8fcf` — единственный real LLM run,
`2c813f2` — full integration. Область каждой проверки указана отдельно.
Сокращения evidence: `E` = `docs/evc/evidence/path-start-01/`; `P` =
`E/preparation-a8d8fcf/`; `V` = `E/verification/`. Это пути внутри доступного пакета.

| AC / PS и источник PATH 1.3 | Реализация/путь/SHA | Проверка/run/подмены | Evidence | Статус / остаток / владелец |
| --- | --- | --- | --- | --- |
| AC01 / все: minimal bootstrap, ownership | Existing stand + exact release seed; 136b858 | Bootstrap repeat LLM=0, пустая owned-БД/маркер/cleanup; safeguards unit | E/free-136b858; V/backend.log.gz | PASS в owned scope; постоянная БД не seed/cleanup target |
| AC02 / PS-01: org create/reload/repeat | Existing UI/entry/API | a8d8fcf создал новую org; технические organization tests; полный final UI repeat не выполнен | P/run.json; V/integration.log.gz | BLOCKED для полной финальной приёмки; повтор создания org в целевом run отдельно не доказан |
| AC03 / PS-01: approved program/catalog/roles | path_start_release_source/inputs; fixture | READ ONLY + 15/15 recompute; 9 Cases/27 original QA; bootstrap проверяет exact hashes | tests/browser/fixtures/path-start-release.json; E/free-136b858 | PASS техническая идентичность/происхождение; не новый human review/CURRENT |
| AC04 / PS-01: exact connection GET/reload | Existing R10, без переиздания | a8d8fcf подключение + reload; R10 browser и program DB tests | P/ps02-read-error.json; V/browser.log.gz; V/integration.log.gz | PASS проверенный путь, без новой публикации |
| AC05 / PS-01: slow/error/null/foreign/lost reply | Existing R10 entry/dist/contracts | Browser mock pending/null/lost reply/reopen/logout; frontend/HTTP contract regressions; не реальные сбои permanent test | V/browser.log.gz; V/frontend.log.gz; V/http.log.gz | BLOCKED полной приёмки AC; перечисленные адресные регрессии PASS, не весь final PATH |
| AC06 / PS-01: admin own scope/auth | Existing auth/routes, separate contexts | a8d8fcf admin login; HTTP/owned integration authorization | P/run.json; V/http.log.gz; V/integration.log.gz | PASS проверенный scope; внешняя почтовая доставка не проверяется |
| AC07 / PS-02: confirmed scope/revision/read states | PG-R2 projection + stale read guard | initial actual 503 FAIL → a8 actual retry PASS; unit/HTTP/PG stale/foreign checks | E/initial-eb3c762; P/ps02-read-error.json; V | PASS адресное исправление; read error не отменяет подтверждение |
| AC08 / PS-03: member/job/BaseRoles | Existing R01/source capabilities | a8 UI member/job/specialist_expert; source/role contracts в regression; явная полная UI-проверка шести ролей не предъявлена | P/run.json; fixture; V/integration.log.gz | BLOCKED для целого AC; specialist_expert проверен, шесть BaseRoles требуют отдельного полного readback |
| AC09 / PS-03: atomic assignment/idempotency | Existing R02 assignment/bindings | a8 назначение; owned path29/assignment contracts + real PG tests, synthetic negative fixtures | P/run.json; V/integration.log.gz; E/free-136b858 | PASS в проверенном API/DB scope; не повтор full final UI |
| AC10 / PS-03/04: exact denial/rollback | PG-R1 Api/acquaintance/router; existing assignment API | before 5 FAIL → unit/HTTP PASS; scoped/source negatives в PG | E/pgr1-initial-a8d8fcf; V/backend.log.gz; V/http.log.gz; V/integration.log.gz | PASS адресные причины/запреты, без изменения норм |
| AC11 / PS-04: participant-owned identity | Existing auth/ownership | a8 own invitation/session; HTTP foreign access 403; owned path29 | P/run.json; V/http.log.gz; V/integration.log.gz | PASS выбранный путь; три session contexts/контролируемый mail sink |
| AC12 / PS-04: acquaintance persistence/reasons | PG-R1 + unchanged R03 | a8 reload/acquaintance/auto-trigger; negative UI reason + HTTP regressions | P/run.json; V/browser.log.gz; V/http.log.gz | PASS адресная сохранность/объяснение; не финальная новая AS |
| AC13 / PS-04: frozen profile/provenance/no PII | PM-02, new allowlisted lineage collector | a8 profile → Cycle refs; новая owned API→profile lineage regression; privacy assertions | P/source-to-runtime-receipt.json; E/free-136b858; V/node.log.gz | BLOCKED для полного целевого readback: старый run не содержит всех refs/времён; не реконструируются |
| AC14 / PS-04: real LLM/admission/UI; PREP-DIAG | PM-03 существующий, strict validator сохранён; ST-R1/R4 fixes | a8 real 20 operations; final candidate FAIL после repair; checks сохранены, AS нет; Node PASS_WITH_WARNINGS регрессии | P/source-to-runtime-receipt.json; P/runner-result.json; E/st-initial-a8d8fcf; V/node.log.gz | FAIL фактический admission / BLOCKED AS; отдельная задача PM-03 владельца. PREP-DIAG-01 UNKNOWN |
| AC15 / PS-03/04: assignment/job lineage | ST-R3 actual admin SQL/compatibility projection | initial PG 3 FAIL → full integration и адресный repeat PASS; two scopes/same config/foreign newer job/unknown | E/lineage-initial-9f9b7b8; V/integration.log.gz; E/free-136b858 | PASS техническая negative fixture, не preseed главного E2E |
| AC16 / PS-04/05: plan/time before explicit start | M7 existing gate; no-AS projection fix; timing collector | a8 prepared/start null; unit ready-plan-without-AS FAIL→PASS; будущие time refs validated; старых effective times нет | P/source-to-runtime-receipt.json; E/start-gate-initial-9f9b7b8; V/node.log.gz | BLOCKED целевые оба времени/READY route с admitted AS; не запускать таймер ради отчёта |
| AC17 / PS-05: start/same AS/zero answers/repeat | Existing explicit start/strict validator | AS отсутствует; start/presentation NOT_RUN; DB assessment_answers=0, started_at=null | P/source-to-runtime-receipt.json | BLOCKED_PM03; не выдаётся за PASS, владелец отдельной генерации |
| AC18 / все: final SHA/full run/viewport/evidence | 136b858 + docs/evidence commits; packet metadata фиксирует final SHA | Backend/HTTP/front/integration/browser/Node; viewports4 mocked; full final real-provider повтор NOT_RUN по решению владельца | E/verification; E/viewports-after; пакет diff/bundle/MANIFEST/VERIFY | BLOCKED полной PATH приёмки; независимые fixes переданы, CI/main/deploy раздельно |

## Checkpoint источников и runner (до изменения продукта)

Read-only текущего test подтвердил описанные program/config/catalog IDs/checksums,
SHA 7221671, target `agent4k_test` через host port 55432 (внутри PostgreSQL 5432).
Receipt `tests/browser/fixtures/path-start-release.json` содержит девять Cases,
27 оригинальных QA JSON/checksum, owner decision, runtime refs; не содержит users
или историю. Независимая проверка JSON и воспроизведение admitted package совпали.
Новая публикация не выполнялась. `tests/path_start_release_source.py` выполняет
только SELECT в READ ONLY transaction; проверка identity/checksum fail-closed.

Existing runner получил `--program-source published-pilot`; legacy diagnostic default
сохранён. Target seed импортирует exact approved package и неизменённые QA origins,
сверяет IDs/checksums и только затем создаёт техническое mirror ProgramDefinition.
Это не новый human review/методологическое согласование. Минимальность дополнительно
проверяется в owned bootstrap. Продуктовые Api/web на этом checkpoint неизменны.

Локальный минимум: backend 743 PASS / 318 deselected; HTTP 106 PASS / 12 deselected;
Node receipts 27 PASS; frontend 131 PASS; lint/build/diff PASS. Первый запуск backend
имел 9 ошибок из-за неверного пути новой fixture; путь исправлен, адресный повтор
9 PASS и весь набор 743 PASS. К продукту/историческому INCOMPLETE это не относится.

Следующий шаг — owned bootstrap и исходный UI run: негативный GET уже подтверждённой
анкеты проверяется до LLM. Это ещё не PATH PASS и не итоговый кандидат.

Первый bootstrap 9cefe53 (`ce02e158ef8b470ab68472ba91a36769`) остановился на
RELEASE_CASE_MISMATCH до browser/provider; cleanup подтвердил удаление owned-БД.
Причина: пустая БД иначе выдаёт физические IDs, включённые в checksums каталога и
ProgramDefinition. Fixture теперь резервирует ещё не занятые release IDs для Case,
catalog/configuration, без создания подставных исторических строк. Операция имеет
whitelist таблиц и запрет постоянной/неизолированной/занятой БД; регрессии добавлены.
Published содержание/QA не изменяется. Это исправление тестового входа, не дефект продукта.

## PS-02 / PG-R2 — исходный дефект и исправление

Исходный run `54c1ca2e33714a5d8e9805589e1349c7` на clean `eb3c762` (продукт
побайтово от main 7221671) создал org/подключение/admin и подтвердил анкету
`specialist-pilot` штатным UI. После reload искусственно потеряно только чтение
GET questionnaire (503), без записи. Renderer назначения показал «Анкета для
выбранной оценки не подтверждена. Подтвердите сведения…» вместо UNKNOWN/read error.
Первый потерянный переход: `questionnaireLoadStates.error` → assignment readiness.
Причина: renderer проверял только отсутствие локального `publishedRevision`, игнорируя
статус чтения. Evidence: `docs/evc/evidence/path-start-01/initial-eb3c762/`, исходный
read-error JSON/скриншот/run/code-identity/runner-result/completion/process-result/
cleanup/source-provenance. Подготовки/LLM/start/оценочных ответов нет, dependent PS-03…05
в этом run NOT_RUN; cleanup marker/absence подтверждены. Отдельный предыдущий run
1efe5c7 остановился на неоднозначном locator hidden-разделов; это harness, не продукт.

Исправление: отдельная pure UI projection отличает loading/error/unknown от
действительного отсутствия подтверждения после успешного чтения. Сохранённая
confirmed revision не отрицается, UNKNOWN не разрешает назначение; retry остаётся
штатным. Per-organization read generation отсекает запоздалые ответы/ошибки.
Предметный admission/backend/API не менялись. Регрессии 8 PASS, весь frontend
139 PASS; lint/build/diff PASS. Повтор actual entry на новой owned-БД — следующий шаг.

## Новый admission run (не PREP-DIAG-01)

Clean a8d8fcff36eb81ff118c82676af6f9885bbbd4b7; run
`aa2cbb221fdd458a8bb75e9a0faeb8b2`, operation
`687295f9-7635-4fa6-b083-4db724749e92`. PS-02 error/read retry прошёл и процесс
достиг автоматической подготовки после знакомства. Planner выбрал CASE.SPEC.02 v0.6
из целевого nine-case catalog, без подстановки готового участника/profile/AS.
Конечный кандидат `56c303d1ed93170082eacabe3e75a84c5ea662d6499e749276e729488549543d`
отклонён после штатного единственного repair: FAIL, пять blocking checks
`indicator:K4.I13`, `indicator:K4.I14`, `indicator:K4.I16`, `indicator:K4.I17`,
`critical_prohibition:02`. Причины/JSON paths в terminal receipt: вариант B стал
подходить по всем существенным условиям, нарушив обязательную остаточную неопределённость.
Deterministic/protocol errors и incomplete checks пусты. Это установленный
содержательный отказ конечного кандидата, не доказательство дефекта исходного Case
или причины исторического INCOMPLETE. Почему генератор не исправил содержание за
разрешённый repair — отдельная дальнейшая диагностика; технический дефект пока не доказан.

20 unique operations/20 HTTP completions, prompt 1 429 582, completion 75 859,
total 1 505 441 tokens. No JSON retry. Admission/методология/источники/repair не
меняются ради PASS; случайный платный rerun не оправдан. Candidate → AS обрывается
на штатном admission: AS нет. Cycle f80c40bc-d45e-4e39-8b31-17019f27b023 и Session
fe4425cf-51a2-4017-9f30-4009c56ce635 prepared, оба started_at=null, ответов 0.
PS-05 start/presentation NOT_RUN/BLOCKED admission, а не PASS.

Evidence `docs/evc/evidence/path-start-01/preparation-a8d8fcf/`: первичные code/run/
runner-result/source-to-runtime/completion/process-result/cleanup/read-error JSON,
failure screenshot. Terminal export выполнен до удаления owned-БД, cleanup PASS.
User history/state/secrets/raw prompts/provider responses в передаче отсутствуют.
PREP-DIAG-01 по-прежнему UNKNOWN, без причинного объединения с новым FAIL.

## Независимые ST-R1 / ST-R4 / PG-R1

- ST-R1: local Chromium на dist a8d8fcf, синтетические API responses. Открытие
  карточки и отказ от отмены: HTTP mutations=0, но «Выполняем действие…» осталось.
  Причина — capture click выставлял mutation loading до локальной карточки/диалога.
  Эти локальные actions больше не инициируют busy; настоящая команда отмены начинает
  своё состояние только после подтверждения. Browser before 2 FAIL → after 2 PASS.
- ST-R4: при `action=check_preparation` renderer не показывал разрешённую проверку.
  Добавлена кнопка, использующая только существующий authorized organizations GET.
  Без прав чужого preparation endpoint, retry/prepare/start. Browser FAIL → PASS,
  mutations=0. Логи `docs/evc/evidence/path-start-01/st-initial-a8d8fcf/`.
- PG-R1: пять технических unit fixtures до исправления показали generic organization
  wait при отсутствующей должности/ФИО/email, потерю exact questionnaire blocker через
  legacy fallback и перезапись установленной причины общим W02. Исправлены сообщения,
  optional readiness title и сохранение причины. Exact assignment не подменяется
  organization-wide legacy context. Новые statuses/права/схема не вводятся.
  Before 5 FAIL, адресный after 19 PASS; backend 752 PASS, HTTP 106 PASS,
  frontend 139 PASS, lint/build PASS. Исходный лог `pgr1-initial-a8d8fcf/unit.log.gz`.
  Логи gzip без изменения исходных bytes (включая trailing spaces тестового reporter).
- Активна отдельная real PostgreSQL negative fixture ST-R3 (не seed основного E2E):
  две assignment refs одной configuration, разные questionnaire/profile bindings,
  более поздний чужой job; actual production SQL, synthetic schema, LLM=0.

## ST-R3 / start-readiness: initial PostgreSQL и адресное исправление

Clean 9f9b7b8646ba6eca97334cb0864cec83bf78c518, owned run
d667721a6c474f04b269a12f109cab2d: actual stage SQL на PostgreSQL, 3 FAIL.
Для A возвращался job-B/failed вместо job-A/completed. При отсутствии scoped
confirmation также угадывался профиль. Причина: profile выбирался по latest frozen
user/org/configuration, без assignment/questionnaire/role binding. Product preparation
operations вообще не участвовали в этой проекции. Связь Cycle.assignment_id уже
существует, новую не вводим. Primary result/log/cleanup — `lineage-initial-9f9b7b8/`.
Первый технический запуск не выполнил тесты из-за отсутствия pytest в venv сервиса;
он не доказывает дефект. Test tools установлены отдельно, service venv не менялся.

Исправление: latest binding только внутри exact assignment; профиль — по точному
Cycle pointer либо scoped confirmation, с совпадением role/configuration/context.
Product job дополнительно совпадает по user/profile/organization/assignment/questionnaire;
чужой более поздний job не подставляется. Flat compatibility fields получают значение
только при одном доказанном scoped stage; при неоднозначности null/unknown, без
latest-user legacy job/session и без дублирования членов через чужую acquaintance.

Адресная unit-проверка также показала ложный ready_to_start у prepared Cycle/READY
plan без допущенной первой AS (FAIL до исправления, `start-gate-initial-9f9b7b8/`).
Проекция теперь требует admitted AS и не скрывает queued/running/failed подготовки
за предварительно созданным планом. Это отражение существующего admission/start gate,
не изменение admission/правил времени. Backend 755 PASS, HTTP 106 PASS, stage units
8 PASS, diff PASS; actual PostgreSQL повтор — активный следующий шаг.

## Проверки следующего checkpoint

- На de23f47 real PostgreSQL ST-R3 повтор 3 PASS. Полный `tests/integration`, явно
  `-m 'integration and not llm'`: 205 PASS / 4 FAIL; все четыре child processes не
  нашли pytest, поскольку изолированный environment не переносит внешний PYTHONPATH.
  Это setup окружения, не доказательство продуктовой регрессии. Owned DB удалена;
  fixture environment не ослаблялся. В частной копии runtime в worktree установлен
  pytest; рабочий venv сервиса не изменён. Повтор всего набора ещё ожидается.
- Actual entry/browser: 15 PASS — новые ST-R1/R4, PG-R1, widths 1440/320/390/768,
  прежние R10 (pending questionnaire/null/lost PUT/reopen/logout), assignment blockers.
  API в этих UI negative/geometry проверках явно mocked, не девять новых LLM runs.
  Main owned run до admission остаётся отдельным фактом a8d8fcf.
- Визуальный QA обнаружил сжатие текста warning на 320 при общем inline-flex `.error`.
  Scoped CSS grid сохраняет иконку и одну читаемую колонку, без новых цветов/redesign.
  До/после: `viewports-before/admin-320.png`, `viewports-after/` (4 PNG + browser log).
  Browser дополнительно проверяет ширину пояснения >150 px и отсутствие overflow.
- Новые HTTP regressions PG-R1: 2 PASS, с реальным router/readiness projection,
  synthetic SQL/source stubs, owner 200 / anonymous 401 / foreign user 403.
- Дополнительный read-only test readback пересчитал 15 stored definitions: prompt
  bundle, M2 methodology, scenario, role, 9 Cases, package и runtime rules — все match.
  Receipt дополнен `artifact_readback`; исходное содержание/refs/QA не менялись.
  В старых run сохраняется прежний receipt hash, его evidence не переписан.

Текущий шаг не является завершением PATH. PM-03 content FAIL после repair остаётся
конкретным ограничением первого старта. Владелец выбрал отдельное согласование
генерации и передачу независимых исправлений; повторный платный запуск не выполняется.

## Дополнение диагностики без повторной генерации

Будущие receipts дополнены точными assignment/binding/questionnaire/profile refs,
checksums трёх источников профиля, frozen_at, связью preparation request → profile,
планом/его revision/checksum, обоими effective times и источниками их разрешения.
Только allowlisted metadata: без ФИО, контактов, ответов, raw prompts/responses.
Неоднозначная связь — UNKNOWN_OR_AMBIGUOUS, без угадывания. Старый run не дописывается:
не выгруженные тогда времена/lineage после cleanup остаются неизвестными.
Регрессии: Python 52 PASS, Node 38 PASS; позитивная real PostgreSQL проверка
дополнена в существующем `test_path29_participant_owned_stand.py` (LLM=0).

Полный integration на clean `2c813f2583fe144c29b72dfb684e92f92829181d`:
209 PASS / exit 0, 500.50 s, run `13567c1db70c482689c9a65ce85ff47a`, LLM=0,
owned cleanup PASS. Предыдущие 4 environment FAIL не скрыты, причина устранена
частным test interpreter, повтор успешен. Продуктовый Api/web после этого SHA
не меняется; для нового collector выполняется отдельная адресная регрессия.

## Итог независимого блока и применимость проверок

Передаётся код `136b8587346c2728014570f755fa98321a223b25` + финальная запись
отчёта/evidence, без новых продуктовых изменений после проверенного SHA. Final
immutable SHA фиксируют head draft PR и MANIFEST пакета; это база, не EVC baseline.

| Этап | Реализация и проверка | Остаток |
| --- | --- | --- |
| PS-01 | Read-only точная публикация; mirror seed; org/program/admin через реальный UI, R10 переиспользован | Финальный целый repeat не выполнен; повтор org и полный AC05 не выводятся из одного happy path |
| PS-02 | Scoped confirmed questionnaire; PG-R2 первоначально воспроизведён, исправлен; actual 503/retry и unit/UI/HTTP regressions | Общий test с новым кодом не развёртывался |
| PS-03 | Реальное добавление участника с должностью/assessment role и назначение; exact bindings; ST-R3 SQL исправлен/PG проверен | Полный six-BaseRoles UI readback в передаче не заявляется |
| PS-04 | Собственная сессия, знакомство/auto-trigger, реальный LLM и final checks; PG-R1/ST-R1/ST-R4 исправлены | PM-03 содержательный FAIL после repair; генерация — отдельное согласование |
| PS-05 | Строгий explicit start validator сохранён; false-ready проекция исправлена; start null/answers0 доказаны | Admission → AS → start/presentation BLOCKED, не PASS |

Команды и первичные логи — `evidence/path-start-01/verification/verification.json`
и `.log.gz`. Gzip сохраняет исходные bytes; SHA-256 распакованных логов записаны
в verification.json. Проверки не заменены собственным текстовым резюме.

| Проверка | Точное основание / результат |
| --- | --- |
| `npm run test:backend` | 136b858: 757 PASS, 323 deselected, exit 0; warning deprecated httpx adapter, не FAIL |
| `npm run test:backend:http` | 2c813f2: 108 PASS, 12 deselected, exit 0; Api/web побайтово совпадают с 136b858 |
| `node --test tests/frontend/*.test.mjs` | 139 PASS, exit 0; неизменённый набор/JS после 2c813f2 |
| `npm run lint:js`, `npm run build:web`, `git diff --exit-code -- web/dist` | 136b858: PASS/exit 0; dist соответствует сборке, нет потерянных пользовательских файлов |
| PostgreSQL `pytest --run-integration -m 'integration and not llm' tests/integration -q` | 2c813f2: 209 PASS, exit 0; новая owned-БД/cleanup PASS; product runtime идентичен 136b858 |
| Новый collector + actual SQL, два integration файла | 136b858: 4 PASS / exit 0, 13.85 s; fixtures технические, provider disabled |
| Node receipt/persistence | 136b858: 38 PASS / exit 0; обязательные stages, final candidate, PASS_WITH_WARNINGS, refs/timing |
| Python runner/source/collector адресно | 136b858: 52 PASS / exit 0 |
| Actual entry/dist browser filtered `auth-r03.spec.mjs` | 15 PASS / exit 0, 16.4 s; mocked HTTP, не real-provider PASS |
| Actual exporter regression / bootstrap repeat | 136b858: оба PASS, LLM=0, owned cleanup PASS; первичные JSON в `free-136b858/` |
| Real-provider целевой процесс | a8d8fcf: FAIL admission после repair, 20 unique calls; не финальный whole-path repeat |
| Новый CI / full-verification / deployed acceptance | На момент commit передачи NOT_RUN; draft PR запускает fast checks, полный CI/Ready и выпуск требуют отдельного допуска |

При первой бесплатной адресной попытке новый profile collector **прошёл**, а три
SQL fixtures заблокировала защита `TEST_DATABASE_URL must not point to DB_NAME`.
Попытка убрать DB_NAME была отклонена `ISOLATED_STAND_CONFIGURATION_REQUIRED` ещё
при collection. Исправлен только внешний task-wrapper: выделены две настоящие
owned-БД для runtime и TEST_DATABASE_URL. Итог 4 PASS, обе БД штатно удалены.
Код защит не менялся. Все три результата/логи/cleanup сохранены в
`free-136b858/{initial-wrapper,repeat-wrapper,final-wrapper}/`.

### Review, риски и передача

- Изменения: `Api/acquaintance.py` (W02/exact readiness), `Api/routes.py`
  (admin assignment/job projection), web router/organizations/wiring/CSS/dist;
  existing runner/source fixture/collector и технические unit/HTTP/PG/browser tests;
  task/profile/handoff/STATE и safe primary evidence. Несвязанный рефакторинг не включён.
- PM-02 источники/PersonalizedProfile и PM-04 admin readiness/start projection
  затронуты; PM-03 admission/repair/generator/опубликованные prompts неизменны.
  LU локализованы существующими функциями `read_state`, `_build_admin_organizations`,
  questionnaire assignment UI projection; новые LU/схема не вводятся.
- Совместимость: API endpoints/status enums и DB schema прежние; optional readiness
  title только добавляет точное сообщение, legacy неоднозначные поля fail-closed.
  Миграция N/A. Опубликованные `assessment_definitions`, M0–M8 и snapshots не правились.
- Безопасность: deny/ownership guards сохранены; роли не расширены. Автотесты только
  isolated owned DB, permanent test — read-only source metadata. Контролируемая почта
  synthetic `@example.test`, без реальной доставки людям. Нет secrets/PII/raw provider
  inputs/responses/state в Git или пакете. Защита постоянной БД от cleanup сохранена.
- Self-review: согласованность контракта/источников, локальных ссылок, границ fixtures,
  failure-before/fix/after и применимости SHA проверена. Это не human review/приёмка.
- Откат: адресный revert этого блока, без удаления bindings/profiles/истории/snapshots;
  новый деплой не делался. Owned cleanup уже выполнен только для своих run IDs,
  с проверкой marker и отсутствия DB/state, без FORCE. Не расследовать DB recovery.
- Ветка push разрешён/выполнен; main `7221671…`, приложение 2.0.62; permanent test
  остался на том же SHA. PATH merge/deploy/version bump/artifact publication — не выполнялись.
  Базовый принятый SYN уже в main; target published-pilot и fixes есть только в этой ветке.
- Следующий минимальный шаг владельца — согласовать отдельную задачу PM-03 по
  [точному блокеру](../reports/path-start-01-pm03-blocker.md), не изменять методологию
  или admission ради PASS. Затем обоснованный whole-path repeat и отдельный выпуск.
  PREP-DIAG-01 остаётся UNKNOWN; причинная связь с новым FAIL не установлена.

### Независимый пакет

ZIP `4K_PATH_START_01_<final SHA12>.zip`: профиль/runner/fixtures, changed source,
полный binary diff к main 7221671, Git bundle (prerequisite тот же main), первичные
source/run/runner-result/checks/cleanup и SHA-256 MANIFEST с offline VERIFY.py.
Пакет не является PASS PATH: verifier проверяет целостность и именно отрицательный
admission/start-null/zero-answers результат, происхождение source QA и cleanup.
Финальные SHA/CI-ссылки — в его HANDOFF/MANIFEST и PR; приватный server checkout
для независимого чтения не нужен. Принятый старый пакет 2f0a5a0 не переписывается.
