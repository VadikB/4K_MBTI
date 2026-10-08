# Task-10-15 — фиксация headless acceptance

## Итог

`TECHNICAL_ACCEPTANCE_NOT_ESTABLISHED`. Candidate `107afe320b1dec5fe383b5f79361a3d5482d448f`
содержит принятые commits 10.11–10.14 и проходит применимые backend/HTTP/frontend
наборы. Полный API M4–M8 и C1/C2 ×3 не выполнены: accepted 10.11 policy разрешает
synthetic/fixture QA evidence только для `qa`, а product orchestration создаёт Cycle
с `usage_scope=assessment`. Harness не достигает AS. Guard не ослаблялся, human
origin не подделывался, производные Evidence/IA/Results не вставлялись вручную.

## Критерии

Полная матрица H1–H12 находится в `artifacts/task10-15/acceptance-matrix.json`.
H7 PASS; H1 backend/HTTP/frontend PASS; component H5/H12 PASS. H2/H3/H10/H11
BLOCKED. H4/H6/H9 PARTIAL. H8 NOT_RUN. Итог не является `PRODUCT_READY`, GC,
`SEMANTIC_PASS` или подтверждением нового UX.

## Проверки и первый FAIL

- backend: `378 passed, 144 deselected`, 15.36 s;
- HTTP: `46 passed`, 24.51 s;
- ESLint/build: PASS;
- integration first run: FAIL в двух clean-bootstrap tests из-за неверного имени
  maintenance DB (`agent4k_pytest_1015` не входит в allowlist). Создана корректная
  owned maintenance DB `agent4k_pytest`; повтор запущен, но полный terminal summary
  не получен, поэтому integration не объявлен PASS;
- browser C1/C2: NOT_RUN/BLOCKED до минимального решения ниже;
- real provider: NOT_RUN.

## Минимальное решение владельца

Нужен отдельный явно разрешённый QA orchestration mode: он должен создавать
catalog-bound Cycle в owned test scope, сохранять `qa` происхождение и проходить
те же M5 admission guards. Расширять ordinary `assessment` policy или маркировать
fixture как human нельзя. После решения повторить full integration, API fullpath и
C1/C2 ×3 с `120/240 s`, retries=0, сохранив шесть настоящих traces до teardown.

## Источники, ветка и границы

Пакет r2 SHA-256 `6ac348c91f12d0aea7732ec597a12ccbe06b984b8ed2f215f627cc5641430e8c`,
CRC PASS. Прочитаны AGENTS/EVC, reports/contracts/evidence 10.11–10.14, применимые
M6–M8 и текущие runners. P4-01/новый UX в candidate отсутствует и не проверялся.
Branch `codex/task10-15-headless-acceptance`, base `107afe3`. Push/merge/deploy,
общая SQL, реальные данные и AI-вызовы не выполнялись. Откат — удалить только
фиксационный commit; runtime candidate не изменялся.
