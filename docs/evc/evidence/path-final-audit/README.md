# PATH-FINAL-AUDIT-01 — первичные результаты

[Матрица18 AC и ограничения](../../reports/path-final-audit-2068.md),
[задача/план](../../tasks/path-final-audit.md),
[PREP](../../tasks/prep-diag-01-review.md),
[AUTH](../../tasks/path-auth-diagnostic.md).
Product base/main/test946a46c /2.0.68; новый report commit — в Git/пакете, не новый deploy.

| Проверка | Фактический результат / первичное evidence |
| --- | --- |
| Existing `docs/evc/evidence/pilot-1.2-path/CHECK.py` | PASS_OFFLINE_ACTUAL_PATH,34 primary hashes/11 runtime objects, реальный Node validator/summary; `offline-path-check.json` и stderr gzip;0 sockets/DB/new provider |
| `pytest -q tests/unit/test_assessment_first_case.py` |11 PASS,0.89s,exit0; `prep-unit.txt.gz` |
| `pytest -q tests/unit/test_path_final_audit_evidence.py tests/unit/test_m4_personalized_profile.py` |17 PASS,0.37s,exit0;12 checker cases (valid +11 tamper negatives) и5 M4 identity contracts; `audit-unit.txt.gz` |
| Explicit auth diagnostic below | **1 FAIL**,6.4s,exit1,retries0; `auth-diagnostic-results.json`, stdout/context gzip, before/after PNG; это ожидаемое обнаружение продукта, не PASS auth |
| node --check на новом diagnostic/config | PASS; продукт/standard browser config не менялись |
| Default `playwright test tests/browser/auth-recovery-race.diagnostic.mjs --list` | Expected exit1/No tests found/0 tests: negative diagnostic исключён matcher; `default-suite-exclusion.txt.gz` |
| `python -O CHECK.py` | Expected exit1/OPTIMIZED_PYTHON_FORBIDDEN; `check-optimized.txt.gz` |
| Source identity e63→946 |11 recorded runner files byte-equal, Api/scripts/definitions diff пустой; `source-identities.json` |
| Closed release2.0.68 | REUSED: `release2068.json`, server-readback и `release2068-closure.txt.gz`; не новый live server check |

Все новые commands — sterile env:
`env -i PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin LANG=en_US.UTF-8`.
Python: `PYTHONDONTWRITEBYTECODE=1`; для pytest также `PYTHONPATH=.`,
`AGENT4K_ISOLATED_STAND=1`, `AGENT4K_STAND_MARKER=stand-10.2:path-final-audit`,
`DB_HOST=127.0.0.1`, `DB_PORT=9`, `DB_NAME=product4k_pytest_path_final_audit`,
`DB_USER=synthetic`, `DB_POOL_MIN_SIZE=0`, `LOG_TO_FILE=false`, `AUDIT_LOGS_TO_DB=false`.
`.env` отсутствует, БД/контейнеры не создавались, штатный runner не запускался.

```sh
.venv/bin/python docs/evc/evidence/pilot-1.2-path/CHECK.py
.venv/bin/python -m pytest -q tests/unit/test_assessment_first_case.py
.venv/bin/python -m pytest -q tests/unit/test_path_final_audit_evidence.py tests/unit/test_m4_personalized_profile.py
node node_modules/@playwright/test/cli.js test --config docs/evc/evidence/path-final-audit/auth-diagnostic.config.mjs
.venv/bin/python docs/evc/evidence/path-final-audit/CHECK.py
```

Auth diagnostic — opt-in `.diagnostic.mjs`, default `*.spec.mjs` его не включает.
Нужны установленные package-lock dependencies/Chromium, свободный localhost18765.
Настоящие HTML/entry/dist, controlled HTTP responses и chat asset gate; никакой
подмены fetch/DOM/таймеров/admission. Собственные synthetic credentials не уходят
наружу. Трассы/cookies/password storage не экспортируются. Reporter config пишет
raw JSON в собственную ignored `.test-stand/` относительно config directory;
для evidence он побайтово скопирован в `auth-diagnostic-results.json`.

Финальный CHECK проверяет целостность записанного evidence и ограничения, не
означает auth/product/full PATH PASS. Его unit tamper negatives запрещают ложный
PASS диагностики, присвоение old run текущему SHA, изобретение причин PREP/auth,
подмену deployment и снятие proof gaps. Python `-O` запрещён.

FILES.json содержит byte hashes primary evidence/источников/отчётов для этого
immutable report snapshot. Исторические manifests прежних рабочих commits не
переизданы и не проверяются на изменённом STATE. Пакет включает применимые старые
primary файлы, новые JSON/PNG/gzip, source/test, diff и Git bundle; см. HANDOFF пакета.
Это локальный результат: новый CI/PR/push/версия/merge/deploy/активация/LLM отсутствуют.

Первый staged diff-check отклонил whitespace в скопированном AX snapshot закрытия
release. Вывод сохранён в `first-staged-diff.txt.gz`; snapshot сжат lossless gzip,
исходные байты не нормализованы, правила diff не ослаблены. Исходный release пакет
не менялся. Повторный staged check выполняется после обновления inventory.
