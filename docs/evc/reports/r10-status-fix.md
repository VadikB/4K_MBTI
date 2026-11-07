# R10-STATUS-DIAG-01 — локальное исправление завершено, без выпуска

## Результат

По разрешению владельца «Да, исправить локально» поверх
`4f2e884eac9e00f6f169dddfe5fad6d7a910aaa9` в `codex/path-final-audit` исправлен
DOM-only feedback подключения. Новый terminal outcome хранится только в памяти
UI и восстанавливается после `restoreAdminOrganizationsDraft`. Он связан с user,
identity epoch, organization, выбранным program_definition_id и снимком фактически
подключённого program_definition_id. Не участвует в admission/readiness/start.

Новый выбор org/program, новое действие, потеря доступа к org или clearing сессии
инвалидируют feedback. Собственный generation guard не даёт позднему callback
вернуть старое сообщение после смены выбора/действия; исходные session guards
сохранены. Restore не фокусирует/не скроллит и не копирует глобальный status в
чужую карточку. Failure/unknown тоже сохраняют error, не превращаются в success.
Exact command/readback проверки обоих ID и operation_id не изменены.
Повторный render карточки больше не стирает подтверждённый итог, хотя отдельная
ошибка загрузки анкеты503 остаётся видимой и не считается готовностью программы.

## Изменённые файлы и источники

Один runtime source: `web/js/screens/admin/organizations.js` — scoped transient
outcome, локальная rehydration и invalidation. Существующий `setStatus` сохраняет
поведение для остальных операций; выделен его прежний DOM helper.
`tests/browser/program-connection-feedback.spec.mjs` —10 новых executable
synthetic HTTP сценариев настоящего entry/dist. `arch30-program-connection.test.mjs`
—3 source-level guard regression в дополнение к browser, не вместо него.
45 dist assets пересобраны по существующему pipeline. Остальное — task/report/
STATE и новый immutable evidence-каталог. Server/Api/scripts/assessment_definitions,
payloads/public API, БД, published artifacts, M0–M8, prompts/admission/repair,
постоянный профиль и runner не менялись. Новой предметной нормы/debt нет.

Основание: existing R10 assertion493 → сохранённый current118/1 и comparison3/3FAIL
до AUTH fix → scope/lifecycle outcome → runtime → старые115 + auth4 + новые10.
Новая before регрессия с неизменённым продуктом4f дала1 FAIL на99 после настоящего
UI re-render. Новый test fixture в этом before был добавлен локально; это не
исторический продуктовый источник. Его bytes совпадают с переданным test source.
Прочитанные пути, stop-условия и допуск — [задача](../tasks/r10-status-fix.md).
Методология M1v1.4 остаётся FROZEN/CURRENT=NO, не runtime-допуск этой проверкой.

## Команды и первичные результаты

Все команды из корня worktree, Node25.5.0/Playwright1.63.0/Chromium1243,
Python3.12.13. Node/browser запускались в `env -i` с PATH системных бинарников и
исходным HOME для Chromium cache. Без чтения .env и без реальных credentials.
Backend/HTTP дополнительно `PYTHON_DOTENV_DISABLED=1 DB_HOST=127.0.0.1 DB_PORT=1
DB_NAME=product4k_pytest_r10_fix DB_USER=synthetic DB_POOL_MIN_SIZE=0`; рабочий URL
и ключи провайдеров не передавались. Browser listen только localhost18764/18766/18767.

| Проверка / команда | Факт | Primary evidence |
| --- | --- | --- |
| Playwright `program-connection-feedback.spec.mjs --grep '503 confirmed'` before | exit1,1 FAIL,8.7s,retry0 | [JSON/trace](../evidence/r10-status-fix/before/results.json) и outputs рядом |
| Playwright `program-connection-feedback.spec.mjs` after | exit0,10 PASS,14.3s,retry0 | [targeted JSON](../evidence/r10-status-fix/targeted/results.json),4 PNG |
| `node --test tests/frontend/*.test.mjs` | exit0,145 PASS | frontend.tap.gz |
| `npm run lint:js` | exit0,PASS | lint.txt.gz |
| `npm run build:web`, повтор после browser, SHA25645 | exit0,PASS,45/45 identical | build.txt.gz/dist-idempotency.sha256 |
| Python `-m pytest -m 'not integration and not e2e and not llm'` | exit0,920 PASS/353 deselected,104.8s | backend.txt.gz |
| Python `-m pytest -m e2e tests/e2e` | exit0,108 PASS/12 deselected,36.0s | http.txt.gz |
| Playwright `auth-r03.spec.mjs auth-recovery.spec.mjs program-connection-feedback.spec.mjs` | **exit0,129 PASS**,205.4s,retry0,skip0 | [full JSON](../evidence/r10-status-fix/full/results.json)/stdout/PNG |
| diff/Node syntax/документальные ссылки/inventory/CHECK | PASS | package/manifest/check output |

У browser: `node node_modules/@playwright/test/cli.js test … --trace retain-on-failure
--global-timeout 420000 --workers 1 --retries 0 --output .test-stand/r10-fix-full`.
Адресный after имел global-timeout120000, before60000. Штатные per-test150000ms/
expect5000ms и assertions не изменены. Full global deadline не достигнут.
Тесты не подменяют DOM/fetch/методы/таймеры продукта и не используют sleep:
сетевые fixtures + настоящие UI navigation/re-render. Lost PUT проверяется
штатным exact GET. Положительные 200/503 confirmed/lost, новая failed intent,
program/org/account/logout/late callback/changed server binding покрыты отдельно.
В полном наборе прошли прежние negative foreign/null/deadline/unknown и4 AUTH
регрессии. У Python одна известная Starlette/httpx deprecation warning, не FAIL.
Пути логов без отдельной ссылки — `docs/evc/evidence/r10-status-fix/`.

## Review, ограничения и состояние

Self-review: не вводится generic global-status replay или localStorage outcome;
реальный доступ/подключение по-прежнему решает server. Поле обратной связи не
меняет published program, состав пилота, готовность AS или условия старта.
Риски конфиг/схема/deploy: изменений нет; откат — revert этого рабочего commit
вместе с его dist. Данные не затронуты, миграции и восстановление БД не нужны.
Integration неприменим: нет изменения server/БД; real/paid PATH NOT_RUN и не
разрешён. Synthetic UI regression не подтверждает реальную авторизацию/human QA.

Локальный шаг завершён. Точный commit/tree и diff after4f — в package HANDOFF.
Новый CI/human review/bump/push/PR/merge/deploy/публикация/активация NOT_RUN.
Main/origin-main — локальные refs946a46c/2.0.68 (fresh fetch NOT_RUN), test —
последний подтверждённый946a46c, новый server readback не делался. Старый release
CI/deploy PASS относится только к946a46c, не к этому локальному коду. Следующий
gate — отдельное разрешение release preflight/кандидата/PR, затем mandatory CI
и человеческое review. Текущий допуск этот gate не открывает, baseline не назначен.

Два исторических ADM PNG, перезаписанных тестом, восстановлены из4f после
сохранения новых копий. Временный node_modules symlink удалён без удаления target.
Старые manifests170/183/76 не пересчитывались; replay только в их immutable
checkout. Новый CHECK проверяет hashes и **записанные** результаты, не новый run.
Отрицательные historical evidence не заменены положительным full129.
Прежние R10/ADM timeout остаются UNKNOWN, auth114/1 — NOT_ESTABLISHED;
PREP-DIAG-01 UNKNOWN отдельно. R10 status-loss исправлен, но не объявляется
причиной этих исторических случаев.
