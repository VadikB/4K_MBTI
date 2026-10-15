# UX-P03 — Return Time Integration

Дата: 15.10.2026. Ветка: `codex/ux-p03-return-time-integration`.

## Результат и границы

Первый этап: QA-only интеграционный адаптер P03 поверх контролируемого события
отсутствия, P02 candidate и P01 replacement. Production activation, UI/W02 copy и
полная сквозная приёмка ожидают D08/D09, методологический контракт и допущенные Cases.

## Источники и решения

- `UX-P03_Return_Time_Integration_2026-10-15.txt`, rev 1.0 — постановка.
- `README.md`, `CONTRIBUTING.md`, EVC workflow/matrix/artifact recipe.
- Change 01 и manifest 2026-10-01; M1 v1.4, M7 v1.3.
- `docs/architecture/m7-completion-contract.md`, P01 и P02 contracts.
- Base: P02 `86080b201c0cc3063de0fae21629a6009b28ac8d`, который зависит от
  `main@909979043a0aecc6ebfee34e1cf1092121cc8d14`.

Стоп-условия: D08/D09 и неприменимый пока product content contract блокируют только
production event ingestion/activation и UI-обещание полной механики. Постановка явно
разрешает контролируемый fixture adapter; предметные решения не добавлены.

## Реализация

- `Api/m7_return_integration.py`: read model, controlled event seam и explicit Continue.
- Draft QA policy с границей 180 секунд вне кода.
- Аддитивные event/command tables и запрет Turn во время blocking wait.
- Owner GET/POST; GET не мутирует состояние.
- Регрессии 179/180, replay, deadline/budget, P02→P01→presentation и route history.

## Проверки

- `python -m py_compile` для изменённых Python-модулей — PASS.
- `pytest tests/unit/test_m7_return_integration.py tests/e2e/test_m5_runtime_http.py` —
  8 PASS, одно существующее предупреждение Starlette.
- P03 PostgreSQL integration (изолированная `agent4k_pytest`) — 2 PASS.
- `pytest tests/integration/test_m7_cycle_planner_db.py` — 15 PASS.
- `pytest tests/e2e` — 65 PASS, одно существующее предупреждение Starlette.
- `npm run test:backend` — 411 PASS / 13 FAIL: известный baseline M6
  (`INPUT_NOT_READY`, `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`), вне diff P03.
- `npm run test:backend:integration` — 78 PASS / 37 FAIL: тот же известный
  M6/provider baseline; все добавленные P03 integration-проверки PASS.

## Непроверенное

- D08: реальный server presence/event source и multi-client semantics — NOT_RUN/blocked.
- D09: retry ceiling, недостаток времени, окончательная ошибка и scenario-ended branch — NOT_RUN/blocked.
- Product Cases/provider, UI/W02 и device/browser matrix — NOT_RUN; первый этап их не включает.

## Риски и откат

- Config: draft QA policy, assessment activation отсутствует.
- Schema: две аддитивные таблицы; старые Cycles без события получают dependency state.
- Security: owner scope; fixture event разрешён только `qa`; публичного ingestion API нет.
- Откат: отключить GET/POST и adapter; историю replacement/AS не удалять и не возвращать
  автоматически в расчёт.

## Следующий минимальный шаг

Владельцы продукта/методологии закрывают D08/D09 и публикуют применимые policy/Case
contracts; затем отдельный PR подключает production event source, UI и полный E2E.

## Открытые вопросы

D08/D09 остаются явными блокерами полного UX-P03; первый этап их не закрывает.
