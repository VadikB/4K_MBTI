# EXEC-FIX-01: адресная сверка источников и исходного кода

Проверено только чтением на исходном HEAD `46a5532` (2.0.87), 09.11.2026. Единственный писатель ветки — root; эта записка не меняет код, нормы, публикации или действующие снимки. Прямое поручение пользователя заменяет организационный паспорт архива: USER/Codex, `USER_WORKTREES/exec-fix-01`, `P4K-EXEC-01-USER`; продуктовые A1–C6 неизменны.

## Применимость

Change 01 (WORKING, 01.10.2026), M1 v1.4 FROZEN/CURRENT=NO, M5 v1.1, M6 v1.8, M7 v1.3, M8 v1.2 выбраны существующим SourceSet. Их наличие не означает runtime publication. Исторические REVIEW/M0-unavailable и прежняя граница draft return-contract (scenario_ended исключён) не отменяют явно заданную карточкой EXEC-FIX-01 правку. Новая предметная политика не нужна. Миграция, изменение опубликованных данных или runtimeManifest не требуются по обнаруженным пробелам.

## Traceability источники → правило → PM/LU → API/данные → проверка

| Критерии | Источник/правило | PM/LU, реализация, необходимая проверка |
|---|---|---|
| A1 | M1.6; M5.5.5/5.5.7; M7.5.2/5.3/6.3: scenario_end оставляет AS открытой; чтение/обдумывание не absence | PM-04 LU-04.2/04.4/04.6; return heartbeat + DTO/client должны допускать только применимую незакрытую scenario_ended AS. PG/browser heartbeat дольше lease и реальный Continue DTO. |
| A2 | M5.5.8, M7.5.5/8; SLS04 R1 policy v2: same AS, explicit Continue, никакой замены | PM-04 LU-04.2/04.6; return_state/continue_return; тот же AS/Dialogue и остаток, provider замен не вызван. |
| A3 | FIX-RETURN-01: late lease не переносит server boundary назад; M7.5.3 интервалы не удваиваются | PM-04 LU-04.6; после Continue leases удаляются, collecting start защищён от ended_at<started_at; PG immediate/late/reload/two-client регрессии. |
| A4 | ADR-002 identity/owner/current checks; закрытый Dialogue не принимает Turn | PM-04 LU-04.2; owner/current AS/terminal guards сохраняются; HTTP чужая, устаревшая, закрытая/terminated AS отклонены. |
| B1 | M7.5.3/5.4/6.3: единый бюджет + независимый deadline, сбор прекращается на первой границе | PM-04 LU-04.6; clarification answer reuses atomic write-admission Cycle→AS/Session; до границы accepted; на/после неё zero Turn/response/interim/job. |
| B2 | M7.5.5; existing return guard + blocking_system_wait | PM-04 LU-04.2/04.6; Session/Cycle active + no open blocking wait + Continue; pause/recognized absence blocked. |
| B3 | ADR-002 идемпотентность Turn; Change01 И-6 повтор доставки не создаёт материал | PM-04 LU-04.5; после Cycle→AS lock re-read response; идентичный accepted request replay прежде новых write guards, изменённый payload конфликт. Проверять и turn_id/request_id/content; replay после expiry/close. |
| B4 | ADR-002 сериализация close/Turn; FIX-RETURN-01 интервалы | PM-04 LU-04.2/04.5/04.6; все конкуренты Cycle→AS; два новых answer после ожидания lock не используют устаревший decision; реальные PostgreSQL races, zero duplicate effects/negative interval. |
| B5 | M7.5.3 и M8.1.3: уточнения, чтение и ответы тот же budget; исключаются лишь фиксированные blocking waits | PM-04 LU-04.6; existing interval model; никаких новых нормативных порогов. `minimum_remaining_seconds` хранится в существующем snapshot механизма и не вводится этой задачей. |
| C1 | M6.6.6/6.6.7; M7.6.3; Change01 И-4, ADR-002 C45/C54 | PM-04 LU-04.4/04.7 ↔ PM-05 LU-05.3; Finish требует актуальный разрешающий semantic decision на последний принятый material; pending/WAIT_TECHNICAL/open ASK блокируют; UI фактическое ожидание/ошибка. |
| C2 | M1.6; M6.6.2; ADR-002 final C45 только closed AS и полный материал | PM-04 LU-04.5/04.7 → PM-05 LU-05.3; одно закрытие/final/outbox; Cycle открыт между AS; PG exact final material refs. |
| C3 | M6.6.6 last included Turn; ADR-002 interim старой material revision не применяется к новой | PM-04 LU-04.4/04.7; M7 decision.c54/handoff boundary сопоставить latest interim C45 и latest actual Turns; новый accepted answer лишает старый NO_QUESTION разрешающей силы. |
| C4 | Change01 И-6; ADR-002 повторы/ошибки и уникальность final | PM-04 LU-04.5/04.7; Cycle lock + existing final uniqueness/outbox ON CONFLICT; repeated Finish/two tabs/lost response one effect. |
| C5 | M6.6.9; M7.5.4/7.2: final_refusal/time_limit самостоятельные основания закрытия | PM-04 LU-04.7; complete/expire_due_cycles не должны зависеть от обычного Finish semantic gate; pending/failed interim не удерживает сбор после отказа/лимита. |
| C6 | M7.5.3/5.5, UX-E01: between_situations исключает учитываемое время, календарь непрерывен, Next explicit | PM-04 LU-04.2/04.6; finish→pause session, существующая owner Next; readback remaining/deadline и нулевой generation до явного Next. |

