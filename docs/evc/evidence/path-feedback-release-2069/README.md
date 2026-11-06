# PATH-FEEDBACK-R1 — первичное evidence кандидата 2.0.69

База main `946a46cb71e5ca5cc99778f036807d6c193188dc` /2.0.68; неизменённая
реализация AUTH/R10 `c59b024ebfae98790e545eae16d043a2280b9384`.
Release-ветка `codex/path-feedback-2069`; финальный SHA/tree — в Git/PR и пакете
передачи после commit. [Допуск](../../tasks/path-feedback-release-2069.md),
[отчёт](../../reports/path-feedback-release-2069.md), [identity](code-identity.json).

Все команды из корня release worktree; Node25.5.0, Python3.12.13,
Playwright1.63.0. Node/browser в `env -i PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
HOME=/Users/vadim_bogachev` (исходный HOME только для cache браузера).
Для Python дополнительно `PYTHON_DOTENV_DISABLED=1 PYTHONPATH=.
PYTHONDONTWRITEBYTECODE=1 DB_HOST=127.0.0.1 DB_PORT=1
DB_NAME=product4k_pytest_release2069 DB_USER=synthetic DB_POOL_MIN_SIZE=0
LOG_TO_FILE=false AUDIT_LOGS_TO_DB=false`. Бинарник Python общей root .venv;
.env отсутствует и не читается, URL рабочей БД/реальные keys не передавались.
Browser HTTP fixtures слушают только localhost, PostgreSQL/контейнер не создавались.

| Команда | Факт | Primary evidence |
| --- | --- | --- |
| `npm run ready:prepare -- --candidate 2.0.69` дважды | exit0/PASS, fresh main946a46c,4 metadata/45 assets identical | raw/preflight.txt.gz, preflight-repeat.txt.gz, idempotency-check.txt |
| `npm run lint:js` | exit0/PASS | raw/lint.txt.gz |
| `node --test tests/frontend/*.test.mjs` | exit0/145 PASS | raw/frontend.txt.gz |
| Python `-m pytest -q tests/unit/test_ci_verification_workflows.py tests/unit/test_release_version.py` | exit0/22 PASS | raw/release-ci-tests.txt.gz |
| Python `-m pytest -m 'not integration and not e2e and not llm'` | exit0/920 PASS,353 deselected,123.20s | raw/backend.txt.gz |
| Python `-m pytest -m e2e tests/e2e` | exit0/108 PASS,12 deselected,44.53s | raw/http.txt.gz |
| Playwright `auth-r03.spec.mjs auth-recovery.spec.mjs program-connection-feedback.spec.mjs` | exit0/129 PASS,230.598s,retry0/skip0/flaky0 | browser.json, raw/browser.txt.gz, browser-outputs/ |
| `shasum -a 256 -c …/release-idempotency.sha256` |49/49 PASS | release-idempotency.sha256 |
| source equality/diff/links/offline CHECK | PASS до commit; recorded results, не fresh execution | raw/source-equality.txt, FILES.json, CHECK.mjs |

Browser: `node node_modules/@playwright/test/cli.js test tests/browser/auth-r03.spec.mjs
tests/browser/auth-recovery.spec.mjs tests/browser/program-connection-feedback.spec.mjs
--trace retain-on-failure --global-timeout 420000 --workers 1 --retries 0
--output .test-stand/release-browser-output`. Таймауты/assertions не ослаблены.
115 прежних +4 AUTH +10 R10; настоящий UI/entry/dist с явно synthetic HTTP,
не product-method/DOM/fetch/timer замены и не реальная авторизация/DB/LLM.
Снимки screenshots/ — новые копии исторического ADM теста; старые PNG восстановлены
изc59 после копирования. Browser-outputs содержит остальные снимки текущего прогона.
Одна известная Starlette/httpx deprecation warning в каждом Python-наборе не FAIL.

`FILES.json` — SHA256 текущих выбранных sources, assets, docs и первичных результатов;
`node docs/evc/evidence/path-feedback-release-2069/CHECK.mjs` проверяет их и записанные
результаты offline, не запускает тесты, БД, provider или network.
Старые manifests170/183/76/209 не изменены и действуют только на immutable commits.
Их отрицательные evidence остаются; CHECK209 на восстановленном c59 снова PASS.

Штатный CI frontend/pytest/full-verification нового exact head/base ожидается в PR;
старый main CI не заменяет его. Human review NOT_DONE, merge/deploy запрещены.
Main и последнее подтверждённое test946a46c/2.0.68; свежий live readback NOT_RUN.
Новый real/final-SHA/post-deploy PATH NOT_RUN; real LLM0, рабочая БД не затронута.
PREP-DIAG-01 UNKNOWN, auth114/1 NOT_ESTABLISHED и старые timeout UNKNOWN отдельно;
исправленные AUTH/R10 defects не объявляются их первопричиной. Baseline не назначен.
