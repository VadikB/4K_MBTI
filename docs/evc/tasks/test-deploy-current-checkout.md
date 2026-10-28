# TEST-DEPLOY-28 — актуальный test checkout

## План, основания и границы

База: `84467d12814196b3196e72f841d462de1a7f8223`, свежий `origin/main`, 2.0.33.
Ветка: `codex/test-deploy-current-checkout`. Владелец 28.10.2026 явно разрешил
отдельный инфраструктурный PR после merge #122 и отдельно кандидат PATCH 2.0.34.
`branch_push=true`, `pr=true`, `version_bump=true`; прежний допуск test-only
выпуска сохраняется, но merge требует CI точного head и нового человеческого review.
`artifact_publish=false`, pilot/production не входят в область.

Read-only inventory, предоставленный владельцем доступ:
SSH с существующим локальным ключом работает как `vadim_bogachev`;
DNS `test.4k-assistant.ru` указывает на `178.236.26.203`.
`agent4k-test.service`: User=`vadim_bogachev`,
WorkingDirectory=`/home/vadim_bogachev/projects/Agent4K-Test`.
Checkout чистый, main/HEAD=`0b44c26541f26adac067c7f5f08eda3d416ff862`;
оба `/home/user1/projects/{Agent4K-Test,4K-Mbti-Test}` отсутствуют.
Старый committed deploy script сам использует `/home/user1/...`.
Изменение только пути его вызова не устраняет bootstrap-дефект.

В environment test HOST обновлён с отдельного допуска владельца. CI попытка #3
[run 40729737543](https://github.com/VadikB/4K_MBTI/actions/runs/40729737543):
Configure SSH PASS, затем `Permission denied (publickey)`, exit 255, до удалённого
скрипта. PRIVATE_KEY/USER не читались и не менялись. Локальный личный ключ не
переносится в CI; пару CI-user/key настраивает владелец отдельно.

## Источники и стоп-условия

Прочитаны README.md, CONTRIBUTING.md, AGENTS.md, agent-workflow,
verification-matrix, artifact-recipe, tests/README.md; действующие workflow,
deploy/retention scripts, release guard и их тесты; карточки UX-ADM28-ADD01-v2
и frontend-deploy-asset-compatibility. Неизменённый архитектурный контекст,
Registry, M1 1.4 FROZEN/CURRENT=NO, Change 01/manifest из предыдущей задачи
переиспользуются только для фиксации отсутствия предметного изменения.
PM/LU, API, схема, данные, methodology и published snapshots не затронуты.
Все восемь стоп-условий — нет в области кода. Отдельный внешний стоп для выпуска:
CI credential и человеческое review; этот PR не предоставляет новые SSH-права.
Управляющие документы не меняются, baseline не заявляется.

## Реализация

1. Workflow запускает bootstrap в фактическом test-каталоге. Скрипт читается
   из Git по точному CI-проверенному SHA без предварительного checkout, без
   ручной загрузки файлов с компьютера. Проверяются SHA и принадлежность main.
2. Deploy script допускает фактический test root, сохраняет legacy test roots,
   отклоняет tracked dirty checkout, старый/чужой target. Предыдущий SHA фиксируется
   до обновления. CI передаёт точный SHA; режим без аргумента совместим с прежним.
3. Не меняются service/port, fingerprint, StrictHostKeyChecking, auth gates,
   retention и предметные пакеты. Ошибка build/smoke возвращает предыдущий SHA.

Локальный минимум до реализации: shell/YAML parse; адресные shell-процессы в синтетических
temporary Git-репозиториях без SSH/БД/LLM, bootstrap старого script и точный SHA,
отказ грязного/неизвестного/старого/чужого target, rollback на build/smoke;
затронутые unit/release tests, backend unit при изменении Python-тестов;
lint/frontend/build/reproducible dist/release guard для кандидата 2.0.34;
diff-check. Полный frontend/pytest CI обязателен перед merge.

## Изменённые пути и фактические проверки

- `.github/workflows/backend-tests.yml`: фактический test root, bootstrap из Git,
  точный `github.sha`, проверка user и timeout соединения; SSH gates сохранены.
- `scripts/deploy_test_remote.sh`: дополнительный известный test root,
  pinned SHA, fail-closed dirty/behind/divergent, сохранение исходного rollback SHA.
- `tests/unit/test_test_deploy_bootstrap.py`: 16 синтетических регрессий; каждый
  сценарий создаёт собственный temporary Git origin/checkout, подменяет только
  npm/curl/sudo, не использует SSH, БД, developer `.env` или real-provider.
- `pyproject.toml`, `uv.lock`, `web/js/config.js`, `web/index.html`, `web/dist/`:
  один штатно подготовленный кандидат 2.0.34. UI-поведение не меняется;
  изменение hashes — следствие единого номера версии.
- Эта карточка и `STATE.md`: основания, статус, границы и передача.

PASS, exit 0:

- `npm run lint:js`.
- `node --test --test-reporter=dot tests/frontend/*.test.mjs` — 82.
- `npm run bump:version -- patch --dry-run`, затем
  `npm run bump:version -- patch --candidate 2.0.34`, `npm run build:web`.
- `.venv/bin/python scripts/check_release_version.py` — consistency 2.0.34.
- YAML parse с проверкой состава frontend/pytest/deploy-test; `sh -n` основного
  script и bootstrap из workflow; `git diff --check`.
- `.venv/bin/python -m pytest -p no:cacheprovider -q
  tests/unit/test_test_deploy_bootstrap.py tests/unit/test_frontend_asset_retention.py
  tests/unit/test_release_version.py` — 25.
- Первый backend unit до расширения пяти cases — 610 PASS; окончательный
  `npm run test:backend -- -p no:cacheprovider` — 615 PASS, 254 deselected,
  exit 0. Единственное предупреждение — существующая deprecation Starlette/httpx.

Read-only серверная проверка `sudo -n -l /usr/bin/systemctl restart
agent4k-test.service` — PASS: уже существующее право есть, restart не выполнялся.
Локальные HTTP/PostgreSQL/browser не повторялись для чисто deployment-изменения:
API/данные/сценарии неизменны, предыдущий main 84467d1 имел 81 HTTP,
167 integration и 77 browser PASS. Для нового head полный CI обязателен,
предыдущий успех не подменяет его результат.
Release guard относительно свежей базы и reproducible build проверяются
на commit перед передачей; final SHA/CI URL — в единственном PR этой задачи.

## Риски, откат и передача

Секреты не читаются и не входят в PR/evidence. Server `.env` и БД не читаются
и не меняются тестами. Нужна корректная CI-пара user/key и существующее право
перезапуска только test-service. Никакие SSH/sudo-права этим PR не расширяются.
Откат приложения: штатный rollback на сохранённый SHA; откат изменения — revert
PR без удаления данных/snapshots. Обязательный CI пока NOT_RUN;
deploy новой версии/HTTPS/визуальная приёмка — NOT_RUN/PENDING.
Следующий шаг: PR; затем CI точного head,
новое человеческое review и исправная CI-пара user/key перед test-only выпуском.
