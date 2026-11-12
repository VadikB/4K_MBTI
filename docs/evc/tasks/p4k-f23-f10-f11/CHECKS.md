# Проверки P4K-F23-F10-F11

## Идентичность и доказательства

- База: `origin/main=aeea4e10014f9852e269eff0da8bf8cabe8d4427`, ветка
  `codex/p4k-f23-f10-f11`. Точный SHA кандидата фиксируется в финальном
  `source.json` сквозного прогона и передаче владельцу после commit.
- Проверки выполнены на содержимом локального кандидата. Сквозной повтор после
  commit записывает тот же SHA в `/private/tmp/p4k-f23-f10-f11-final/*/source.json`.
- Owned PostgreSQL: отдельный локальный контейнер `p4k-f23-f10-f11-pg`, БД с
  `test`/`pytest` в имени; browser-стенды создают marker и проверяют владение при
  удалении. Рабочая и пользовательская БД не применялись.
- Сквозной PASS после исправления UI:
  `/private/tmp/p4k-f23-f10-f11-combined/b9d2e4e3-80ea-4e68-96c5-0078617b520b/`.
  `source.json`, `baseline.json`, `after-grant.json`, `after-assignment.json`,
  `saved-a.json`, `switched-b.json`, `revoked.json`, `cleanup.json` — числовой
  readback до/после. В `cleanup.json`: `owner_verified=true`,
  `database_absent=true`, `state_absent=true`, `force=false`.
- Исторический, не текущий TEST receipt общего выпуска:
  `docs/evc/evidence/pilot-program-publication-execution/published-release-source.json`,
  SHA-256 файла `09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b`.
  `specialist_pilot@1.2`, configuration `11`, catalog `2`, definition checksum
  `b4e8270fd10436c417d7b40b8be8049dc2e9329f42a1ffa6d725877480d04718`.

## Критерии

Статус `PASS` здесь означает адресный локальный синтетический контур; отдельные
внешние проверки указаны ниже. В сквозном тесте Cycle A вставлен **fixture после
реального UI assignment** и служит только проверке сохранения ранее записанных
источников при A→B. Он не доказывает product prepare или полный EXEC.

| AC | Данные и ожидание | Фактическое доказательство | Статус |
| --- | --- | --- | --- |
| F23-AC01 | U participant в A; grant/revoke по 2 раза; B без изменений; повтор не меняет timestamps | Новая HTTP/PG регрессия до исправления `FAIL`, после `PASS`; browser до UI fix выявил пустой admin-list при успешном grant, после fix UI показывает кнопку revoke и убирает её после команды; `revoked.json`: U снова `member`, `is_participant=true`, контрольная org без связей, сохранённые binding/Cycle равны A | PASS |
| F23-AC02 | U org-admin и participant; личный маршрут, возврат/reload/deep-link без Cycle | Совмещённый browser: вход U, личный маршрут, reload/возврат, `after-assignment.json` имеет `cycles=[]`; адресный `auth-r03.spec.mjs` deep-link `PASS`; `test_f01_role_isolation_db.py` — роль оценки не даёт admin scope | PASS |
| F23-AC03 | Ordinary admin, чужая org, superadmin-target/configured права | В combined UI U видит свою org; прямые foreign GET и connect PUT дают `403`; F01 HTTP/PG проверяет запрет назначения configured superadmin без membership, role isolation; `superadmin_memberships=0` до/после | PASS |
| F10-AC01 | Exact deps; missing/draft/retired; dry-run 0 writes | Новый `test_f10_publisher_db.py`: штатный CLI `VALIDATED_ONLY`, checksum, 0 новых definitions, отказ missing/draft/retired config, retired catalog, draft role; источник/версии общего выпуска сверены с receipt | PASS |
| F10-AC02 | Published immutable; retire; новые connect/assign запрещены, история/старые источники сохранены | `test_program_publication_retirement_db.py` и `test_arch30_program_definition_db.py`: trigger запрещает UPDATE/DELETE content, retire точного checksum, повтор и rollback, retired connect/resolve запрещены; сквозной saved A при B неизменен | PASS |
| F10-AC03 | Штатная команда, receipt, различить выпуск и синтетику | `test_f10_publisher_db.py` и browser fixture запускают штатный release CLI на owned PG и сверяют published checksum/refs. Общий published receipt выше — исторический. Новый рабочий выпуск: `NOT_RUN`, нет прямого `artifact_publish` | PASS локального lifecycle; actual publication NOT_RUN |
| F11-AC01 | UI S подключает точную A/B, readback/reload; foreign и недопустимые версии без записи | Combined UI и PG: A затем B, имена/версии совпадают; U foreign GET и connect PUT `403`; `test_arch30_program_definition_db.py` draft/retired отказывает, 0 связей; существующий browser/HTTP guard | PASS |
| F11-AC02 | A→B, loss до/после commit, exact replay, история, binding/Cycle A | Новый PG тест: rollback до commit, replay receipt после commit, conflict на изменённый payload, A closed/B current, control org A; `saved-a.json`=`switched-b.json` для assignment/binding/Cycle | PASS |
| F11-AC03 | Absent/unknown/delayed; blockers/feedback; 320/390/1440, text200% | 41 browser PASS: `adm-program-guards`, `adm-program-visual`, `adm-program-positive`, `adm28-real`, `program-connection-feedback`; actual handlers/renderer, запрет POST, поздний ответ, доступность независимых сведений. Автоматическая browser-проверка не заменяет owner visual на TEST | PASS локально; owner visual NOT_RUN |
| INT-AC01 | Одни S/U/org A+B: S connect/grant, U self assignment и маршрут, A→B, revoke | Новый combined browser/HTTP/PG `1 PASS`: `baseline`→`after-grant`→`after-assignment`→`saved-a`→`switched-b`→`revoked`; точные id, membership, connection history, binding/Cycle и контрольная org в JSON; cleanup доказан | PASS локально |

