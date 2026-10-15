# UX-W02 — знакомство и готовность к оценке

## Контекст и границы

- Задание: `UX-W02_Acquaintance_2026-10-15.txt`, редакция 1.4.
- Справочный анализ: `P4K_Case_Return_Impact_Review_2026-10-15.txt`, редакция 1.1.
- База реализации: `origin/main` `adae595784c919795b8953f91314dc94208dc5f3`, версия 2.1.33.
- Специальная замена незавершённой AS после 180 секунд (P01–P03) не входит в W02.
- На базе реализации отсутствует утверждённый источник participant-facing цели и
  получателей результатов из R04. Ранний допуск не подменяет его `invitation_intro`:
  зависимое состояние возвращает ожидание и точные причины.

## Прочитанные источники

`README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
`docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`,
`docs/evc/review-checklist.md`, `docs/evc/task-template.md`,
`docs/architecture/product-4k/1.0/context.md`,
`docs/architecture/product-4k/registry.md`, Change 01 и его manifest,
ADR-002, `docs/evc/change01-traceability.md`, M7 v1.3 §§5.3–5.5,
затронутые backend/frontend контракты и тесты.

## Связь и решения

| Правило | Контракт/владение | Реализация | Проверка |
|---|---|---|---|
| Ранний допуск не зависит от M4 и ответов | membership + подтверждённые participant-facing сведения организации | отдельная server-side acquaintance readiness | unit + HTTP/integration |
| Ответы сохраняются до готовности M4 | UserContext принадлежит участнику | отдельное подтверждение UserContext, идемпотентная история знакомства | integration + HTTP |
| Поздний допуск использует frozen M4 и план | M4/M5/M7 | prepare без presentation, start с повторной readiness | integration + HTTP |
| До явного старта время не идёт | M7 Cycle/Session | Cycle/Session остаются `prepared`, `started_at/deadline` отсутствуют | integration |
| UI не придумывает числа и состояние | read model подготовленного плана | количество/бюджеты только из persisted plan/cycle | browser |

## План

1. Добавить серверные read/write-контракты знакомства, ранней/поздней готовности и
   сообщения о неточности с организационной изоляцией.
2. Разделить `prepare` и явный `start` существующего M10/M7 lifecycle.
3. Перевести journey и текущий onboarding на серверные этапы, сохранив reload/login.
4. Добавить регрессии, выполнить локальный минимум, review и обязательный CI.

## Совместимость и откат

Изменения аддитивны: существующие M4 snapshots, Cycle, Session, согласия и ответы не
переписываются. Уже начатые циклы продолжаются по frozen состоянию. Откат — revert PR;
новые таблицы/колонки можно оставить неиспользуемыми, уничтожение данных не требуется.

## Результат проверок

- `py_compile Api/m10_product_flow.py Api/m10_contracts.py Api/routes.py` — PASS.
- `node --check web/js/screens/interview.js` — PASS.
- `pytest tests/unit/test_user_journey.py -q` — PASS, 5 passed.
- адресный PostgreSQL integration prepare/start — PASS, 1 passed.
- полный `test_m10_product_path_db.py` — FAIL в существующей downstream-цепочке:
  после evidence worker не создаётся assessment request; адресная prepare/start
  регрессия проходит, причина не связана с новым таймерным стыком и требует
  отдельной диагностики до слияния.
- реальные iOS/Android/Windows/macOS браузеры — NOT_RUN.

## Стоп-условие

В `origin/main` и удалённых ветках отсутствует R04 и утверждённый participant-facing
источник цели оценки и получателей/правил доступа. `organizations.invitation_intro`
не используется как подмена: это прямо запрещено заданием. Поэтому зависимые ранняя
readiness, экран знакомства и сквозные сценарии 1–10 не могут быть объявлены
реализованными или отправлены в main. Независимый prepare/start-контур сохранён в
рабочей ветке; PR не создаётся до появления источника и зелёной полной проверки.
