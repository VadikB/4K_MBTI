# UX-P03 — Return Time Integration, продолжение

Дата: 16.10.2026. Ветка: `codex/ux-p03-continue`.

## Результат и границы

Реализовано продолжение P03 по принятому дополнению rev 1.2: server-time presence
lease, multi-client семантика, явная карточка возврата в том же чате, граница
119/120 секунд и предел трёх успешных замен одной позиции. Реализация использует
существующие контуры P01/P02/P03, не вводит новый Cycle и не подменяет предметные
артефакты значениями в коде.

Обычная product-активация остаётся заблокирована допуском методологии/Cases и
provider configuration. Реальный путь замены не получает встроенный fallback: если
допущенный `provider_config_ref` отсутствует, UI сообщает о недоступности операции.

## Прочитанные источники и состояние Git

- `/Users/vadim_bogachev/Downloads/UX-P03_CONTINUE_2026-10-16.txt`, rev 1.2,
  SHA-256 `a0f9156c8218eeb8d4abf828e11fe657399f5a18ffdcd4455fc08e3da609c2bb`.
- `/Users/vadim_bogachev/Downloads/UX-P03_Return_Time_Integration_2026-10-15.txt`,
  rev 1.0, SHA-256
  `c69813f2147013b706068de58375942e8d54e3210f3499423a96f818c5123c82`.
- `README.md`, `CONTRIBUTING.md`, EVC workflow, verification matrix, artifact
  recipe и review checklist.
- Change 01, source-set manifest 2026-10-01, M1 v1.4 и относящиеся к задаче
  контракты/карта реализации; CURRENT им не присваивался.
- До изменения: `main@39ffa2bdd43c002341a6630b905018d080f396ef`, P03 PR #53.
  Ветка продолжает принятые зависимости R04
  `7143c1d` и W02 `391235a05a6495bb9bcb844e09467d8483e2adf6`.

## Трассировка правила → контракт → код → проверка

| Правило rev 1.2 | Контракт/данные | Реализация | Доказательство |
|---|---|---|---|
| Heartbeat около 10 секунд, lease 120 секунд по server time | policy v1.2, presence clients | `heartbeat`, `reconcile_presence`, owner HTTP endpoint | unit, HTTP и PostgreSQL 119/120 |
| Несколько клиентов: действует последний lease, отсутствие начинается на expiry | `m7_return_presence_clients`, return event | `MAX(lease_expires_at)`, событие на точной границе | PostgreSQL multi-client regression |
| До expiry время расходуется; признанное отсутствие и системное ожидание не расходуют его | M5 time intervals | закрытие collecting на expiry, `blocking_system_wait`, защита перекрытий | PostgreSQL budget/deadline regressions |
| Только явный Continue завершает отсутствие | return state/command | stopped AS скрыт, input заблокирован, explicit Continue | frontend unit и Playwright |
| `<180` — тот же AS, `>=180` — новый AS в той же позиции | P03 policy, P02 candidate, P01 replacement | существующий continue/replace pipeline | PostgreSQL 179/180 |
| Не более трёх успешных замен позиции | route history, P03 policy | четвёртая требуемая замена закрывает collection с фактическим материалом | PostgreSQL replacement-limit regression |
| GET не создаёт AS/command/event | return read model | виртуальное состояние рассчитывается из lease | integration/read-model regression |

## Изменённые контуры

- `assessment_definitions/planning/m7_return_integration/v1`: immutable policy
  rev 1.2 и обновлённый checksum manifest.
- `Api/m7_return_integration.py`: server presence, точная фиксация absence,
  multi-client lease, лимит замен и расширенный read model.
- `Api/m5_cycle_runtime.py`: перекрывающиеся blocking intervals больше не
  возобновляют расход времени преждевременно.
- `Api/routes.py`, `Api/m7_completion_contracts.py`: owner-scoped heartbeat API.
- `web/js/screens/interview.js`, `web/styles/screens/interview.css`: независимый
  heartbeat и same-chat return card; `web/dist` пересобран.
- Unit, frontend, HTTP, PostgreSQL integration и browser regressions.

## Фактические проверки

- Python `py_compile` изменённых backend-модулей — PASS.
- `npm run lint:js` — PASS.
- `npm run build:web` — PASS.
- `node --test tests/frontend/*.test.mjs` — 18 PASS.
- `pytest tests/unit/test_m7_return_integration.py -q` — 1 PASS.
- `pytest tests/integration/test_m7_cycle_planner_db.py` на изолированной
  `agent4k_pytest` — 17 PASS.
- Целевые PostgreSQL проверки 119/120, 179/180, multi-client и четвёртой замены —
  4 PASS.
- `npm run test:backend:http` на изолированной `agent4k_pytest` — 56 PASS,
  10 deselected, одно существующее предупреждение Starlette.
- `tests/browser/auth-r03.spec.mjs` — 20 PASS; отдельный P03 сценарий — 1 PASS.
- `git diff --check` — PASS.

## Непроверенное и открытые границы

- Физические устройства и полный browser/device matrix — NOT_RUN; проверен
  автоматизированный Chromium-контур.
- Реальные LLM-вызовы — NOT_RUN и не входят в стандартный набор.
- Фактический detector/feed инфраструктурных инцидентов — NOT_RUN: таблица и
  защита от ложного absence при уже подтверждённом incident готовы, но источник
  подтверждения находится вне этой задачи.
- Ветка `scenario_ended` при незакрытых уточнениях не реализована: дополнение не
  содержит принятого решения для этого сценария.
- Product Cases/provider admission остаются блокером обычной оценки. Подключение
  source/policy и техническая реализация не означают допуск runtime-контента.

## Риски, совместимость и откат

- API расширен аддитивно; существующие клиенты и история Cycle сохраняются.
- Миграция добавляет presence/incident tables и расширяет допустимый source kind.
- Heartbeat авторизован владельцем Cycle; server timestamps не принимаются от
  клиента. Секреты и production/test данные в проверки не передавались.
- Откат: отменить этот коммит и отключить presence endpoint; уже записанные
  events/route history не удалять и не возвращать автоматически в расчёт.

## Следующий минимальный шаг

После допуска methodology/Cases и provider configuration подключить реальный
provider reference, источник подтверждённых infrastructure incidents и провести
device matrix. Вопрос `scenario_ended` вынести в отдельное решение владельца.
