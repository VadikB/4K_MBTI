# P4K-PATH-GUARD-01 — проверки и передача 07

Base `e8773ca80b9e3089a0faec16e9722680d126d8bb`; tested code/release candidate `8523340a036fe06bc7f61c8e227b273fd4c550d2`; branch `codex/p4k-path-browser-guard-01`, версия 2.1.10. Последующий документационный commit не меняет проверенный код. Актуальный PR head сверяется отдельно при публикации.

## Проверки кандидата

| Команда/проверка | Результат |
| --- | --- |
| `node --test tests/browser/fixtures/path-action-budget.test.mjs` | PASS, 4 |
| `node_modules/.bin/playwright test tests/browser/path-action-budget.spec.mjs tests/browser/path-viewports.spec.mjs --workers=1 --retries=0 --reporter=line` | PASS, 4 native Chromium, фиксированный HTML, без auth/DB/LLM |
| Тот же native smoke (1 test) через Python process group wrapper `communicate(timeout=30)`, TERM/KILL окно до 30 с | PASS exit0 за 2.8 с; stop не понадобился |
| `.venv/bin/python -m pytest -q tests/unit/test_assessment_first_case.py tests/unit/test_path_action_budget_summary.py tests/unit/test_assessment_run_summary.py tests/unit/test_provider_model_ownership.py` | PASS, 80 |
| `npm run build:web` | PASS |
| `npm run bump:version -- patch --dry-run` | PASS; предложен 2.1.9 → 2.1.10, затем номер подтверждён владельцем |
| `npm run ready:prepare -- --candidate 2.1.10` | PASS после прямого подтверждения владельца; `origin/main` актуален, release 2.1.10, `web/dist` пересобран |
| `git diff --check` | PASS |
| Исторический `summarize_runs(path, 0, controlled_provider=True/False)` | `PASS TECH` / `FAIL FIRST_CASE_EVIDENCE_INVALID`; старый action-profile остаётся FAIL |
| `verifyFirstCase` на сохранённом controlled receipt v1.2, in-memory mutations | positive PASS; refs/admission/owner `REJECTED_AS_EXPECTED`; без записи в старый worktree |
| `npm run test:backend` | PASS, 1116 на release-кандидате 2.1.10 с локальным доступом к `ps`. Первоначальный sandbox run: 1102 PASS/11 FAIL, 9 из-за запрета `ps`, 2 мока исправлены |
| `npm run lint:js` | PASS |
| `node --test tests/frontend/*.test.mjs` | PASS, 332 |
| Новый полный PATH | NOT_RUN по заданию; один запуск Final_Resume после выпуска |
| Обязательный CI `frontend`, `pytest`, `full-verification` | NOT_RUN до PR |

## Команда для будущего 07

Из отдельного owned run после merge/deploy, точного TEST SHA и согласования ресурсов. Не запускать её как часть этого PR:

```sh
P4K_FULL_PATH=1 P4K_CONTROLLED_PROVIDER=1 P4K_PROGRAM_SOURCE=published-pilot \
  P4K_PATH_BOUNDED=1 P4K_PATH_ACTION_LIMIT=120 P4K_PATH_VISUAL_LIMIT=40 \
  STAND_ADMIN_URL="$OWNED_TEST_DATABASE_ADMIN_URL" \
  .venv/bin/python scripts/assessment_first_case.py \
  --controlled-provider --program-source published-pilot \
  --program-receipt /Users/vadim_bogachev/Developer/4K/worktrees/p4k-remain-07/docs/evc/evidence/pilot-program-publication-execution/published-release-source.json \
  --program-receipt-sha256 09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b \
  --program-version 1.2 \
  --path-action-limit 120 --path-visual-limit 40 \
  --directory "$OWNED_EVIDENCE_DIRECTORY" --port "$OWNED_FREE_PORT" \
  --run-deadline-seconds 1200 --no-progress-seconds 900
```

`P4K_COMPLETION_PROFILE` и `P4K_STOP_AFTER_FIRST_AS` не задаются. Команда создаёт owned test DB только после проверки лимитов и источника. Контролируемый результат обозначается `PASS TECH`, real-provider проверка остаётся строгой. Для offline перепроверки без сети/БД: `.venv/bin/python scripts/assessment_first_case.py --summarize-only --controlled-provider --directory "$OWNED_EVIDENCE_DIRECTORY"`.
Указанный источник версии 1.2 повторно проверен по исходным байтам SHA-256 15.11; перед фактическим запуском 07 владелец сверяет его с закреплённым TEST и выбирает новые отдельные `OWNED_*` ресурсы. `P4K_FULL_PATH`, `P4K_CONTROLLED_PROVIDER` и `P4K_PROGRAM_SOURCE` передаются явно, а runner проверяет/повторяет их.

## Остаток

PR/head/CI заполнить после разрешённой публикации; локальный release gate PASS. Ранее сохранённые 6 negative controls: `worktrees/p4k-remain-07/docs/evc/tasks/p4k-remain-07/receipts/controlled-validator-controls.json`; действуют лишь для неизменённой валидации admission/refs/owner.

## Текст PR

**P4K-PATH-GUARD-01: конечный browser budget до первой AS и controlled summary (2.1.10)**

PATH29 получает один общий guard до создания owned DB и первых browser-действий. Сценарные и визуальные операции резервируются до Playwright delegate; превышение сохраняется в безопасной квитанции и делает итог FAIL. Bounded first-case использует один основной viewport и минимальное доказательство первой AS, обычные визуальные проверки сохраняют прежний default. Runner явно выбирает controlled validation до запуска; сохранённый controlled receipt даёт `PASS TECH`, real-default остаётся строгим.

Проверки: локальный backend/frontend/lint/build, unit и native browser smoke, historical controlled/real и отрицательные refs/admission/owner; точные команды выше. Полный новый PATH и real LLM не запускались по границе задачи. CI `frontend`, `pytest`, `full-verification` требуется на точном head до merge. Риски: bounded профиль может завершиться диагностическим FAIL раньше функционального результата при исчерпании лимита; owned state при неизвестном terminal export сохраняется. Откат: revert squash commit, миграций и публикации артефактов нет. После merge/deploy TEST передать 07 команду выше и SHA; новый полный PATH исполняется отдельно один раз.
