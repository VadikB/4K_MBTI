# Воспроизводимые команды

```bash
python -m pytest -m 'not integration and not llm' -q
TEST_DATABASE_URL=postgresql://pytest:pytest-local@127.0.0.1:55439/p4k_pers_pytest \
STAND_ADMIN_URL=postgresql://pytest:pytest-local@127.0.0.1:55439/postgres \
  python -m pytest -m integration --run-integration -q
RUN_REAL_CYCLE_LLM=1 \
P4K_FULL_CYCLE_EVIDENCE_PATH=docs/evc/evidence/pers-functional-personalization/full-cycle-real-final.json \
TEST_DATABASE_URL=postgresql://pytest:pytest-local@127.0.0.1:55439/p4k_pers_pytest \
  python -m pytest -m 'integration and llm' --run-integration \
  tests/llm/test_m10_real_cycle_db.py -q
python scripts/summarize_functional_personalization_v2.py
python scripts/verify_functional_personalization_transformations.py
python scripts/run_functional_scenario_matrix.py
STAND_ADMIN_URL=postgresql://pytest:pytest-local@127.0.0.1:55439/postgres \
BROWSER_PYTHON=../../.venv/bin/python npx playwright test --workers=1
git diff --check
```

Значения URL приведены только для изолированной pytest-БД. Ключи provider и иные
секреты в команды и архив не включаются.
