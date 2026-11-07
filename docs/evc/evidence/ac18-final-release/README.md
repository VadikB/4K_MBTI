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

## Кандидат2.0.75 — локальная подготовка завершена

После отдельного решения владельца выполнен canonical ready preflight2.0.75 дважды,
consistency/release gate и45 build hashes идемпотентны. Это один bump, не два выпуска.
Согласие/границы — owner-version-decision.json; ready-result.json — фактический итог.

`BUILD_APPLICABILITY.py` сравнивает с exact paid-PATH38bf:18 runtime files unchanged,
только release literals в4 metadata файлах;45 normalized modules и их import graph
совпадают. Нормализуются только номер приложения и generated module hash в import
references, но edges дополнительно связываются с content hash того же модуля.
Это не приравнивание разных candidate/AS/payload checksum и не ослабление runtime.

После bump: frontend146/receipt66/Python runner+release24 PASS, lintPASS;
browser9 PASS/retries0/flaky0: pending/denial/retry/failure capture, CASE01/02 real
materializer→UI projections на4 widths иinitial HTML version. Явно SYNTHETIC HTTP,
без DB/LLM/пилотного admission. Старые127 browser/956 backend/108 HTTP результаты
применимы по неизменным функциональным bytes; mandatory CI проверяет новый head отдельно.
Source parent6f9d1c94, точный content release worktree привязан source/build hashes;
последующая фиксация добавляет только docs/evidence, не меняет проверенное поведение.

```sh
python3.12 docs/evc/evidence/ac18-final-release/VERIFY.py
```

Initial launcher errors сохранены: системный python3 не поддержал glob root_dir
до запуска checks; затем ошибочный worktree-local Playwright path не нашёл CLI;
следующий browser дал7PASS/2ENOENT отсутствующего worktree .venv. Выбран существующий
parent CLI и explicit project BROWSER_PYTHON; окончательный9PASS. Продуктовые код/
assertions для этого не менялись. Это ошибки местного операционного launcher, не
установленные причины исторического timeout/INCOMPLETE/PREP-DIAG-01.
Первичные неуспешные результаты не переписаны в PASS, реальный LLM не вызывался.
Raw lint stdout помещён вlint.raw.zip: исходные bytes с лишней пустой строкой
не форматируются ради git whitespace hook; распаковка восстанавливает тот же вывод.
