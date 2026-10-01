# T08.2 — целостность snapshot исполнения

## Результат

Начатая assessment-сессия, задание очереди и M5 Assessment Situation исполняются
только по сохранённому и проверенному snapshot. Повреждённый, неподдерживаемый или
относящийся к другому объекту snapshot завершается технической ошибкой без fallback
на текущую конфигурацию.

## Область

- Включено: общий verified reader, legacy assessment session, preparation queue,
  M5 AS/execution payload/C-45, DB-защита snapshot, тесты и диагностические коды.
- Не входит: фактическая идентификация вызова LLM (Task 7); Cycle foundation и
  calculation snapshot до появления принятого контракта Task 5; production deploy.

## Контекст

- Основание: запрос владельца от 2026-10-01 и
  `Product_4K_Task_6_T08_2_Snapshot_Integrity_2026-10-01.txt`.
- Значимые точки входа: `assessment_runtime`, `assessment_preparation_queue`,
  `assessment_service`, `m5_storage`, `m5_scenario_runtime`, `database`.
- Архитектура: `docs/architecture/product-4k/1.0/context.md`, M1 v1.4,
  `docs/architecture/product-4k/registry.md`, `docs/adr/002-cycle-as-dialogue-contracts.md`.
- Контракты и проверки: `docs/evc/artifact-recipe.md`,
  `docs/evc/verification-matrix.md`, существующие unit/integration/HTTP-тесты.
- Архитектурный адрес: техническая целостность входов PM-03/PM-04 и передачи C-45;
  предметное содержание и правила оценки не меняются.
- Предметные артефакты: существующие опубликованные methodology/scenario/prompt,
  M4 profile и M5 package; новые предметные значения не вводятся.

## Источники и решения

- Прочитано: указанный Task 6; `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  рабочий цикл, матрица проверок, рецепт артефактов, Registry/context, код и тесты
  затронутых runtime-путей. Исходный commit: `e00513d`.
- Не найдено: реализация Task 5 Cycle/Session и calculation snapshot. Это блокирует
  только зависимую часть Task 6.
- M1 v1.4 — понятийный FROZEN/CURRENT=NO источник; M2–M5 имеют runtime-пакеты;
  M6–M8 не объявляются реализованными.
- Решение: реализовать независимую техническую часть → владелец продукта → команда
  «делай» от 2026-10-01 → текущая задача без изменения предметной нормы.
- Стоп-условия: изменение смысла — нет; публичная совместимость — старые записи без
  доказуемого checksum честно отклоняются, как явно задано Task 6; миграция данных —
  нет; новый предметный формат — нет; секреты/права — нет; откат описан ниже;
  Cycle/calculation — да, ожидает Task 5.
- Требуется решение владельца: нет для текущей области.

## План и состояние

- Завершено: разведка; verified reader; owner/checksum/format validation;
  защита session/queue/M5; удаление backfill; unit, HTTP и PostgreSQL integration.
- Активный шаг: commit, PR и обязательный CI.
- Следующий шаг: после merge выполнить стендовую A/B/restart/readback-проверку.
- Ветка: `codex/t08-2-snapshot-integrity` от `origin/main` (`e00513d`).

## Ограничения и риски

- Совместимость: по решению владельца обратная совместимость не требуется;
  запись без integrity envelope/checksum не исполняется и не адаптируется.
- Данные: массового backfill и переписывания snapshot нет.
- Безопасность: snapshot не содержит секретов; тесты не используют рабочую БД.
- LLM: реальные вызовы не входят в стандартную проверку.
- Эксплуатация: повреждённая queue job должна завершаться машинной ошибкой, а не
  бесконечно повторяться.

## Критерии приёмки

- [x] Session и queue проверяют checksum, schema, формат и owner до исполнения.
- [x] Нет fallback/backfill исторического snapshot текущей default-конфигурацией.
- [x] M5 проверяет checksum, owner/composition и точные зависимости.
- [x] C-45 фиксирует проверенную границу и не принимает повреждённый AS.
- [x] DB запрещает изменение неизменяемых snapshot и используемых дочерних Case.
- [x] Ошибки имеют стабильные машинные коды и не становятся результатом оценки.
- [x] Новое предметное содержание не встроено в исходный код или генератор пакета.
- [x] Проверены потребители и неизменность исторических снимков.

## План проверки

- `git diff --check`.
- Адресные unit-тесты snapshot integrity.
- `npm run test:backend`.
- `npm run test:backend:http`.
- `TEST_DATABASE_URL=… npm run test:backend:integration` на изолированной БД.
- GitHub CI `frontend` и `pytest`; после merge — A/B/restart/readback на test.

## Откат

Revert PR возвращает прежний reader и DB-функции. Изменение не переписывает
исторические snapshots и не удаляет данные; новые диагностические поля допускают
сохранение до отдельной очищающей миграции.

## Передача результата агентом

### Результат

Добавлен единый строгий reader execution snapshot. Новые snapshots получают
версионированный integrity envelope и owner пользователя. Session runtime, обе
очереди, диалог, evaluators, M3 binding и shadow batch читают только проверенные
данные. M5 дополнительно проверяет AS owner, execution payload, CaseVersion и
PersonalizedProfile. Startup-backfill удалён. Snapshot без envelope не адаптируется.

### Изменённые файлы

- `Api/snapshot_integrity.py` — формат, checksum, owner и машинные ошибки.
- `Api/assessment_*`, `Api/communication_agent.py` — verified consumers и очереди.
- `Api/m5_scenario_runtime.py`, `Api/database.py` — M5 composition и DB-защита.
- `tests/unit`, `tests/integration` — tamper, wrong-owner и регрессия runtime.

### Проверки

- `git diff --check` → passed.
- `npm run test:backend` → 231 passed.
- `npm run test:backend:http` → 22 passed.
- `TEST_DATABASE_URL=postgresql://pytest:***@127.0.0.1:55432/agent4k_pytest npm run test:backend:integration`
  → 32 passed на временном PostgreSQL 16; контейнер удалён.

### Непроверенное

- GitHub CI ожидает push/PR.
- A/B publication, worker restart и DB readback на test выполняются после merge.
- Cycle foundation/calculation snapshot ожидают контракт Task 5; в этой ветке его нет.
- Фактическая идентичность provider/model относится к Task 7.

### Риски и откат

- Старые session snapshots без нового envelope перестанут исполняться; это принятое
  владельцем несовместимое поведение, без массовой миграции и fallback.
- Revert PR возвращает прежнее чтение; сохранённые данные не удаляются.

### Следующий минимальный шаг

Commit/push/PR, успешные `frontend`/`pytest`, merge и test A/B/restart/readback.

### Открытые вопросы

Нет для текущей области. Cycle/calculation остаётся зависимостью Task 5.