## Подтверждённые пробелы исходного кода

- `Api/m7_return_integration.py::heartbeat` допускает только active/paused; `ReturnContinueRequest.expected_state` — те же Literal. Поэтому исходный D1 сохраняется.
- `m7_clarification.answer` проверяет Cycle active/calendar, но не remaining_seconds, Session, blocking wait/return. После `_source(lock=True)` decision не перечитывается, в отличие от уже исправленного `present`: два concurrent answer могут принять устаревшее решение. `record_outcome` имеет тот же stale-read риск.
- `m5_cycle_runtime.assert_collecting` — существующий общий guard Cycle+Session active, blocking wait и оба лимита, его логика/ошибки подходят для переиспользования. Учитывать, что он меняет time states перед ValueError; транзакционная обработка endpoint должна сохранять ожидаемое поведение.
- `finish_current_situation` блокирует только последний ASK без response; отсутствие decision, WAIT_TECHNICAL, старое решение после нового ответа допускают finalizer.
- `finishProductAssessment` ждёт clarification только когда сам сделал active→scenario_end; reload на scenario_ended пропускает ожидание. Общий runtime должен отражать server-authoritative can_finish/phase, чтобы кнопка не зависела от локальной ветки.
- Принятые FIX-RETURN-01 lease reset/boundary guards уже есть: не переписывать. Existing `present` Cycle→AS lock/re-read также сохранить.

## Стыки 01/02 и 03

EXEC-FIX-02 сохраняется самостоятельным результатом. 01 владеет clarification answer admission/replay, return/Continue/Finish. 02 владеет deepseek/preparation semantic scope/Next retry; здесь не запускался. После импорта 01+02 на отдельном compatibility candidate проверить: inter-case Finish→explicit Next; отказ в Finish не создаёт preparation operation; повтор Next сохраняет operation/position scope; heartbeat/return не меняют generation semantics.

Обязательный стык 01+03: accepted clarification до границы → потеря HTTP ответа → close/expiry → owner readback/replay; тот же request_id/turn_id подтверждает один Turn/response/interim/job, изменённый payload конфликт, новая запись запрещена. 03 не меняет handler/guard01; нужное узкое owner readback согласуется по symbol. Эта записка не запускает 03.

## Поздние решения

R1 policy `sales-pilot-return-r1@2.0`: server_presence_lease, heartbeat10/lease120, same AS, explicit Continue, replacement_not_applicable. SLS04/пилот7200/259200 имеют scope; default3600 остаётся и старые snapshots не меняются. PATH-PILOT P/M decision и отдельная publication различаются; receipt для published-release-source должен оставаться `09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b`. Никакой новый paid run/Prod/publication из этих источников не следует.

## Файлы и фактические SHA-256

