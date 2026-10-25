# ARCH-A03 — transaction phases, fencing и восстановление PM-03

## Основание и результат

- Пакет `P4K_Case_AS_Cycle_Plan_2026-10-23`, редакция 2.0, карточка
  `06_A03_A04_A07_Dependencies.txt`.
- Base: `main@f7707bc1fdb9bbe9a17c5a50eec2a3a5b11aa7ae`, приложение `2.0.24`.
- FIX-M10 из PR #104 сохраняется как отдельная закрытая регрессия порядка
  блокировок `Cycle → AS`; он не объявляется полным A03.
- Результат задачи: операции PM-03 имеют уникальный fence каждой попытки,
  heartbeat lease, проверку актуальности перед attach/final commit и повторное
  чтение decision/Cycle после row lock. Поздняя попытка не может перезаписать
  результат новой попытки или добавить AS в закрытый Cycle.

## Границы и решения

- Включено: `product_cycle_preparation_operations`, claim/heartbeat/requeue,
  functional provider boundary, attach и final commit, crash/retry concurrency.
- Не включено: изменение смысла planner, пакетов A01/A04/A07, методологии,
  Reliability и исторических результатов.
- Снимок запроса и зависимостей формируется до внешнего I/O; provider вызывается
  без открытого connection-контекста очереди. Перед предметной записью worker
  блокирует строку операции и подтверждает `attempt_token`.
- Gateway-level освобождение соединения теперь fail-closed: transport освобождает
  только idle lease без commit; при активной transaction получает
  `EXTERNAL_IO_REQUIRES_CLOSED_DATABASE_TRANSACTION`. Поэтому transport не может
  фиксировать или откатывать предметную transaction вызывающего кода.

## Стоп-условия

- Схема расширяется совместимым nullable `attempt_token UUID`; удаление данных
  и миграция существующих значений не нужны.
- Публичный API не меняется; token никогда не попадает в participant projection.
- Предметных решений нет: изменение относится к orchestration/DB ownership.
- Откат: revert PR; колонка может остаться nullable и не влияет на старый код.

## Критерии приёмки

- [x] Две попытки одного operation имеют разные fence; поздний ответ старой
  попытки не выполняет attach/final/failure commit.
- [x] Heartbeat не позволяет reclaim живого worker при долгой серии provider calls.
- [x] Crash до provider, после provider и после committed attach восстанавливается
  новой попыткой без двух AS.
- [x] Закрытие Cycle во время provider call приводит к `M7_COLLECTION_CLOSED`;
  поздний response не добавляет AS/Turn.
- [x] Decision после ожидания row lock читается повторно и видит существующий attach.
- [x] Во время внешнего I/O нет открытой предметной transaction/row lock;
  PostgreSQL evidence включает `pg_stat_activity`/`pg_locks` и timestamps.
- [x] Gateway не commit/rollback предметную транзакцию вызывающего кода.

## План проверки

- Unit: fence и lock/re-read порядок.
- PostgreSQL integration: два worker, lease expiry/late response, три crash points,
  concurrent Cycle close, idempotent attach и lock observation.
- Полные backend/HTTP/integration проверки по EVC matrix; CI exact head и human review.
- Real provider не требуется для concurrency semantics; controlled blocking gateway
  используется для воспроизводимых временных границ.

## Состояние

- Реализованы attempt fencing, heartbeat, guarded attach/final/failure commit,
  Cycle recheck и fail-closed transaction boundary transport-а.
- PostgreSQL подтвердил три crash/reclaim точки, fence старой попытки, обновление heartbeat до reclaim,
  отсутствие удерживаемой строки/`idle in transaction` во время controlled
  provider calls и отбрасывание provider response после закрытия Cycle.
- Технический A03 PASS не означает AI tester, методологическую приёмку или
  Reliability: эти статусы остаются отдельными воротами пакета.
