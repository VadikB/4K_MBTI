# FIX-B01/B02 — безопасность API подготовки Cycle

## Результат

Публичные ответы подготовки Cycle раскрывают только разрешённую участнику
проекцию, а повтор `operation_id` проверяет владельца и содержимое запроса до
возврата сохранённого результата.

## Область

- Включено: POST/GET подготовки Cycle, очередь
  `product_cycle_preparation_operations`, серверная публичная проекция,
  регрессии HTTP и PostgreSQL.
- Не входит: FIX-B03, изменение генератора/tester, изменение методологии,
  публикация пакетов, пилотная конфигурация и перестройка общей lease-модели.

## Контекст

- Основание: запрос владельца от 2026-10-23 и пакет
  `P4K_Case_AS_Cycle_Plan_2026-10-23.zip`, редакция 2.0.
- База: `f4af7beb0d09374153bf0e16c6edb5c0dabe1cec`, приложение `2.0.16`, PR #102.
  Кандидат результата: приложение `2.0.17`, PR #103.
- Значимые точки входа: `POST /users/assessment/cycles/prepare`,
  `POST /users/assessment/m7/cycles/{cycle_id}/next`,
  `GET /users/assessment/cycles/preparation/{operation_id}`.
- Архитектурный адрес: PM-03/PM-04, API/queue/DB; внутренние доказательства
  генератора остаются серверными, участник получает только публичное состояние.
- Контракты: ADR-002 C-23/C-24/C-34/C-45; Product Architecture v1.0 +
  Change 01 WORKING; task SourceSet `2026-10-01`.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
  `docs/evc/artifact-recipe.md`, архитектурный context/Registry, Change 01,
  SourceSet manifest, карточка FIX-B01–B03 редакции 2.0, текущий код и тесты.
- Не найдено: последующих изменений `origin/main` после `f4af7be`; отдельной
  репозиторной карточки FIX-B01/B02 до этой задачи не было.
- Решение владельца: закрытая AS/tester trace не выдаётся участнику; ключ
  операции не является авторизацией; тот же ключ и иной payload дают conflict.
- Стоп-условия: все восемь — нет. Публичный API сужается безопасной проекцией
  без удаления внутренней диагностики; схема и сохранённые данные не меняются.
- Требуется решение владельца: нет.

## План и состояние

- Завершено: проверены archive manifest и актуальность `origin/main`.
- Активный шаг: безопасная проекция и owner-bound idempotency.
- Следующий шаг: адресные unit/HTTP/integration проверки, затем полный локальный
  минимум и отдельный PR.
- Ветка: `codex/fix-preparation-api-security`.

## Ограничения и риски

- Совместимость: сохраняются `operation_id`, `status` и успешный participant
  `result`; внутренние `error_message`, tester и candidate становятся недоступны.
- Данные и миграции: миграция не нужна; глобальная уникальность `operation_id`
  сохраняется.
- Безопасность: ответы используют whitelist; чужой ключ не возвращает статус
  или результат.
- Внешние сервисы/LLM: не вызываются в стандартных тестах.
- Производительность: сохраняется advisory lock пользователя и существующий
  индекс уникальности ключа.

## Критерии приёмки

- [x] Failed/queued/running/completed ответы содержат только публичные поля.
- [x] Candidate, tester trace, criteria и сырые provider/exception сообщения не
  попадают в participant API.
- [x] Повтор своего ключа с тем же payload возвращает тот же результат; другой
  payload даёт контролируемый conflict.
- [x] Чужой ключ не возвращает данные ни через POST, ни через GET.
- [x] Разные активные запросы одного пользователя с разным payload не
  объединяются молча.
- [x] Внутренний `result_json` failed-операции сохраняется для диагностики.

## План проверки

- `git diff --check`.
- Адресные unit/HTTP-тесты публичной проекции и прав.
- PostgreSQL integration очереди на изолированной БД `test`/`pytest`.
- `npm run test:backend`, `npm run test:backend:http`; обязательный CI точного
  head перед слиянием.

## Откат

Revert PR возвращает предыдущую маршрутизацию без изменения таблицы и данных.
При аварийном откате диагностические поля остаются закрытыми; небезопасную
публичную выдачу не включать как fallback.

## Передача результата агентом

### Результат

Добавлена единая whitelist-проекция публичного состояния операции. Внутренние
`result_json`, tester trace и сырые ошибки не выдаются при `failed`. Enqueue
сначала сериализуется по глобальному `operation_id`, затем проверяет владельца и
checksum; активные операции одного пользователя объединяются только при полном
совпадении канонического запроса.

### Изменённые файлы

- `Api/product_cycle_preparation_queue.py` — owner-bound idempotency, глобальная
  advisory-блокировка ключа, owned read и публичная проекция.
- `Api/routes.py` — применение публичной проекции и контролируемые HTTP 403/409.
- `web/js/product-cycle-preparation.js` — клиент читает только новый безопасный
  контракт `result` / `error.message`, без внутренних `result_json` и
  `error_message`.
- `tests/unit/test_product_cycle_preparation_projection.py` — whitelist статусов.
- `tests/e2e/test_m5_runtime_http.py` — отсутствие закрытых маркеров и HTTP права.
- `tests/integration/test_m10_product_path_db.py` — replay/conflict/owner/scope в PostgreSQL.

### Проверки

- `pytest tests/unit/test_product_cycle_preparation_projection.py tests/e2e/test_m5_runtime_http.py -q` → 12 passed.
- `pytest -m 'not integration and not e2e and not llm' -q` → 537 passed, 222 deselected.
- `pytest -m e2e tests/e2e -q` → 68 passed, 11 deselected.
- адресный integration-тест на PostgreSQL 16 `fix_b01_b02_pytest` → 1 passed.
- `git diff --check` → PASS; `py_compile` изменённых Python-файлов → PASS.
- `prepare_release.py patch --dry-run` → `2.0.16 → 2.0.17`; кандидат
  `2.0.17` подготовлен штатным скриптом.
- `npm run build:web` → PASS; `npm run lint:js` → PASS;
  `node --test tests/frontend/*.test.mjs` → 74 passed.
- После release bump CI обнаружил опубликованную high-уязвимость
  `GHSA-mrhx-c7xc-m3w5` в транзитивном `zod 4.4.3`; оба lockfile обновлены до
  `zod 4.6.7`. `npm audit --audit-level=high` → 0 vulnerabilities.

### Непроверенное

- Полный integration-набор: первый прогон остановился на конфигурации
  clean-bootstrap maintenance DB; повтор с `STAND_ADMIN_URL=.../postgres` не
  вернул итоговую сводку в доступное окно. Адресная DB-регрессия выполнена.
- Первый CI head `4e7b8cd` подтвердил обязательность release bump и ожидаемо
  остановил frontend: `Product changed but release version remains 2.0.16`.
  Следующий head `346f791` прошёл release check, но остановился на новой
  advisory для `zod`; lockfile-исправление подготовлено в том же PR. Полный
  browser CI на `bec8001` выявил несовместимость клиента с новой публичной
  проекцией: polling продолжал читать внутреннее `result_json`. Клиент переведён
  на `result` / `error.message`; точный повтор browser и итоговый CI ожидаются.
  Human review и merge не выполнены.

### Риски и откат

Схема и данные не менялись. Совместимость успешного `result` сохранена; публичные
диагностические поля намеренно удалены. Откат — revert commit, но небезопасную
проекцию failed-операции повторно не включать.

### Следующий минимальный шаг

Отправить lockfile-исправление в PR #103, дождаться обязательных CI/review;
затем перейти к ARCH-A01 в новой ветке от обновлённого `main`.
