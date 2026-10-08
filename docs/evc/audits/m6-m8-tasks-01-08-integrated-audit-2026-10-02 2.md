# Интегральный аудит Tasks 01–08 M6–M8

Дата проверки: 02.10.2026.
Запрос: `Product_4K_Tasks_01_08_Integrated_Audit_Request_2026-10-02.txt`, редакция 1.
Проверенный commit: `c1bdd8dcecb0dc5d70b32969d384869c7ab602e3`.
Ветка: `codex/m6-task08-cycle-aggregation`. Рабочее дерево до аудита было чистым; сам аудит добавляет только этот документ.
Версия приложения: отдельная release-версия для проверяемой сборки в репозитории не зафиксирована; воспроизводимым идентификатором служит полный Git SHA.

## Итог

Контур Tasks 01–08 **частично принимается технически как restricted QA-контур**. Код и хранение для C-45, доказательной цепочки, C-54, управления Cycle, C-46 и C-56 существуют и проходят локальные unit/HTTP/PostgreSQL проверки. Полная техническая приёмка Tasks 01–08 и начало зависимой реализации Task 09 **заблокированы** тремя обстоятельствами:

1. полного пользовательского маршрута через основной UI/API нет: создание плана, M6, уточнение и агрегация доступны только superadmin QA endpoints;
2. ни один GC не утверждён, реальные LLM-прогоны и Reliability protocol отсутствуют;
3. обязательный E8-F и пакет T8-01–T8-18 не реализованы как воспроизводимая проверка, поэтому история пересчёта C-46/C-56 на изменённом допуске не принята.

Независимые работы Task 09 по C-67/Results/Report можно проектировать и реализовывать за feature boundary на синтетических fixtures. Нельзя подключать их к пользовательскому пути, утверждать корректность фактических результатов или выпускать M8/Prod до закрытия блокеров.

## Проверенный состав

| PR | Commit | Результат |
| --- | --- | --- |
| #24 | `01411eb` | Tasks 01–03: источники/границы, GC-кандидаты, доказательная цепочка M6-A |
| #25 | `5c7dc7b` | Task 04: interim/final IA и C-54 |
| #27 | `e17e241` | Task 05: план Cycle и выбор следующей AS |
| #28 | `164c029` | Task 06: уточнение в том же Dialogue |
| #29 | `93596e7` | Task 07: завершение, continuation, C-46 |
| #30 | `c1bdd8d` | Task 08: агрегация и C-56 |

Основа — `dd3d2ca` (`main`). Все шесть commit входят в проверенный SHA последовательно; отсутствие этих изменений в `main` не трактуется как отсутствие реализации.

