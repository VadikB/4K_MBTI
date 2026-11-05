# PATH-AC02/05: бесплатные первичные доказательства

Область/источники/риски/AC matrix: [карточка](../../tasks/path-ac02-ac05-coverage.md).
Base bb3b5cb /2.0.67; product source before fbe338670d02…; новый working SHA —
в пакете передачи. Main/test не менялись. Никаких новых LLM или working DB access.

## Результаты и ограничения

- `fixture-reload-race.json`/output:2 FAIL,1 interrupted,14 not run из-за
  incomplete reload fixture. `mixed-before.json`:2 PASS/15 FAIL, из них3 fixture,
  12 product AC05 ложное «не подключена». Не выдаются за чистый product before.
- `clean-before.json`: AC02 **3 PASS**, product AC05 **2 FAIL** на исходном dist.
  Исправлен только synthetic bootstrap/ожидание экрана, product source ещё bb3b5cb.
  Test source hash43b8bb28a0b2738ac9aae4a9ef0e29492b2432152c281a816717e4eb72d6b282.
  `clean-before-spec.mjs.gz` восстановлен обратной дельтой позднейших assertions;
  распакованные байты точно совпали с этим хешем, записанным до product fix.
  Для before replay использовать этот spec в отдельном checkout bb3b5cb, не новый dist.
- `after-selection.json`:**17 PASS**,52.138s;3 AC02 +12 fault combinations +2
  foreign-org guards. HTTP synthetic, реальный entry/dist/deadline15s, retries0.
- `browser-full-first.json`/`browser-full.txt.gz`:**114 PASS/1 FAIL**,136.215s;
  R03 auth error отсутствовал. Это неизвестная причина, не установленная регрессия.
- `auth-baseline-repeat.txt` и `auth-candidate-repeat.txt`:по**5 PASS**, без
  изменения auth source/теста. Baseline463e7e2 имеет то же дерево4565dbf0, что bb3b5cb.
  `auth-baseline-launcher-error.txt`: первая команда до теста не нашла Node dependency;
  после временного локального symlink повторилась штатно. Не продуктовый отказ и не skip PASS.
- `browser-full-control.json`/`browser-full-control.txt`:полный контроль**115 PASS**,137.827s,
  exit0/retries0/skipped0, код/критерий не менялись после первого полного114/1.
  Это не доказательство исправления единичного auth-сбоя. Сохранён его PNG.
- `frontend.txt`:**140 PASS**; `lint.txt.gz`:exit0; `http-and-m3.txt`:**25 PASS**,
  sentinel port9/без БД; `build.txt`:45 assets, повторная сборка идемпотентна.
- `ac02-integration.txt`:**2 PASS**, PostgreSQL16/real route/DDL/transactions;
  auth/scope и list projection synthetic, не полный auth/UI E2E. UNIQUE table DDL
  извлечён из текущего Api/database.py, не выдуман отдельный fixture-контракт.
- `container-owner.txt`:точный новый container/labels; `owned-schemas-after-tests.txt`=0;
  stop/removed содержат exact ID, `container-after-cleanup.txt` пуст — контейнер удалён
  с собственным anonymous volume без FORCE. Ни одна другая БД/контейнер не цель cleanup.
- `ac05-unknown-{1440,320,390,768}.png`:synthetic viewport assertions;1440/320
  визуально просмотрены. `generated-*-status-list.png` — новые побочные captures старого
  теста, исторические adm-status-01 PNG восстановлены из immutable bb3b5cb.

## Проверенные команды

Все browser/frontend/lint запущены с `env -i` и только
`PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin LANG=en_US.UTF-8`.
Никаких .env/provider credentials. Временные node_modules/.venv symlinks
не попали в Git/пакет и после проверок удалены без удаления targets/зависимостей.
Они не являются новым runtime. Для повторения нужны зависимости
package-lock/requirements-test и установленный Chromium; localhost18764 свободен.

```sh
node node_modules/@playwright/test/cli.js test tests/browser/auth-r03.spec.mjs --grep 'PATH-START AC0[25]'
node node_modules/@playwright/test/cli.js test tests/browser/auth-r03.spec.mjs
node node_modules/@playwright/test/cli.js test tests/browser/auth-r03.spec.mjs --grep 'R03 successful password response reports a missing browser session' --repeat-each=5
npm run lint:js
node --test tests/frontend/*.test.mjs
npm run build:web
git diff --check
shasum -a 256 -c docs/evc/evidence/path-ac02-ac05/code-sha256.txt
```

HTTP+M3: `.venv/bin/python -m pytest -q -m 'not integration and not llm'
tests/e2e/test_adm27_assignment_http.py tests/e2e/test_m3_role_profile_selection_http.py
tests/unit/test_m3_base_roles.py`, sterile `PYTHONPATH=.`/isolated marker,
DB_HOST127.0.0.1/DB_PORT9/DB_NAMEproduct4k_pytest_ac02_ac05/DB_POOL_MIN_SIZE0,
LOG_TO_FILE=false/AUDIT_LOGS_TO_DB=false/PYTHONDONTWRITEBYTECODE1.

Integration: `.venv/bin/python -m pytest -q --run-integration
tests/integration/test_path_ac02_organization_create_db.py`, тот же sterile env,
отдельный TEST_DATABASE_URL localhost55439/product4k_pytest_ac02_ac05; DB_NAME
sentinel `product4k_pytest_unused`, не совпадает с test target. Новый контейнер
postgres:16 (image ca0bd484…) не имеет host mounts, опубликован только на127.0.0.1.

`code-sha256.txt` фиксирует50 source/asset файлов; `FILES.sha256` покрывает evidence,
карточку и STATE. Проверять из корня **этого working commit**, не будущего bump/dist:

```sh
shasum -a 256 -c docs/evc/evidence/path-ac02-ac05/FILES.sha256
```

Хеши разных объектов не приравниваются. JSON/PNG — оригинальные test outputs;
сырые stdout/error-context с trailing whitespace хранятся lossless gzip, потому
что staged diff-check отклонил исходные текстовые окончания. Проверка не отключалась,
содержимое не нормализовано; распаковка восстанавливает исходные байты.
нет auth traces/cookies/паролей/данных рабочей БД. Опубликованные определения и
исторические CHECK не менялись. Mandatory CI/human review для нового кандидата
пока NOT_RUN. Старый provider PASS остаётся только e63/2.0.66.
