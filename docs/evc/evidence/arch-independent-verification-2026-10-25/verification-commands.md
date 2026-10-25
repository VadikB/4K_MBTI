# Воспроизведение

Проверяемый product commit: `2e4aa4000799e329e095a68ccd2d114e656267d3`.
Команды не используют production/developer DB; integration разрешён только с
изолированной БД, содержащей `test` или `pytest` в имени.

## Безопасный локальный минимум пакета

```bash
jq empty docs/evc/evidence/arch-independent-verification-2026-10-25/*.json
shasum -a 256 -c docs/evc/evidence/arch-independent-verification-2026-10-25/MANIFEST.sha256
git diff --check origin/main...HEAD
```

## Адресные проверки продукта

```bash
.venv/bin/python -m pytest \
  tests/unit/test_product_cycle_preparation_projection.py \
  tests/unit/test_product_cycle_preparation_fencing.py \
  tests/unit/test_cycle_execution_manifest.py \
  tests/unit/test_m8_descriptive_report.py \
  tests/unit/test_arch_a06_acceptance_matrix.py

.venv/bin/python -m pytest -m e2e tests/e2e/test_m5_runtime_http.py

TEST_DATABASE_URL=postgresql://pytest:pytest-local@127.0.0.1:55437/a_b_verification_pytest \
  .venv/bin/python -m pytest -m integration --run-integration \
  tests/integration/test_m10_product_path_db.py \
  tests/integration/test_m7_parameter_resolution_db.py \
  tests/integration/test_f05_runtime_matrix_db.py

node --test tests/frontend/*.test.mjs
npm run build:web
```

## Зафиксированные фактические результаты

- Проверка самого пакета: JSON/path/SHA-256/`git diff --check` — PASS;
  адресные unit-регрессии — `33 passed`. Запись `.pytest_cache` была запрещена
  режимом управляемого worktree, тесты завершились с exit `0`.
- PR #112 head `5c447cb...`: backend non-integration `573 passed`; HTTP/e2e
  `69 passed`; PostgreSQL M10/A03 `16 passed`; frontend build PASS.
- Итоговый merge `2e4aa400...`: workflow `40189333177`, jobs `frontend`,
  `pytest`, `deploy-test` — success.
- Test readback: `2.0.25`.
- Результаты остальных ограниченных PR сохранены в соответствующих
  `docs/evc/tasks/arch-*.md`/`fix-*.md` и `ci-and-releases.json`.

Полный повтор integration в этой docs-only задаче не требуется матрицей и не
выдаётся за новый запуск. Real-provider, AI tester человека, методологическая
приёмка и Reliability этой командой не выполняются.
