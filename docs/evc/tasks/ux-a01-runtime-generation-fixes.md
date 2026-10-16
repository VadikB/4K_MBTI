# UX-A01 — исправления runtime и генерации

Дата: 16.10.2026. Ветка: `codex/ux-a01-runtime-generation-fixes`.
База: `main@39ffa2bdd43c002341a6630b905018d080f396ef` (PR #53).

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
- Полный `pytest -m unit` — 238 PASS / 3 FAIL. Все три FAIL воспроизводят независимый
  baseline `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED` в M6 evidence/indicator tests;
  затронутые A01-наборы PASS. Исправление provider contract не включено в этот PR.
- Real LLM, production activation, browser/device visual matrix — NOT_RUN: не входят
  в разрешённую область. CI — NOT_RUN до публикации ветки/PR.

## Совместимость, безопасность и откат

- Публичные данные аддитивны; новая nullable `lease_expires_at` создаётся
  `IF NOT EXISTS`. Исторические AS, Turns, snapshots и checksums не переписываются.
- Секреты/production data не читались; integration использует только изолированную
  БД с `pytest` в имени; реальные LLM-вызовы не выполнялись.
- Откат кода возвращает прежнее чтение/маршрутизацию. Колонку и сохранённые operation,
  candidate AS и admission history не удалять; они безопасно остаются аудиторским
  следом. Config-переменные можно убрать после отката кода.

## Передача

Следующий шаг: локальное ревью diff, commit/push, PR, обязательный CI и только затем
решение владельца о merge. Production activation остаётся отдельным решением.