## Команды и локальный минимум

| Команда/контур | Факт |
| --- | --- |
| `npm run lint:js`, `npm run build:web`, `git diff --check` | PASS |
| `node --test tests/frontend/*.test.mjs` | 261 PASS |
| `npm run test:backend` | 1089 PASS, 547 deselected |
| `npm run test:backend:http` | 152 PASS, 13 deselected |
| Адресные новые HTTP/PG, F10/F11 и role tests на owned PG | PASS; F23 before-fix регрессия была FAIL, после fix PASS |
| `npx playwright test tests/browser/adm-program-guards.spec.mjs tests/browser/adm-program-visual.spec.mjs tests/browser/adm-program-positive.spec.mjs tests/browser/adm28-real.spec.mjs tests/browser/program-connection-feedback.spec.mjs --workers=1 --reporter=line` | 41 PASS |
| `npx playwright test tests/browser/auth-r03.spec.mjs --grep 'ADM19-02 routes org-admin own assessment'` | 1 PASS |
| `npx playwright test tests/browser/f23-f10-f11-combined.spec.mjs --workers=1` | 1 PASS после исправления UI, 42.3s; повтор на зафиксированном SHA: 1 PASS, `source.json` и `cleanup.json` в `/private/tmp/p4k-f23-f10-f11-final/` |
| `npm run test:backend:integration` с `TEST_DATABASE_URL=.../p4k_f23_f10_f11_pytest` | 367 PASS, 2 skipped, 25 setup ERROR из EXEC-FIX02: его fixture принимает лишь `agent4k_pytest`/`task11_pytest`; ошибка DSN тестового стенда, не assertion продукта. См. `/private/tmp/p4k-f23-f10-f11-integration.log` |
| EXEC-FIX02 с исправленным DSN `.../agent4k_pytest` | 25 PASS, 1 warning (`/private/tmp/p4k-f23-f10-f11-exec02.log`) |
| Полный `npm run test:backend:integration` с исправленным DSN | 392 PASS, 2 ожидаемых real-provider skip, 1245 deselected, 1 warning (`/private/tmp/p4k-f23-f10-f11-integration-corrected.log`) |

Команды DB/browser запускались с `TEST_DATABASE_URL` и `STAND_ADMIN_URL`,
указывающими только на локальный owned контейнер. Никакие реальные provider/LLM
вызовы не выполнялись. Секреты, токены и персональные данные в evidence не сохранены.

## Внешняя граница и следующий шаг

`PR-CI=NOT_RUN`, `main=NOT_RUN`, `artifact_publish=NOT_RUN`, `TEST=NOT_RUN`,
`owner visual=NOT_RUN`, `real-provider=NOT_RUN`, полный EXEC `NOT_RUN`.
До merge необходимы обязательные CI `frontend`, `pytest`, `full-verification` и
человеческое review. После отдельного допуска: push/PR, релизная подготовка по
`ready:prepare` с согласованной версией, TEST/readback deployed SHA и визуальная
приёмка владельца. Эти статусы нельзя выводить из локального PASS.

## Продолжение: draft CI и release preflight