- `AGENTS.md` — `c304a0383bfbf4d04a29e18abc51fbf51c755731bd282128fb3cb09eb2fc515a`
- `docs/evc/agent-workflow.md` — `a93c6b3e6edaf16bc812a18cb5153fb98d22225001498a659f87726b92e6329c`
- `docs/evc/verification-matrix.md` — `825d8eec26b525bfd862e2187722f7ae326a87fdb533cca6d60c13734ff440c5`
- `docs/evc/artifact-recipe.md` — `cb706183a095ff902db51fe3304ae193305c45c14456e91bb75d646a09f5847a`
- `CONTRIBUTING.md` — `7ac6ceb862081ba964fb28d9d2c5e49d6db6aeda5826a470ddf87b63cb32549e`
- `docs/architecture/product-4k/1.0/context.md` — `effebfc639a572593b6171a7a57cfe60db09bba200909d8a4edafb0e7ac98ebb`
- `docs/architecture/product-4k/registry.md` — `b663db7f557fc3de3abd2d9e86b596926274ba4c5e2170047d4a6e5e60c54001`
- `docs/architecture/product-4k/1.0/updates/2026-10-01/README.md` — `ac082bb94aac1b86c61d7e39589d76c886c6703ef3afc07bc8fecf1676a0a26d`
- `docs/architecture/product-4k/1.0/updates/2026-10-01/source.md` — `ee03f59d78e441f69964352bcd94a1e7c375c2ce306433a8d0cd056ba3af93d2`
- `docs/architecture/product-4k/m1/v1.4/source.md` — `282e69b87585c28b52327e657d71a620c15842f7ade134467788252829833299`
- `docs/methodology/source-sets/2026-10-01/manifest.json` — `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8`
- `docs/methodology/source-sets/2026-10-01/originals/M5.Methodology-v1.1.docx` — `dc96f9b48e0711326c0c4239d63f50a2fa1e63176a728f3e9eb4420f9efb77c1`
- `docs/methodology/source-sets/2026-10-01/derived/M6-v1.8.md` — `f081bc9ca795257b6a4afbebbd4b56f32243a1a75f5c25d91a77c64d64fc86fa`
- `docs/methodology/source-sets/2026-10-01/derived/M7-v1.3.md` — `9b65a8eee1520fed57286b209a28ce73e33cd394ba8c9353c240673867483ec8`
- `docs/methodology/source-sets/2026-10-01/derived/M8-v1.2.md` — `f0272e304f36dc2d58777080b753a5fcc55578d22947e3afbae308b8afb71e0e`
- `docs/architecture/m7-clarification-contract.md` — `03d5aa51ef63489c75a48b2a0b276a02a054a794ee85e7159f3e30b4f70800c3`
- `docs/architecture/m7-completion-contract.md` — `261bfdc28b2c698835c5369485bbaad0c16012e8d6cef6494194a8829fa77feb`
- `docs/adr/002-cycle-as-dialogue-contracts.md` — `4a4e0170bee7faf137301b342fec46b3e8e0209acd26dcb6b2dc7a788c58b25f`
- `docs/evc/decision-register.md` — `4460d8bb7eaca9cb6d94a212f683d871d791f071813026dc9a057d910af04e46`
- `docs/evc/tasks/path-pilot-approved-design.md` — `09534fa95a055ce6525b8b2c880f429941a9f0b3352ddd8fe02c8e505d146d66`
- `docs/evc/evidence/path-pilot-owner-decision-2026-11-05.json` — `3e1293c6978fc042b2461d301cfc78f3b7995445a83599bc583f5f4cf808a04b`
- `docs/evc/evidence/pilot-program-publication-execution/published-release-source.json` — `09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b`
- `docs/architecture/pilot-plan-start-admission-contract.md` — `817ce314c29824f17c1a8051366dbe1ab1803b33120bfc148ae3a0c47e28548c`
- `assessment_definitions/planning/m7_return_integration/v2/policy.json` — `7ee12e5ebbd063ad27c24d415fbe388f9404ac33579621637cae1a94a9342e3a`
- `docs/evc/tasks/sls04-sales-return-budget.md` — `8e0bf272644370d4dec9b32ea9169fe3d5f574cae695b02ab0c7ed306fbdc6e3`
- `docs/evc/tasks/fix-return-heartbeat-race.md` — `5ab3ecb7f1a334a2e8bafac6dc10b19d8b09e88019143dff805a6f3c085f52dd`
