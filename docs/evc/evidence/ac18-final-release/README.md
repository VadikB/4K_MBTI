# AC18-FINAL-REL-01 — evidence подготовки

Начальная база339aff9 /2.0.74, exact HEAD38bf8244. Статус/границы —
[карточка](../../tasks/ac18-final-release.md).

- preflight-before-version-decision.json: canonical ready preflight exit2,
  ожидает отдельного решения PATCH2.0.75, файлы версии не менялись.
- targeted-before-bump.xml:24 PASS, без DB/сети/LLM, на том же runtime HEAD38bf:
  `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 PYTHONPATH=. <project-venv>/python
  -m pytest -q tests/unit/test_release_version.py tests/unit/test_assessment_first_case.py`.
- Offline primary64 files и10 новых локальных doc links проверены PASS;
  `git diff --check` PASS. Платный branch PATH не повторялся.

Это не PASS release gate, нового CI или deployed acceptance; эти этапы ещё ожидают
своих условий. Полный runner trace находится в соседнем ac18-branch38-path.