| Проверка/действие | Факт на 11.11.2026 |
| --- | --- |
| GitHub draft PR #212, head `b8654a8943b628145a2995da6f8f3bd54d35f82b` | `frontend` PASS, `pytest` PASS; `full-verification` SKIPPED по условию draft; review/merge/TEST NOT_RUN |
| `git fetch origin main`, `git merge-base HEAD origin/main` | PASS; база `aeea4e10014f9852e269eff0da8bf8cabe8d4427`, версия `2.0.99`, ветка актуальна |
| `npm run ready:prepare` без candidate | Ожидаемый exit 2, без изменения файлов; предложен PATCH `2.0.100` |
| `python3.12 scripts/prepare_release.py patch --dry-run` | PASS; ровно `pyproject.toml`, `uv.lock`, `web/js/config.js`, `web/index.html` |
| `npm run ready:prepare -- --candidate 2.0.100` после прямого решения владельца | PASS; release gate, сборка `web/dist`, 39 product paths |
| `python3.12 scripts/check_release_version.py --base-ref origin/main`, `git diff --check` | PASS; версия `2.0.100`, замечаний по diff нет |
| `node --test tests/frontend/*.test.mjs`, `npm run lint:js` | 261 PASS; lint PASS |
| `/Users/vadim_bogachev/Developer/4K/.venv/bin/python -m pytest -m 'not integration and not e2e and not llm' -q` | 1089 PASS, 550 deselected, 1 dependency warning |

Эта секция фиксирует состояние до commit release-кандидата. Полный CI на его
точном SHA, человеческое review, merge/deploy/TEST и новый рабочий выпуск
программы остаются отдельными проверками.

## Регрессия CI на release head и исправление

На `11b91319e9ee38afb54f5a3e58c0e1c6ab088d96` обязательные `frontend` и
`pytest`, integration и четыре runtime browser lanes — PASS. Browser fast:
`229 PASS, 1 FAIL, 1 SKIP`; сводный `full-verification` — FAIL. Единственный
отказ — новый `f23-f10-f11-combined.spec.mjs:82`: после connect A проверка
`toContainText('Синтетическая программа 1.0')` срабатывала по тексту `<option>`
до подтверждения операции. При последующем render поле email терялось, а grant
отвечал «Укажите email администратора.» Это ошибка ожидания теста, не отказ
server grant/readback.

Оба подключения A/B теперь ожидают `[data-program-connection-state]` с точной
строкой `Подключено: ...` после readback. Адресный повтор на owned PG:
`npx playwright test tests/browser/f23-f10-f11-combined.spec.mjs --workers=1`
— PASS, 1 тест, 36.9s. База тестового стенда создана и удалена штатным
`test_stand.py` (`owner_verified`, `database_absent`, `state_absent` — true);
отдельный собственный контейнер PostgreSQL удалён, `docker ps -a` пусто по
его имени. Полный CI требуется повторить на commit исправления.

## CI после восстановления GitHub Actions, 12.11.2026

На `a0181e03e1d49edfd29b9e72181c48eb4098cf94` исходный Full verification
[#227](https://github.com/VadikB/4K_MBTI/actions/runs/43094314200) завершился
`FAIL`: все тестовые шаги прошли, но загрузка browser evidence дала
`Failed to CreateArtifact` после пяти попыток; GitHub также сообщил
`Internal server error`, correlation ID `591e2d73-ebeb-4103-bc76-73d40c4bcc6a`.
Запуски Full verification
[#228](https://github.com/VadikB/4K_MBTI/actions/runs/43097560601) и CI
[#965](https://github.com/VadikB/4K_MBTI/actions/runs/43097560577) остались
`Queued` после объявленного GitHub восстановления. UI-отмена каждого вернула
`Failed to cancel workflow`.

Повтор исходного CI [#964](https://github.com/VadikB/4K_MBTI/actions/runs/43094314154),
attempt 2, на том же SHA — `PASS` (`frontend`, `pytest`; `deploy-test` ожидаемо
`SKIPPED`). Повтор Full verification #227, attempt 2, выполнил integration и
четыре runtime browser lanes, но browser fast завершился `FAIL`: существующий
`path-admin-contract.spec.mjs:87` ожидал подтверждения чтением операции не более
стандартных 5 секунд; при подтверждённом HTTP 200 UI ещё показывал `loading`.
Результат browser fast: 229 PASS, 1 FAIL, 1 SKIP. Это не свидетельствует об
ошибке нового admin grant/revoke: отказ находится в ожидании прежнего AC09.

Ожидание AC09 теперь проверяет точный текст readback в течение 20 секунд и
затем `data-tone=success`; постоянное отсутствие подтверждения по-прежнему
завершает тест ошибкой. Адресный HTTP/PG browser-прогон против отдельного
`agent4k_pytest` в owned контейнере:
`npx playwright test tests/browser/path-admin-contract.spec.mjs --workers=1 --reporter=line`
— `1 PASS (42.7s)`. Первый запуск без разрешения на Chromium не стартовал из-за
локальной песочницы; повтор с разрешённым Chromium — PASS. Контейнер
`p4k-f23-f10-f11-ci-pg` остановлен и удалён (`docker ps -a` не находит его).
Полный CI на следующем commit, проверка обязательных статусов PR и человеческое
review остаются обязательными.
