# AUTH-DIAG-01 — локальное исправление, без выпуска

## Результат и прослеживаемость

Разрешённый владельцем узкий UI fix реализован поверх
`dea8c44a183c2ac5f4b527e53cdeed0a39bcf454` в `codex/path-final-audit`.
`session.js::resetStaleUserState` синхронно очищает прежнюю ошибку после
fail-closed/returnToStart; `resetChatScreen` передаёт `preserveAuthFeedback=true`
в delayed `resetChat`. Поэтому текущий catch может показать новую401-ошибку,
которую последующая очистка чата не стирает. Перед reset остаётся проверка
точного session generation. Обычные reset/logout по умолчанию по-прежнему очищают
auth feedback. Сервер, cookie, API, схема, runtime-артефакты, methodology,
admission/repair и постоянный профиль/runner не менялись.

Подтверждённое наблюдение → правило lifecycle → три UI-файла → четыре настоящие
entry/dist browser-регрессии. Тест подставляет только synthetic HTTP и задерживает
доставку настоящего chat asset; DOM/fetch/таймеры/методы продукта не заменяются.
После release ждёт import того же модуля и следующий rendering turn, не sleep.
Проверки: delayed/eager401 оставляют видимую ошибку и закрытые защищённые экраны;
late cleanup не стирает другой аккаунт; BroadcastChannel смены поколения в другом
табе сохраняет fail-closed первого и новый вход второго; logout-запросов0.
Concurrent401, поздние старые200/401 и незавершённый recovery нового поколения
проверены существующими исполняемыми `api-unauthorized.test.mjs` в полном frontend.
Две новые source-level проверки дополнительно фиксируют defaults/guard; это не
замена browser-проверкам. UI-заголовок returnToStart не перерабатывался.

## Проверки и первичные доказательства

Все команды из корня worktree. Node25.5.0, Python3.12.13, установленные lockfile
dependencies и Chromium1243. Временно подключён только root node_modules symlink;
он удаляется перед commit без удаления target. `.env` не читался.
Для Node/browser — `env -i PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
HOME=/Users/vadim_bogachev …`; HOME только исходное значение для browser cache,
не переопределённая task variable. Browser listen разрешён только для собственного
localhost18764/18766. Backend: тот же sterile env + `PYTHON_DOTENV_DISABLED=1
DB_HOST=127.0.0.1 DB_PORT=1 DB_NAME=product4k_pytest_auth_fix DB_USER=synthetic
DB_POOL_MIN_SIZE=0`; ни рабочего URL, ни ключей LLM нет. Использовался Python
из `/Users/vadim_bogachev/Developer/4K/.venv/bin/python` без переноса окружения.

| Команда / область | Факт | Evidence |
| --- | --- | --- |
| Playwright `auth-recovery.spec.mjs --grep 'delayed cleanup'` до fix | exit1, 1 FAIL; ошибка пуста после cleanup | [JSON](../evidence/path-auth-fix/before/browser-results.json), PNG/context рядом |
| Playwright `auth-recovery.spec.mjs` после fix | exit0, 4 PASS, retry0 | [JSON](../evidence/path-auth-fix/after/targeted-results.json), delayed/eager PNG |
| `node --test tests/frontend/*.test.mjs` | exit0, 142 PASS | frontend.tap.gz |
| Python `-m pytest -m 'not integration and not e2e and not llm'` | exit0, 920 PASS /353 deselected | backend.txt.gz |
| Python `-m pytest -m e2e tests/e2e` | exit0, 108 PASS /12 deselected | http.txt.gz |
| `npm run lint:js`, `npm run build:web` | exit0;45 current assets; повтор сборки SHA25645 совпал | lint/build.txt.gz, dist-idempotency.sha256 |
| Playwright `auth-r03.spec.mjs auth-recovery.spec.mjs` | **exit1,117 PASS/2 timedOut**, retry0 | [full JSON](../evidence/path-auth-fix/after/full-results.json), stdout/context/PNG |
| Playwright auth-r03 `--grep 'restores the exact connected program after reopening\|keeps superadmin participant cards readable on narrow viewports'` | **exit1,1 PASS/1 timedOut** | [followup JSON](../evidence/path-auth-fix/after/followup-results.json) |
| `git diff --check`, offline CHECK, inventory/документальные ссылки | PASS после финальной фиксации inventory | пакет и CHECK output |

Все пути evidence без отдельной ссылки в таблице находятся в
`docs/evc/evidence/path-auth-fix/`. У Python одна известная deprecation warning
Starlette/httpx; это не FAIL. Первый setup node PATH был неполным (exit127),
затем sandbox запретил localhost listen (EPERM); после явного разрешения сохранён
настоящий before FAIL. Setup-ошибки не считаются воспроизведением продукта.

### Красный широкий browser gate

Первый полный run: R10 `selectOption` не нашёл program form, timeout150000ms;
ADM-STATUS остановился на клике `#verify-magic-link-button` в helper login,
до проверки layout. Фактическая recorded duration ADM1777707ms при заявленном
timeout150000ms; это наблюдение, не доказанная причина. Повтор неизменённых двух
тестов: R10 PASS; ADM timeout на том же шаге, total3614785ms. Timing/network trace
не включался (стандартный trace=off); причина UNKNOWN, baseline comparison для
этих новых timeout NOT_RUN. Связь с fix не установлена; они не объявлены ни новой
product cause, ни безопасным infrastructure-only сбоем. Полный набор **не PASS**.
Четыре auth-регрессии прошли и отдельно, и внутри полного run. Исходные FAIL
не заменены повтором; тесты/таймауты/ожидания не ослаблены. Исправления чужих
сценариев не включены в узкий допуск. Перед выпуском этот gate нужно разрешить.

## Границы, review и передача

Локальный self-review: diff узкий, defaults logout сохранены; generation check
после await неизменён, recovery не вызывает logout, нет server/DB/source-policy
изменений. Integration/real PATH/LLM NOT_RUN (не нужны для UI-only cleanup и
не разрешены); положительный synthetic browser не является реальной авторизацией
или human acceptance PATH. Новый CI, human code review и выпуск NOT_RUN.
Старый CI/deploy/readback946a46c PASS переиспользован **только** как статус уже
развёрнутого2.0.68, не как проверка этой новой локальной дельты.

Main и origin/main в локальных refs946a46c; свежий fetch не выполнялся, remote
дрейф не проверялся. Test — последний подтверждённый946a46c/2.0.68, сервер сейчас
не опрашивался и не менялся. Точный локальный commit/tree и diff after dea8c44
в package HANDOFF.json/bundle. Все release flags false. Откат — revert нового
локального commit; данные не затронуты. Готовность merge/deploy не заявляется.

Исторический auth114/1 остаётся UNKNOWN/causality NOT_ESTABLISHED.
PREP-DIAG-01 — отдельно UNKNOWN. Старый audit170/checker относится только к
immutable dea8c44; его FILES.json/отрицательный opt-in diagnostic не менялись.
Штатный browser перезаписал два прежних ADM PNG: новые сохранены здесь,
ровно исторические два файла восстановлены из dea8c44. Пользовательские файлы
не удалялись. Локальный CHECK подтверждает hashes и записанные результаты,
**не** выполняет заново browser/backend и не превращает красный gate в PASS.