Прочитаны `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, EVC workflow, verification matrix, artifact recipe, review checklist, Change 01, ADR-002, registry/traceability, task reports 01–08, task source set и применимые производные M6 v1.8, M7 v1.3, M8 v1.2. Идентичность Change 01 подтверждена `SHA256SUMS`. M0 v1.0 по-прежнему не зарегистрирован локальным оригиналом; это ограничение источников, а не новый дефект runtime.

Изолированная среда БД: временный PostgreSQL 16, БД `product4k_pytest`, отдельные схемы `*_pytest_*`; рабочая/production БД и `.env` не использовались. Реальный LLM не запускался.

## Матрица восьми задач

| Задача | Требование → код/данные → проверка | Основной путь | Нормативная проверка | Итог |
| --- | --- | --- | --- | --- |
| 1. База и границы | FROZEN M1/M2/M3/M4/M5/M6/M7/M8 и Change 01 зарегистрированы; версии и checksum сохраняются в пакетах/snapshots; общие Cycle/Session/AS остаются во владении M5 runtime | Не переключает продуктовый путь | Идентичность источников PASS; методологическая согласованность целиком не переаудирована; M0 original отсутствует | **ПРИНЯТО ТЕХНИЧЕСКИ** |
| 2. Сценарии и GC | TECH fixtures, содержательные кандидаты, blind packet и формы экспертизы есть в `tests/fixtures/m6_gc/v1` и `docs/evc/tasks/m6-task02` | Только QA fixtures | Все approved counts = 0; выводов методолога/эксперта, трёх одинаковых прогонов обязательных GC и Reliability нет | **ЧАСТИЧНО** |
| 3. Evidence chain | `m6_input_resolver`, `m6_repository`, `m6_worker`: Fragment/BS/Evidence/EB, авторство, версии, empty EB, immutable revisions и read-back | Только `/admin/m6-evidence/*`; основной interview его не вызывает | Структура и происхождение TECH PASS; содержательные кандидаты NOT_REVIEWED | **ПРИНЯТО ТЕХНИЧЕСКИ** |
| 4. Interim/final IA | `m6_assessment_*`: L0–L3, IE, NO_ASSESSMENT и TECHNICAL_FAILURE; final требует закрытую AS; C-54 сохраняется | Только `/admin/m6-assessments/*` | Mock/fixture и DB PASS; real provider и GC NOT_RUN | **ПРИНЯТО ТЕХНИЧЕСКИ** в QA |
| 5. План Cycle/AS | `m7_cycle_planner`, versioned rules, frozen profile/goal/time, eligibility, deterministic route и decision read-back | Создание/выбор только `/admin/m7-*`; owner может управлять уже созданным Cycle | Текущий Case pool не имеет утверждённого допуска; кандидаты 0 approved | **ЧАСТИЧНО** |
| 6. Уточнения | `m7_clarification*`: semantic C-54, neutral question, тот же Dialogue, answer/refusal/no-answer, новый interim C-45 и повтор M6 | Только admin QA; UI отсутствует | Gateway подменён; 15 кандидатов, approved=0, real_llm_runs=0 | **ЧАСТИЧНО** |
| 7. Завершение/continuation | `m7_completion`, expiry worker, owner control/completion/additional-session endpoints, immutable C-46 | Owner API есть, UI и пользовательский старт Cycle отсутствуют | DB проверки времени/continuation PASS; 18 кандидатов, approved=0 | **ЧАСТИЧНО** |
| 8. Агрегация | `m6_cycle_aggregation*`: IA→Indicator→Component→Skill, 4 исхода, 5 покрытий, versioned C-56 и reconciliation C-46 | Только `/admin/m6-cycles/*` с ручным admission | E8-A–E8-E PASS; E8-F и T8-01–T8-18 отсутствуют; Reliability `not_verified` | **ЧАСТИЧНО** |

## Две сквозные трассы

### Трасса A — штатное завершение

Фактически выполнена как связка воспроизводимых integration-тестов на одном SHA и настоящем PostgreSQL:

- M7 plan → selected AS → presentation: `test_selected_case_is_prepared_presented_once_and_low_level_does_not_drive_repeat`;
- настоящий C-45 → Evidence/EB → final IA/C-54 → read-back: `test_real_c45_empty_bundle_readback_and_replay`, `test_m6_b_final_ia_c54_transactional_readback_and_replay`;
- clarification в том же Dialogue → новый C-45 → повтор M6: `test_m7_clarification_reuses_dialogue_and_restarts_m6`;
- закрытие AS/Session/Cycle → C-46: `test_completion_closes_open_as_persists_final_c45_and_c46`;
- final IA → manual admission → три уровня агрегации → C-56 → reconciliation C-46: `test_m6_cycle_calculation_persists_c56_and_reconciles_c46`.

Состояние: **ЧАСТИЧНЫЙ PASS**. Хранение и новые соединения с БД проверены; IDs генерировались в изолированных схемах и удалены после тестов. Это составная QA-трасса из нескольких тестов, а не одно прохождение основного UI/API. Модель заменена детерминированным gateway/fixture, admission ручной.

### Трасса Б — прерывание и Additional Session

`test_interruption_allows_one_additional_session_without_copying_dialogue` подтвердил прекращение старой AS, новый Session/новую AS, отсутствие копирования Dialogue и однократность continuation intent. `test_background_calendar_expiry_closes_paused_cycle` и `test_blocking_wait_is_explicit_idempotent_and_does_not_move_deadline` подтвердили сохранение срока и закрытие в фоне.

Состояние: **ЧАСТИЧНЫЙ PASS**. Нет одной трассы «материал первой AS → interruption → Additional Session → неполный final → C-46/C-56 и read-back», нет UI-прохождения и сохранённого аудиторского набора обезличенных IDs/событий. Этот пробел зафиксирован как AUD-03.

## A01–A16

| ID | Итог | Доказательство / ограничение |
| --- | --- | --- |
| A01 | PASS TECH | snapshots и `processing_snapshot_survives_source_change`; основной путь не проверен |
| A02 | PASS TECH | author/material/event/Turn validation, `test_real_fragment_readback`; fixture material |
| A03 | PASS TECH | L0/IE/no IA/technical failure и empty EB различаются; GC не утверждены |
| A04 | PASS TECH | scenario_end/close/pause проверены unit+DB; UI NOT_RUN |
| A05 | PARTIAL | neutral/scope validators и same-Dialogue DB PASS; real LLM/экспертная оценка NOT_RUN |
| A06 | PASS TECH | paused deadline expiry/late state guards; браузерный путь NOT_RUN |
| A07 | PASS TECH | explicit blocking wait idempotent, deadline не сдвигается; полный набор гонок не выполнен |
| A08 | PARTIAL | continuation DB PASS; полного завершения второй трассы до C-56 нет |
| A09 | PARTIAL | idempotency, lease/retry и concurrent claim покрыты; две вкладки и все перечисленные гонки UI/HTTP не воспроизведены |
| A10 | PASS TECH | cross-cycle rejected, composition строится по точным FK Cycle/Session/AS |
| A11 | PARTIAL | формат решения и запрет subset есть; содержательный admission вручную вводит superadmin и GC отсутствует |
| A12 | PARTIAL | E8-A–E8-E и subset PASS; E8-F отсутствует |
| A13 | PASS TECH | четыре исхода, пять покрытий, `0 != no result`, empty denominator=`null` |
| A14 | PASS TECH | failure/processing/readiness различены; real provider NOT_RUN |
| A15 | PARTIAL | checksum/revision/history структуры есть, mismatch отклоняется; E8-F history/recalculation не проверен |
| A16 | PARTIAL | admin/owner API guards PASS; M6/M7 UI отсутствует, legacy совместимость подтверждена только regression suite |

## Выполненные проверки

| Команда | Результат |
| --- | --- |
| `npm run test:backend` | PASS: 310 passed, 95 deselected, 1 deprecation warning |
| `npm run test:backend:http` | PASS: 27 passed, 1 deprecation warning |
| `TEST_DATABASE_URL=<redacted/product4k_pytest> npm run test:backend:integration` | первый sandbox-прогон FAIL из-за запрета TCP; повтор вне sandbox PASS: 64 passed, 341 deselected, 1 warning |
| адресные M6/M7 unit-тесты | PASS: 76 passed |
| `node --test tests/frontend/*.test.mjs` | PASS: 3; warning о `type: module` |
| `npm run lint:js` | PASS |
| `npm run build:web` | PASS; `web/dist` совпал с Git |
| `npm audit --audit-level=high` | PASS: 0 vulnerabilities |
| Change 01 `shasum -a 256 -c SHA256SUMS` | PASS |
| `git diff --check` | PASS |

NOT_RUN: настоящий основной UI маршрут, real LLM, три прогона каждого обязательного GC, независимая часть GC, Reliability protocol, E8-F, T8-01–T8-18, deployment/Prod. Чужой CI на PR показывает frontend/pytest успешными и deploy-test skipped; локальный аудит опирается прежде всего на перечисленные собственные команды.

## Замечания

### AUD-01 — блокер Task 09: отсутствует полный основной пользовательский маршрут

- Задачи/правила: 3–8, A16, Change 01 И-4–И-6.
- SHA/пути: `c1bdd8d`; `Api/routes.py`, `web/js/**`.
- Воспроизведение: найти вызовы `/admin/m6-*`, `/admin/m7-plans`, `/admin/m7-clarifications`; сопоставить с web-клиентом. M6/M7 start/analysis/aggregation в web-клиенте отсутствуют, а runtime endpoints требуют superadmin.
- Ожидалось: пользователь проходит один маршрут от frozen profile до C-46/C-56 с server-side ownership.
- Фактически: owner endpoints управляют уже созданным Cycle; создание, PM-05, clarification и C-56 выполняет QA/admin.
- Ущерб: нельзя принять продуктовый стык, выполнить требуемые UI-трассы или безопасно подключить Results к фактическому пользователю.
- Минимальное исправление: отдельный PR интеграции orchestration/API/UI без изменения предметных формул; owner-scoped read/write и состояние processing.
- Повторная проверка: две трассы A/Б через основной UI/API плюс IDOR/две вкладки/read-back.

### AUD-02 — внешний блокер нормативной приёмки: GC и Reliability не завершены

- Задачи/правила: 2, 4–8; M6.9.5; A05/A11/A14.
- SHA/пути: `tests/fixtures/m6_gc/v1/**`, `docs/evc/tasks/m6-task02/**`.
- Воспроизведение: все manifests показывают `approved_count: 0`; expert cards пусты; clarification/completion `real_llm_runs: 0`; C-56 хранит Reliability `not_verified`.
- Ожидалось: независимые решения на общем frozen input, разбор расхождений, утверждённая версия GC, три успешных повтора и независимая выборка.
- Фактически: пакеты готовы к review, но утверждения отсутствуют.
- Ущерб: нельзя заявлять методологическую корректность IA, clarification, admission и Skill results.
- Минимальное исправление: выполнить уже подготовленный протокол владельцами смысла; код не менять ради получения PASS.
- Повторная проверка: immutable approval artifacts, reviewer identity/role, три прогона, holdout и versioned Reliability report.

### AUD-03 — существенный пробел интеграционной проверки Additional Session

- Задачи/правила: 7–8; A08/A10/A15.
- SHA/пути: `tests/integration/test_m7_cycle_planner_db.py`, `tests/integration/test_m6_evidence_db.py`.
- Воспроизведение: тест continuation заканчивается после создания новой Session; тест aggregation использует штатный Cycle и не проходит interruption.
- Ожидалось: одна воспроизводимая трасса от первой AS через Additional Session до неполного C-46/C-56 и read-back новым соединением.
- Фактически: участки проверены раздельно.
- Ущерб: принадлежность и покрытия финального расчёта после continuation не доказаны целиком.
- Минимальное исправление: один PostgreSQL integration/HTTP тест, сохраняющий audit trace двух Sessions и точный composition.
- Повторная проверка: неизменные budget/deadline, старая AS terminated, новая AS в новой Session, partial outcomes/5 coverages, согласованные C-46/C-56.

### AUD-04 — существенный пробел Task 08: E8-F и T8-01–T8-18

- Задачи/правила: 8; A09/A12/A15.
- SHA/пути: `tests/unit/test_m6_cycle_aggregation.py`, `tests/integration/test_m6_evidence_db.py`, `docs/evc/tasks/m6-task08-implementation.md`.
- Воспроизведение: unit содержит E8-A–E8-E и subset; поиск E8-F/T8 manifest результатов не даёт. Сам task report заявляет только A–E.
- Ожидалось: E8-F даёт новый `4/3`, сохраняет прежний `1`, не удваивает IA, не открывает Cycle; все T8-01–T8-18 имеют фактический статус.
- Фактически: схема поддерживает revisions, но обязательное поведение не воспроизведено и не принято.
- Ущерб: история пересчётов и защита от позднего worker не доказаны; это входная гарантия Task 09.
- Минимальное исправление: versioned TECH fixtures E8-F/T8, unit + PostgreSQL integration + HTTP read-back, без изменения формулы при отсутствии выявленного дефекта.
- Повторная проверка: обе revisions доступны, C-46 ссылается на новую, старая C-46/C-56 неизменяема, stale worker не перезаписывает новую.

## Исправленные прежние риски

Старые F01–F09 не переносились автоматически. На текущем SHA доказаны: frozen profile/target membership; scenario_end отдельно от close; empty EB; авторство и unavailable material; final IA только после close; cross-cycle reject; C-46/C-56 composition mismatch; explicit blocking wait и calendar expiry. Эти результаты ограничены QA/integration-контуром.

## GC и граница приёмки

Готово: TECH fixtures и их checksum; 11 evidence-кандидатов и blind packet; 7 IA, 8 planning, 15 clarification и 18 completion candidates; формы/назначения экспертов. Утверждённых GC: **0**. Реальных LLM-прогонов: **0**. Протокол Reliability: **не выполнен**. Повторные технические тесты не считаются независимыми случаями и подтверждают структуру/арифметику, а не правильность смысла.

## Связное задание на доработку

**Результат:** довести проверяемый контур до одного owner-scoped пользовательского orchestration пути и закрыть недостающие acceptance traces E8-F/T8, сохранив QA/admin инструменты и immutable историю.

Порядок:

1. технический владелец добавляет E8-F, T8-01–T8-18 и полную continuation→C-56 integration-трассу;
2. владелец продукта и безопасности утверждает owner-scoped API orchestration; frontend подключает состояния plan/dialogue/clarification/completion/processing;
3. методолог и эксперт независимо завершают GC review; владелец Reliability проводит versioned protocol;
4. после этого выполняются две UI/API трассы, IDOR/concurrency, real provider на разрешённых синтетических данных и актуальный CI.

Затронутые пути будущей задачи: `Api/routes.py`, M6/M7 services/repositories, `web/js/screens/**`, новые tests/fixtures для Task 08, integration/e2e tests и отдельные approval/reliability artifacts. Управляющие документы и FROZEN источники не менять.

Откат будущей интеграции: отключить новый пользовательский entrypoint/orchestrator, сохранить immutable Cycle/AS/IA/C-46/C-56 и продолжить доступ только через существующий QA read-back. Миграция данных не должна удалять историю.

## Решение по Task 09

**МОЖНО С ОГРАНИЧЕНИЯМИ** проектировать и реализовывать C-67/Results/Report на frozen синтетическом C-46/C-56 за отдельной границей. **ЗАБЛОКИРОВАНО** подключение Task 09 к основному пользовательскому пути, методологическая приёмка результатов и выпуск до закрытия AUD-01, AUD-02 и AUD-04; AUD-03 обязателен для continuation-варианта.

Этот аудит не присваивает CURRENT/baseline, не разрешает merge/Prod и не является окончательным выпуском M8.
