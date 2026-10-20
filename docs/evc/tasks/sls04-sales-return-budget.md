# SLS04: бюджет Sales Cycle и возврат R1

## Основание и результат

- Источник: `P4K_Sales_04_Return.txt`, редакция 2 от 19.10.2026; решения владельца
  от 18–19.10.2026.
- Правило: новые Sales Cycles получают опубликованный program revision с бюджетом
  `7200` секунд и окном `259200` секунд; возврат всегда продолжает ту же незавершённую
  AS только после явного Continue.
- Контракты: PM-04, C-24/C-45/C-46, T10; M7 v1.3 и Change 01.

## Границы

- Глобальный method default `3600` не меняется.
- Presence lease остаётся `120` секунд, heartbeat — `10` секунд.
- Старый QA snapshot v1.2 и начатые Cycles не переписываются.
- Реальные organization/configuration/actor ID не хранятся в Git.
- Provider эквивалентных замен не используется политикой R1.

## Реализация и эксплуатация

- Новый immutable package: `assessment_definitions/planning/m7_return_integration/v2`.
- Assessment-план сохраняет version/checksum политики; QA продолжает читать v1.2.
- Повтор идентичной публикации program revision возвращает существующую ревизию.
- Операторская команда сначала запускается без `--apply`, затем с ним:

  `python scripts/configure_sales_pilot_timing.py --organization-id ID --configuration-id ID --actor-id ID [--apply]`

  Команда проверяет область, показывает dry-run и после применения печатает read-back
  без секретов. Audit обеспечен `created_by`, `published_at`, revision и checksum.

## Проверки и откат

- Unit: формат/checksum и допуск v1.2/v2.0.
- Integration: приоритет program revision, `7200`, snapshot начатого Cycle,
  идемпотентность публикации, lease/Continue и сохранение AS.
- Frontend: карточка возврата и блокировка ввода до Continue.
- Откат: прекратить новые назначения с program revision; опубликовать следующую
  совместимую program revision. Уже начатые Cycles завершаются по snapshot.

## Фактическая проверка перед PR

- `pytest -m 'not integration and not e2e and not llm'`: PASS, 467 тестов.
- `pytest -m e2e tests/e2e/test_m5_runtime_http.py`: PASS, 8 тестов.
- Адресные PostgreSQL integration для R1 и program revision: PASS, 2 теста;
  остальные тесты двух затронутых модулей в предыдущем полном прогоне: 31 PASS,
  один fixture FAIL, после исправления именно он повторён и PASS.
- `node --test tests/frontend/*.test.mjs`: PASS, 65 тестов.
- `npm run lint:js`, `npm run build:web`, `git diff --check`: PASS.
- Реальные organization/configuration/actor ID и применение program revision:
  NOT_RUN до test-deploy; команда намеренно требует явные ID.
- Authenticated visual smoke: NOT_RUN локально; требуется опубликованный test.
