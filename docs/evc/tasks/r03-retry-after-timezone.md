# R03 — корректный Retry-After при часовом поясе PostgreSQL

## Результат и граница

Повторный запрос ссылки в пределах cooldown получает HTTP 429 с правдивым
`Retry-After` от 1 до заданных 7 секунд при `UTC` и `Europe/Moscow`.
Исправляются два существующих технических расчёта для `auth_action_tokens` и
`auth_magic_links`; схема БД, публичный формат ответа, токены, предметные
артефакты, F05–F09 и логика допуска не меняются. Реальные письма не отправляются.

Основание — прямой ответ пользователя 12.11.2026: исправить R03 отдельно на
новой ветке, сохранив локальный кандидат F05–F09. База —
`origin/main@c06e94d5ff3784b2788b44089091a62a3921d301`, ветка
`codex/r03-retry-after`, worktree `/private/tmp/p4k-r03-retry-after`.
`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`; локальный код, owned test БД,
проверки и commit разрешены. Внешние действия требуют отдельного прямого
поручения.

## Источники, причина и решение

Использованы ранее прочитанные в этой сессии `README.md`, `CONTRIBUTING.md`,
`AGENTS.md`, `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
`docs/evc/review-checklist.md`, архитектурные Context/Registry и Change 01.
Адресно прочитаны `Api/auth_service.py`, `Api/routes.py`,
`tests/integration/test_r03_auth_full_flow_db.py`, `scripts/test_stand.py`,
`tests/README.md`, раздел FIX5 в `docs/evc/tasks/ux-r02-r03-fixes.md` и
исторический сбой в `docs/evc/tasks/p4k-f01-role-isolation.md`. Применимого
нового Decision ID или предметной нормы для этого технического расчёта нет.

Выбранные зафиксированные источники (SHA-256): Change 01 README
`ac082bb94aac1b86c61d7e39589d76c886c6703ef3afc07bc8fecf1676a0a26d`,
manifest `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0ef1c10b237db8`,
архитектурный Context
`effebfc639a572593b6171a7a57cfe60db09bba200909d8a4edafb0e7ac98ebb`,
Registry `b663db7f557fc3de3abd2d9e86b596926274ba4c5e2170047d4a6e5e60c54001`,
контракт ADR-002 `4a4e0170bee7faf137301b342fec46b3e8e0209acd26dcb6b2dc7a788c58b25f`
и карта `e528baedfa7bfa2f6aa8fdf9ea2ec4c3e092c32cedb5fa4068f0abc0af1d3eaa`.
M1 v1.4 остаётся `FROZEN / CURRENT=NO` и не предоставляет runtime-допуск;
изменение R03 техническое и не затрагивает границы PM-03–PM-07.
До изменений `Api/auth_service.py` имел SHA-256
`f56bd5f0d3a27bec172581e441dd063654e2fd3034b137a1022655a894155432`,
а R03 integration test —
`00b4d6801d9e2a4c3a6de510a91df3541aee1375c6198ce9fd56bccaae890860`.

`created_at` в обеих auth-таблицах — `TIMESTAMP` без зоны с `DEFAULT NOW()`:
значение записывается в часовом поясе сессии БД. Старый расчёт вычитал
`CURRENT_TIMESTAMP AT TIME ZONE 'UTC'`. На owned PostgreSQL 15 с
`Europe/Moscow` тестовый HTTP 429 фактически вернул `Retry-After: 10807`
при cooldown 7 секунд; на неизменённом `origin/main` тот же тест упал.
Исторический отчёт исправлял только зону тестового кластера. Предыдущая
интерпретация строки pytest как `Retry-After: 0` была ошибочной: точный
HTTP readback показал 10807.

Решение: вычитать `LOCALTIMESTAMP`, совпадающий по зоне и типу с существующим
`created_at`. Это не мигрирует и не переписывает старые записи. Граница:
сохранённые naive timestamps не позволяют восстановить исходную зону записи,
если зону сервера меняли между выдачей и повтором; такой перенос данных здесь
не выполняется. Стоп-условий рабочего цикла нет: смысл и PM, права, API и
схема не меняются, откат — revert только этой ветки.

Связь: существующий контракт cooldown HTTP 429 → `AuthService` и два поля
`created_at` → `Api/auth_service.py` → owned HTTP/PG тест при двух зонах.
Публичный route лишь передаёт `AuthRateLimitError.retry_after_seconds` без
изменения. Владелец данных — auth service; UI и предметная оценка не затронуты.

## План, проверки и передача

1. Воспроизвести на базе и зафиксировать фактический заголовок и зону — DONE.
2. Исправить оба расчёта; расширить реальный owned PG тест для `UTC` и
   `Europe/Moscow`, action и magic link — DONE, адресно 2 PASS.
3. Выполнить локальный минимум матрицы: backend unit, HTTP и полный
   integration на allowlisted marker-owned test БД, `git diff --check`,
   затем review и commit — DONE локально.

Тестовые БД создаются только через `scripts/test_stand.py` или в выделенном
локальном PostgreSQL с точным owner marker; перед удалением marker проверяется.
Ни production/test данные, ни реальные письма и LLM не используются.
Откат: revert изменений `Api/auth_service.py` и регрессионного теста; схемы и
сохранённых данных изменение не касается. CI и human review — после прямого
разрешения на push/PR; merge/TEST/приёмка не входят в текущий этап.

## Проверки и review

| Команда / действие | Результат |
| --- | --- |
| `STAND_ADMIN_URL=<owned-maintenance-url> .venv/bin/python -m pytest --run-integration -q tests/integration/test_r03_auth_full_flow_db.py` | 2 PASS: UTC и Europe/Moscow; реальный HTTP/PG action cooldown и прямой magic link cooldown с контролируемым mail sink. |
| `npm run test:backend` | 1089 PASS, 551 deselected, 1 warning. |
| `npm run test:backend:http` | 152 PASS, 13 deselected, 1 warning. |
| `STAND_ADMIN_URL=<owned-maintenance-url> TEST_DATABASE_URL=<owned-agent4k_pytest-url> npm run test:backend:integration` | 393 PASS, 2 SKIP явного real-provider LLM, 1245 deselected, 1 warning; 724.22 с. |
| `py_compile` изменённых Python-файлов с кэшем в `/private/tmp`; `git diff --check` | PASS. |

Предупреждение — существующий `StarletteDeprecationWarning` в зависимости
FastAPI TestClient. Полный integration выполнялся одним процессом. Тестовый
`agent4k_pytest` создан в выделенном PostgreSQL 15, после прогона точный owner
marker проверен, БД удалена, контрольный запрос не нашёл stand БД, кластер
остановлен. [Безопасная сводка](../evidence/r03-retry-after-timezone/summary.json).

Review: изменены только два SQL-выражения и owned интеграционный тест;
`Api/routes.py`, публичный статус/форма 429, схема, миграции и конфигурация не
меняются. Retry сохраняет прежний предел и не выдаёт фиктивное время.
Новые переменные окружения не вводятся. Риск — legacy `TIMESTAMP` без зоны,
описанный выше; проверена совместимость новых записей в двух зонах. Frontend,
сборка и визуальная проверка неприменимы, поскольку UI-файлы не изменены.

## Передача одного PR

**Заголовок:** R03: корректный Retry-After для часового пояса PostgreSQL.

**Описание:** HTTP 429 для повторного запроса ссылки берёт остаток cooldown из
часов сессии БД, в которых записан `created_at`; два пути auth и owned
PostgreSQL проверены при UTC/Europe-Moscow. Публичный контракт и схема не
изменены. Локальные backend/HTTP/integration проверки выше; CI и human review
ещё не выполнялись. Откат — revert коммита этой ветки.

Следующий шаг после локального commit — прямое разрешение на push/PR,
обязательный CI точного SHA и human review. При возврате к F05–F09 исправить
в его отчёте прежнее ошибочное прочтение `Retry-After: 0` на фактические
`10807` секунд и интегрировать R03 только после независимого принятия.
