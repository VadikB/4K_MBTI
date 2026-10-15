# UX-P01 — маршрут, состояния и замена AS

## Результат и границы

Реализовать устойчивые позиции маршрута и атомарную замену текущей предъявленной
незавершённой AS новой AS того же CaseID/version на том же месте. Сохранить историю,
исключить old AS из действующего покрытия/расчёта и оставить legacy Cycles совместимыми.

Не входят: автоматическое правило возврата, UX ветки отсутствия, управление временем
после возврата и LLM-генератор. Обычный runtime provider выключен (`None`);
контролируемый `FixedCaseReplacementProvider` предназначен только для изолированной
приёмки.

## Источники и решения

- Вход: `UX-P01_Time_Interruption_Return_2026-10-15.txt`, rev 2.0.
- База: `main` / `041e9af`, версия 2.1.33.
- M1 v1.4 §§5–10; M6 v1.8; M7 v1.3; Change 01; task manifest; ADR-002.
- Технический контракт: `docs/architecture/m7-route-replacement-contract.md`.
- Решение владельца: та же позиция и CaseVersion, обязательная история, old AS
  исключается; вариант presentation versions внутри одной AS не применяется.

Стоп-условия: предметное решение, аддитивная схема, совместимость и откат заданы.
P03 отсутствует, поэтому автоматический trigger/presentation/time resume не реализуются.

## Реализация и трассировка

| Правило | Данные/контракт | Код | Проверка |
| --- | --- | --- | --- |
| Та же позиция и Case | route position/history | `m7_route_replacement.py` | PostgreSQL integration |
| Один эффект и stale guard | operation request hash + row locks | `replace_current` | replay/stale integration |
| Old AS сохраняется, но исключается | disposition/reason/operation | M7 facts/completion, C-46, M6 input | integration |
| Owner scope | optimistic HTTP contract | `routes.py`, `m7_replacement_contracts.py` | e2e HTTP |
| Legacy read | `legacy_current` | `_composition` | существующая M7 regression |

## Проверки

- `py_compile` затронутых Python-модулей — PASS.
- `git diff --check` — PASS.
- `pytest tests/unit/test_m7_cycle_planner.py tests/unit/test_m6_cycle_aggregation.py -q` — PASS, 8.
- `pytest tests/integration/test_m7_cycle_planner_db.py -q --run-integration` на
  `agent4k_pytest` — PASS, 11; включает two-tab race, owner/stale/expired/terminal
  guards, late C-54, M6 input и
  сохранённый preparation failure без половинного переключения.
- `pytest tests/e2e/test_m5_runtime_http.py -q` — PASS, 5.
- `npm run test:backend` — 407 PASS, 13 FAIL: существующие M6 admission/evidence/
  indicator tests не совпадают с текущим provider contract (`INPUT_NOT_READY`,
  `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`); затронутые P01-тесты проходят.
- Startup на совершенно пустой PostgreSQL — NOT_RUN: общий `ensure_core_schema`
  ожидает существующую базовую таблицу `users`; адресная схема P01 успешно создаётся
  в 11 изолированных integration-сценариях через штатный `ensure_m5_runtime_schema`.

## Риски и откат

- Схема: только новые таблицы/индексы/FK; AS/Turns/snapshots не удаляются.
- Конфиг: production provider отсутствует, обычная оценка не создаёт замену.
- Деплой: schema bootstrap создаёт расширение штатно.
- Откат: отключить endpoint/provider и вернуть код; сохранённая история остаётся
  доступной совместимому коду, удаление данных не требуется.

## Непроверенное и следующий шаг

Полный substantive admission → C-56 с различающимися old/new IA и полный CI ещё
не выполнены. Текущая integration проверяет C-46 → M6 input: late old C-54 остаётся
в истории, но не попадает в observations и не блокирует readiness. До PR требуется
либо расширить расчётное доказательство, либо явно не заявлять критерий 7 полностью.
