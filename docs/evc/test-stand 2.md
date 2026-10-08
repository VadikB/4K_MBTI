# Изолированный стенд 10.2

Стенд предназначен для технического Cycle M5–M8. Все пользователи и данные
синтетические. AI заменяется **только при явном** `--gateway 1`; это не GC,
не экспертная оценка и не проверка реального provider. Рекомендации детерминированные.

## Зависимости

Проверено: Python 3.12.13, PostgreSQL 15.16 (локально; CI — 16), Node 25.5.0
(локально; CI — 22), Python Typst binding 0.14.9. Поддерживаемая проверяемая связка
CI: Python 3.12 / PostgreSQL 16 / Node 22, Typst из requirements (>=0.14.8).
Используются `requirements-test.txt`, `requirements.txt`, `package-lock.json`.

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
npm ci
npm run build:web
```

Нужен уже запущенный локальный PostgreSQL, отдельная техническая роль с CREATEDB.
Не используйте роль или пароль рабочего сервера. Например, для отдельного пустого
локального кластера (PostgreSQL binaries должны быть в PATH):

```sh
mkdir -p .test-stand
initdb -D .test-stand/pg -U stand_owner --auth-local=trust --auth-host=trust
pg_ctl -D .test-stand/pg -l .test-stand/postgres.log -o '-h 127.0.0.1 -p 55492' start
export STAND_ADMIN_URL='postgresql://stand_owner@127.0.0.1:55492/postgres'
```

Trust здесь применим только к этому одноразовому localhost-кластеру без реальных
данных. Альтернатива — существующий отдельно подготовленный localhost test-server
с явным техническим паролем. Не указывайте рабочий/общий test/production.
Разрешены maintenance database `postgres` либо test БД CI `agent4k_pytest` /
`task11_pytest`; сами данные стенда всегда создаются в новой случайной БД.

## Подготовка

Из корня checkout, без рабочего `.env`:

```sh
.venv/bin/python scripts/test_stand.py create --state .test-stand/run-a/state.json --port 18520 --gateway 1
.venv/bin/python scripts/test_stand.py bootstrap --state .test-stand/run-a/state.json
.venv/bin/python scripts/test_stand.py seed --state .test-stand/run-a/state.json
.venv/bin/python scripts/test_stand.py serve --state .test-stand/run-a/state.json
```

`create` возвращает имя `product4k_pytest_<uuid>` и `application_tables=0`.
`bootstrap` — `bootstrap ready`, `seed` — `Synthetic input seed ready`.
`serve` работает в foreground, включает штатные workers. UI:
<http://127.0.0.1:18520/>. Readiness: `/health/ready`, включая `gateway_mode`.
Отсутствие bootstrap, другая структура, отсутствующий обязательный пакет дают
ошибку, а не `ready`. Конфликт порта проверяется до импорта приложения.

В другом терминале с тем же **явно заданным** STAND_ADMIN_URL:

```sh
.venv/bin/python scripts/test_stand.py smoke --state .test-stand/run-a/state.json
```

Smoke выполняет password login → start/resume → Turns → owner completion →
workers → C67/PDF, проверяет отказ другому пользователю. Polling ограничен 90 сек.
`smoke.json` содержит IDs/версии и режим; `report.json`/`report.pdf` — синтетические
артефакты. Повтор smoke читает **тот же** Report. Для нового прохождения — новая
state/БД. Не удаляйте smoke.json ради обхода повторного чтения.

В UI входят `participant@example.test` или `other@example.test`. Для каждого запуска
генерируется отдельный пароль, он находится в локальном `state.json` (права 0600).
Это одноразовые синтетические credentials; не публикуйте state.json. После входа:
«Подтвердить профиль» → dashboard → «Продолжить» → «Начать» → активная AS.
Никаких superadmin прав у участников нет. Seed не создаёт Cycle, Turns, IA или Report.

Без `--gateway 1` механизм — provider; credentials не наследуются из `.env` или
процесса родителя. Отсутствующий provider возвращает явную ошибку, не test-ответ.
Реальный provider smoke не входит в эти команды и требует отдельного допуска.

## Остановка, повтор, очистка

Остановить `serve` — Ctrl+C в его терминале. Затем можно повторить bootstrap/seed
и `serve` на том же state. Пароли, M4/AS snapshots и Results/C67 сохраняются.
Сброс не является частью bootstrap. Явная очистка:

```sh
.venv/bin/python scripts/test_stand.py destroy --state .test-stand/run-a/state.json
```

Удаляется только БД с совпадающими UUID и секретной меткой владения. Чужой state,
неизвестная БД и иной localhost server отклоняются. Активные подключения не
прерываются принудительно: сначала остановите `serve`. Артефакты smoke остаются.
Для собственного локального кластера после удаления всех его стендов:
`pg_ctl -D .test-stand/pg stop`. Команда не затрагивает другие кластеры.
Новый порт выбирается при `create --port`; новый независимый запуск — другой state.

## Автоматическая проверка / CI

```sh
.venv/bin/python scripts/test_stand_check.py --directory .test-stand/check-a --port 18521
.venv/bin/python scripts/test_stand_check.py --directory .test-stand/check-b --port 18522
```

Каждая команда создаёт пустую БД, выполняет bootstrap/seed, два запуска настоящего
main:app, HTTP smoke/read-back и повтор bootstrap/seed. По завершении сервер
останавливается и **своя** БД удаляется (даже при ошибке). `--keep` сохраняет БД
для анализа, но процесс всё равно останавливается. Exit nonzero — неуспех;
логи `create/bootstrap/seed/app/smoke/destroy.log` находятся в указанном каталоге.
State с credentials не входит в CI-артефакты и Git.

`tests/integration/test_clean_bootstrap_db.py` выполняет этот же entrypoint дважды
и отдельный отрицательный прогон. При явном integration без TEST_DATABASE_URL
тест падает, а не skip. Роль TEST_DATABASE_URL должна иметь CREATEDB.
Обязательные CI jobs frontend/pytest сохранены; pytest дополнен uvicorn для
настоящего subprocess-сервера.

## Границы передачи 10.3

Полный browser S10-A/B/C и T11-10 не закрываются HTTP smoke. Проверено лишь
обычное UI начало активной AS. Для чистой browser-трассы создайте новый state и
не запускайте smoke до UI (smoke сам завершает Cycle первого участника).
Зафиксированные версии входят в сохранённые M4/M5/Results/C67 snapshots; seed
использует M2/M3 QA publication lifecycle и изолированный M5 fixture-допуск из
существующего `test_m10_product_path_db`. Файлы исходных draft/WORKING пакетов
не меняются; fixture PASS не становится нормативным одобрением.

Legacy dashboard aggregate удалён по решению владельца. Dashboard читает Cycle/AS/
Report; промежуточный процент адаптивного плана не придумывается. Старые данные
не удаляются. Остальные legacy auth/profile/admin зависимости, которые реально
используются, требуют отдельного поэтапного удаления и пока остаются совместимыми.
