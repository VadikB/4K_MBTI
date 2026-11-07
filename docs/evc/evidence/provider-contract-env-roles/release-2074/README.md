# PROVIDER-ROLES-01 — кандидат2.0.74, не deploy/AC18

07.11.2026 владелец отдельно подтвердил PATCH2.0.74, push/PR/mandatory CI/review.
Main/base44802660/2.0.73; source1666f921, handoff19bc6ad0. Merge/deploy, программа,
серверный `.env` и платный AC18 исключены. Этот receipt записан **до push**; точный
head/PR и последующее состояние CI фиксируются в PR, не задним числом в XML.

Штатный `PYTHON_DOTENV_DISABLED=1 npm run ready:prepare -- --candidate 2.0.74`
и повтор — PASS/exit0; второй bump отсутствует.49 hashes (4 metadata +45 dist)
совпали до/после повтора. `check_release_version.py --base-ref origin/main` PASS.
Build очистил только собственный dist этого нового worktree и воспроизвёл assets;
ничего не удалялось в чужой ветке/серверном checkout.

Новые primary JUnit:

- `frontend.xml`:145 PASS; Node spec + junit reporters.
- `receipt.xml`:66 PASS; те же source validators/admission/lineage/time guards.
- `python.xml`:116 PASS; release/CI/published source/model ownership/harness/stand.
- Lint exit0; scoped functional diff пуст; `git diff --check` PASS.

Node25 JUnit содержит testcase непосредственно в testsuites. VERIFY считает именно
testcase (в том числе pytest116), требует ненулевое число, ноль failure/error/skip,
проверяет bytes/hash файлов и существующий CHECK18/4. Это не замена обязательного CI.
Предшествующие956 backend/108 HTTP переиспользуются только для неизменных source bytes
1666f921; новый candidate metadata отдельно проверен указанными release regressions.

Команды из корня checkout (без `.env`, DB и провайдера):

```sh
npm run lint:js
node --test tests/frontend/*.test.mjs
node --test tests/unit/test_assessment_preparation_receipt.mjs tests/unit/test_assessment_receipt_file.mjs
PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 .venv/bin/python -m pytest -q \
 tests/unit/test_release_version.py tests/unit/test_ci_verification_workflows.py \
 tests/unit/test_path_start_release_source.py tests/unit/test_provider_model_ownership.py \
 tests/unit/test_deepseek_provider_contract.py tests/unit/test_deepseek_capacity.py \
 tests/unit/test_assessment_first_case.py tests/unit/test_test_stand.py
python3 docs/evc/evidence/provider-contract-env-roles/release-2074/VERIFY.py
```

Для Node сохранены `--test-reporter=spec --test-reporter-destination=stdout` и
`--test-reporter=junit --test-reporter-destination=<this>/<name>.xml`; для pytest
`--junitxml=<this>/python.xml`. Node25 MODULE_TYPELESS_PACKAGE_JSON warning и прежний
Starlette/httpx warning не исправлялись несвязанной сменой зависимостей. CI Node22
и mandatory PostgreSQL/browser на отдельной БД остаются отдельными проверками.

Проверки не подтверждают provider auth/качество AS, human review, методологический
допуск, schema/data sync или real PATH. Provider manifest1.0.0 и published snapshots
не менялись. Исторический PREP-DIAG-01 UNKNOWN; Q-DRAFT causal identity NOT_PROVEN.
