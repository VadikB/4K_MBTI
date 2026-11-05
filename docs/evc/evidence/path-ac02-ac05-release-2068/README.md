# PATH-AC02/05 — release candidate 2.0.68

База `bb3b5cb34696af8a8a2bdaa1999dd8a795786085` / 2.0.67; рабочая реализация
`ffca29c22050c08c9673662ef7763d01a47cabdd`. Ветка
`codex/path-ac02-ac05-coverage`; финальный head определяется Git/PR и пакетом
передачи после commit. [Решение/границы](../../tasks/path-ac02-ac05-release-2068.md).
Только PATCH/PR/CI/review, без merge/deploy, рабочей БД, активации и платного LLM.

Все команды запущены из корня worktree с очищенным environment:
`env -i PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin LANG=en_US.UTF-8`.
`.env` отсутствует и не читается. Сырые stdout сохранены без потерь в `.txt.gz`.

| Команда | Результат | Первичное evidence |
| --- | --- | --- |
| `npm run ready:prepare -- --candidate 2.0.68` дважды | PASS; fresh main bb3b5cb, 45 assets; четыре metadata + assets неизменны при повторе | `preflight.txt.gz`, `preflight-repeat.txt.gz` |
| `npm run lint:js` | PASS, exit0 | `lint.txt.gz` |
| `node --test tests/frontend/*.test.mjs` | 140 PASS, exit0 | `frontend.txt.gz` |
| `.venv/bin/python -m pytest -q tests/unit/test_ci_verification_workflows.py tests/unit/test_release_version.py` | 22 PASS, exit0 | `release-tests.txt.gz` |
| `node node_modules/@playwright/test/cli.js test tests/browser/auth-r03.spec.mjs` | 115 PASS, 0 skipped/flaky/unexpected, retries0; 142.242 s, exit0 | `browser.json`, `browser.txt.gz` |
| `shasum -a 256 -c docs/evc/evidence/path-ac02-ac05-release-2068/code-sha256.txt` | 54/54 PASS | `code-sha256.txt` |

Для Python добавлены только test sentinel: `PYTHONPATH=.`,
`PYTHONDONTWRITEBYTECODE=1`, `AGENT4K_ISOLATED_STAND=1`,
`AGENT4K_STAND_MARKER=stand-10.2:release2068`, `DB_HOST=127.0.0.1`,
`DB_PORT=9`, `DB_NAME=product4k_pytest_release2068`, `DB_USER=synthetic`,
`DB_POOL_MIN_SIZE=0`, `LOG_TO_FILE=false`, `AUDIT_LOGS_TO_DB=false`.
Рабочая БД не используется, новый test container не создавался.

`ac05-unknown-{1440,320,390,768}.png` — текущие responsive browser снимки.
`desktop-status-list.png` / `mobile-status-list.png` — новые снимки старого
теста; исторические файлы adm-status-01 после копирования восстановлены из
ffca29c. Синтетический HTTP маркирован в tests; не реальное выполнение на test.

Прежние clean-before AC02=3 PASS / AC05=2 FAIL, targeted17 PASS, HTTP25 и real
PG2, очистка owned контейнера, первый full114/1 UNKNOWN auth и control115 PASS
сохранены в [рабочем evidence](../path-ac02-ac05/README.md). Их manifests относятся
только к immutable ffca29c, не к новому dist/STATE. Исторический auth FAIL не
объявляется исправленным. PREP-DIAG-01 UNKNOWN и реальный PATH на e63/2.0.66
остаются отдельными, новый платный запуск не выполнялся.

Локальные ссылки, diff и source equality проверяются до commit. Новый mandatory
CI перед review — в PR точного head/base. Human review НЕ заменён self-review;
main и последнее подтверждённое test остаются bb3b5cb / 2.0.67.
