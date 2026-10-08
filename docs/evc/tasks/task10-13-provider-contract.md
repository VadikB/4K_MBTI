# Task-10-13 — продуктовый контракт DeepSeek без внешних вызовов

## Результат и границы

На базе `8c7c52b8cd1c799bf771a148d6009a81f7a7b9f7` создан проверяемый product gateway
contract. Реализация фиксирует `deepseek-flash`, non-thinking и declared response
format, сохраняет безопасную trace, usage и attempts, отклоняет empty/truncated
ответы и предоставляет preflight без секрета. Реальных AI-вызовов, общей SQL,
deploy/push/merge не было: `REAL_PROVIDER_NOT_RUN`, `SEMANTIC_NOT_VERIFIED`.

Унаследованный из 10.12 стоп-фактор полного маршрута сохраняется: synthetic/fixture
catalog разрешён только для `qa`, а orchestration выбирает `assessment`. Поэтому P8
доказан на уровне общего gateway и component operations, но будущий full-path run до
M6 не объявлен готовым и guard не ослаблялся.

## Критерии

- P1 PASS — captured request включает model/thinking/response_format и совпадает с operation.
- P2 PASS — M5/M6/M7 adapters используют `_call_with_trace` общего product gateway.
- P3 PASS — transport/empty/invalid JSON/schema/ref/truncation остаются technical failure.
- P4 PASS — safe trace не содержит Authorization, хранит usage и все attempts.
- P5/P10 PASS — provider operation входит в frozen snapshot; новые contract/config не меняют сохранённый объект.
- P6 PASS — direct legacy calls по умолчанию остаются `text`; JSON задаётся operation.
- P7/P9 PASS — future manifest привязан к implementation SHA и runner/input contracts, с единым budget.
- P8 BLOCKED (full-path), PASS (component) — product gateway используется; M5 admission blocker 10.12 сохранён.
- P11 PASS — plan/dry-run не вызывает сеть и не меняет SQL.

## Источники и решения

Прочитаны `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, EVC workflow/matrix/artifact
recipe, Change 01, SourceSet 2026-10-01, ADR-002, Registry, контракты и evidence
10.11/10.12, M5–M7 prompt manifests/consumers/tests. Пакет r2 проверен: SHA-256
`c2b2f2f7ec6a1b74217d7fc51a266517d2dead6ff59b2623df3c71c67a462111`, CRC PASS.
Официальные DeepSeek docs сверены 08.10.2026: alias `deepseek-flash`, явный thinking,
JSON Output и `finish_reason=length`. Содержательные prompts не менялись.

## Изменения и совместимость

Добавлены versioned provider manifest/loader, gateway payload/validation/preflight,
safe failures и no-network tests. Default example/config переведён с legacy
`deepseek-chat` на `deepseek-flash`. Public `chat`/`chat_with_trace` обратно совместимы:
новые параметры optional; default response format — `text`. Rollback описан в artifact.

## Проверки

- `py_compile` изменённых Python-файлов — PASS, exit 0.
- `pytest -m "not integration and not e2e and not llm" -q` — PASS, 376 passed,
  143 deselected, 14.66 s; внешняя сеть не использовалась.
- `git diff --check` — PASS.
- CI/integration/e2e/llm — NOT_RUN: CI требует PR; SQL не менялась; реальные LLM
  прямо запрещены пакетом. Обязательный CI остаётся условием merge.

## Передача

Branch `codex/task10-13-provider-contract`; implementation commit
`2673db303afda6e7d6958b819e338b41850d500e`. Evidence находится в
`docs/evc/tasks/artifacts/task10-13/`. Откат — revert commits задачи и возврат test
config; сохранённые snapshots не переписывать. Следующие задачи не запускались.
