# PROVIDER-ROLES-01: первичные бесплатные проверки

База44802660/2.0.73. Решение владельца и реализация:
[карточка](../../tasks/provider-contract-env-roles.md). Этот каталог — локальные
evidence, не публикация артефакта/программы и не новый real-provider AC18.

- `red.zip` → точный `red.xml`: до реализации15 units,13 FAIL/2 PASS. Часть первичных machine assertions
  также затронута запретом socket bind в sandbox; в окончательных ownership units
  port probe явно подставлен. Не интерпретировать13 failures как13 продуктовых ошибок.
- `targeted.xml`:52 PASS,0 skip/error/fail.
- `backend.xml`:956 PASS,354 deselected по стандартному backend marker expression.
- `http.xml`:108 PASS,12 deselected. Существующие HTTP fixtures, не actual PostgreSQL.
- `result.json`: source hashes, числа из JUnit, manifest identity, границы и
  дополнительный offline readback с synthetic legacy model env. Значения credentials
  и старой переменной модели в readback отсутствуют.
- `CHECK.py`: стандартная библиотека; перепроверяет18 хешей исходных файлов/evidence
  и все четыре JUnit record. Не читает `.env`, не использует сеть/БД/LLM.

Из любого каталога:

```sh
python3 /absolute/checkout/docs/evc/evidence/provider-contract-env-roles/CHECK.py
```

Команды выполнены из корня нового worktree; общий Python3.12.13 — существующий
`/Users/vadim_bogachev/Developer/4K/.venv/bin/python`, без установки зависимостей.
Везде `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0`:

```sh
/absolute/python -m pytest -q tests/unit/test_provider_model_ownership.py
/absolute/python -m pytest -q tests/unit/test_provider_model_ownership.py \
  tests/unit/test_deepseek_provider_contract.py tests/unit/test_deepseek_capacity.py \
  tests/unit/test_assessment_first_case.py tests/unit/test_test_stand.py
/absolute/python -m pytest -q -m 'not integration and not e2e and not llm'
/absolute/python -m pytest -q -m e2e tests/e2e
```

У каждого запуска свой `--junitxml=docs/evc/evidence/provider-contract-env-roles/<name>.xml`.
У red ожидаемый exit1, остальных exit0. Предсуществующий Starlette/httpx warning
сохранён в результатах инструментов; зависимости не менялись.

Первый staged diff-check и commit hook отклонили trailing spaces внутри raw negative
JUnit. Его bytes не форматировались: primary помещён в ZIP, uncompressed SHA256
`293a8bdb9928c89f40aa3aad8f299e03532e45c8a243230fe0eb0ebe2f9b1798`
проверяется `CHECK.py` отдельно от SHA256 архива. Локальный raw `red.xml` игнорируется
только здесь; положительные результаты/исходники/hook не скрываются и не меняются.

Никаких обращений к серверу в этой реализации, developer dotenv/рабочей БД,
test DB create/cleanup, реальной почты, LLM, bump, push, PR, merge, deploy.
Schema/SQL не меняются: DB integration не требуется этим diff. Frontend не меняется:
build/browser не запускались. Unit default model/CLI tests не доказывают качество AS,
реальный human review, admission или полный PATH. CI остаётся отдельным обязательным
шагом выпуска. Старый sidecar `AC18-2072-FREE-PREFLIGHT.py` — историческая диагностика,
не способ запуска нового кандидата; после выпуска применяется новый штатный runner
и exact окончательный deployed SHA, не старое сравнение модели с `.env`.
