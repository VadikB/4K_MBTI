# UX-A01 — исправления runtime и генерации

Дата: 16.10.2026. Ветка продолжения: `codex/ux-a01-add01-configuration`.
База: `main@39ffa2bdd43c002341a6630b905018d080f396ef` (PR #53).
Основной A01 перенесён коммитом `eb755d8b712f59339d74cdd828cc83131a338bea`
поверх актуальной цепочки R04/W02/P03, без возврата на старый SHA.

## Результат и границы

Исправлены F01–F05 аудита: данные Case не раскрываются до предъявления; текущая AS
определяется маршрутной позицией; непривязанные кандидаты не меняют journey,
завершение и вход расчёта; admission разделён для QA и assessment; generation lease
восстанавливается с fencing и ограниченным retry; return read model учитывает лимиты,
готовность кандидата и различает плановые и созданные позиции.

Production-активация генерации, новые предметные критерии трудности/уровней,
нормативные изменения и исправление независимого M6 provider-contract baseline в
область A01 не входят.

## Источники и решения

- `UX-A01_Runtime_Generation_Fixes_2026-10-16.txt`, rev 1.0,
  SHA-256 `9030e274321a088c1c0dffbb9762074608fe4e22d4ff4aafda4d8dc6660fcd05`.
- `P4K_Audit_All_Tasks_2026-10-16.txt`,
  SHA-256 `aa5deb1b01a56d6a988e590414cdf4d224c2bf551f2470465b1ae5e8100fe1bc`.
- `UX-A01-ADD01_Configuration_2026-10-16.txt`, rev 1.0,
  SHA-256 `54ed467f8828565c39428b2b9d20b40c9544f54bacf1b78d18b7622e796d66a1`.
- AS-IS карта `docs/evc/timer-and-configuration-storage.md`, SHA-256
  `6825b71316f6a3ca3d35efae8e567d51b0dc848cf5e4ae572f2c69a82b022a1`;
  файл пользователя прочитан, но не изменён и не включается в коммит.
- `README.md`, `CONTRIBUTING.md`, EVC workflow, verification matrix и artifact recipe.
- Architecture context/Registry, Change 01, source-set manifest 2026-10-01,
  ADR-002 и существующие P01/P02/P03/W02 контракты и тесты.

Решение сохраняет владение PM-03/PM-04/PM-05: candidate остаётся сохранённой
аудируемой AS, но становится частью действующего маршрута только через P01;
PM-05 явно исключает `unattached_candidate`. Полноценный assessment admission требует
published/approved contract и активные PASS evidence с provenance. QA остаётся
`approved_for_qa`; QA fixture не становится production-нормой.

Открытых стоп-условий для QA/runtime-исправления нет. Отсутствие опубликованного
assessment admission закрывает только production activation, что соответствует
постановке. Управляющие документы и artifact debt register не изменялись.

## Реализация

- `Api/m10_product_flow.py`, `Api/m7_cycle_planner.py`, `Api/m7_completion.py`:
  route-owned current AS, закрытая проекция до start, исключение кандидатов из
  participant runtime и завершения с сохранением истории в C-46.
- `Api/m6_cycle_aggregation_repository.py`: непривязанные кандидаты не попадают в
  observations C-56 и получают явный processing status.
- `Api/m5_equivalent_generation.py`, schema/config examples: структурная и
  содержательная валидация, независимый admission evidence, lease expiry, fencing,
  bounded retry и replay до проверки stale current AS.
- `Api/m7_route_replacement.py`: повторная проверка operation→position→old AS→
  Cycle/Session/profile/CaseVersion и последнего admission перед переключением.
- `Api/m7_return_integration.py`: terminal/deadline/budget-aware action, требование
  готового candidate и отдельные planned/created counts без мутации GET.

## ADD01: единые источники и фиксация настроек

- `Api/m7_parameter_resolution.py` добавляет узкий M7-контур immutable published
  revisions, привязанный к существующим `organization_id` и
  `assessment_configuration_id`. Это не универсальный configuration service.
- Порядок разрешения применяется отдельно к каждому параметру: method default →
  organization revision → program/configuration revision → superadmin QA override.
  Assessment override из HTTP/вызова отклоняется.
- `None` означает отсутствие слоя; `0`, отрицательное значение, `bool`, строка и
  неизвестное поле дают явный отказ. Повреждённый checksum опубликованного источника
  не заменяется default.
- Cycle сохраняет секунды, точный source kind, revision ID/no, checksum и resolution
  checksum. Изменение активной ревизии влияет только на новый Cycle.
- Подготовленный, ещё не начатый план меняется только через новую
  `m7_plan_revisions` revision. Чтение не создаёт историю; после первого старта
  параметры заморожены.
- `m7_planning_package.load_rules` явно запрещает значения `duration_estimate`,
  `tie_break`, `required_case_statuses` и `required_qa_scopes`, которые текущий
  алгоритм не умеет исполнять.
- Equivalent generation принимает только server-resolved provider identity. QA
  использует точный controlled fixture ref; ложный клиентский checksum отклоняется.
  DeepSeek manifest остаётся `draft`, поэтому assessment generation закрыта, а
  credentials не попадают в snapshot.

| Параметр | Смысл/единица | Владелец и default | Разрешённое изменение | Snapshot и влияние |
|---|---|---|---|---|
| `time_budget_seconds` | фактический сбор, секунды | PM-04, `m7_cycle_plan/1.0.0` | organization; program; QA override только в `qa` | Cycle + plan revision; начатый Cycle не пересчитывается |
| `calendar_window_seconds` | календарное окно, секунды | PM-04, `m7_cycle_plan/1.0.0` | organization; program; QA override только в `qa` | Cycle + plan revision; reload/Session/replacement не пересчитывают |
| generation lease/max attempts | технический lease/retry | server settings | deployment config, без изменения предметного replacement limit | фактические значения сохраняются в `provider_config_json` операции |

Полный административный редактор, правило второго этапа «последний кейс + 5 минут»,
production provider/prompt publication и UX-W02/P03 ADD01 не входят в этот результат.

## Проверки

- `py_compile` изменённых Python-модулей — PASS.
- Unit + HTTP: participant projection, generation validation и runtime HTTP —
  15 PASS, одно существующее предупреждение Starlette.
- Полный HTTP/E2E-набор `tests/e2e` — 65 PASS, одно существующее предупреждение
  Starlette.
- PostgreSQL `tests/integration/test_m7_cycle_planner_db.py` на изолированной
  `agent4k_pytest` — 18 PASS.
- PostgreSQL product path prepare/start/current/C-46 с непривязанным candidate —
  1 PASS.
- ADD01 unit (`test_m7_cycle_planner`, `test_m5_equivalent_generation`) — 7 PASS.
- ADD01 PostgreSQL — 3 PASS: независимые organization/program sources, новый/старый
  Cycle, invalid values/scope, plan revision/read/freeze.
- M7 planner + Cycle runtime PostgreSQL regression — 22 PASS.
- Clean bootstrap после включения новой schema в штатную инициализацию — 3 PASS.
- Полный HTTP/E2E на текущем head — 56 PASS, 10 deselected, одно существующее
  предупреждение Starlette.
- Полный backend — 415 PASS / 13 FAIL. Сбои находятся в известном M6 baseline
  (`INPUT_NOT_READY`, `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`), затронутые ADD01
  unit-наборы PASS.
- Полный integration initial run — 87 PASS / 39 FAIL. Один ADD01-релевантный
  clean-bootstrap mismatch исправлен и повторно дал 3 PASS; остальные сбои —
  существующая цепочка M6/provider и зависящие от неё product/M8 сценарии плюс
  отдельный profile journey baseline. Полный набор после точечного исправления
  повторно не запускался; обязательный CI остаётся NOT_RUN до PR.
- Real LLM, production activation, browser/device visual matrix — NOT_RUN: не входят
  в разрешённую область. CI — NOT_RUN до публикации ветки/PR.

## Совместимость, безопасность и откат

- Публичные данные аддитивны; `lease_expires_at` и `m7_parameter_revisions`
  создаются `IF NOT EXISTS`. Исторические AS, Turns, snapshots, Cycles и checksums
  не переписываются.
- Секреты/production data не читались; integration использует только изолированную
  БД с `pytest` в имени; реальные LLM-вызовы не выполнялись.
- Откат кода возвращает прежнее чтение/маршрутизацию. Таблицу/колонку, parameter
  revisions, plan revisions, operation, candidate AS и admission history не удалять;
  они безопасно остаются аудиторским следом. Активную M7 revision при откате
  заменить новой совместимой revision, не редактировать опубликованную.

## Передача

Следующий шаг: локальное ревью diff, commit/push, PR, обязательный CI и только затем
решение владельца о merge. Production activation остаётся отдельным решением.
