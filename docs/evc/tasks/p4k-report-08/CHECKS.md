# CHECKS — P4K-REPORT-08

| Критерий | Статус | Доказательство / предел |
| --- | --- | --- |
| AC01: один Cycle, фильтры и страницы | PASS | `tests/integration/test_m8_report_access_db.py`: 3 PASS на локальной изолированной `p4k_report08_pytest`; latest revision, два статуса без Report, поиск/программа/статус, total и page. |
| AC02: текущий админ и историческая организация | PASS | Та же PostgreSQL integration: новый admin читает старый Cycle после снятия участника, снятый/чужой отказ; HTTP detail/PDF перепроверяет membership. |
| AC03: точный detail/PDF, возврат и смена организации | PASS | `tests/e2e/test_m8_report_access_http.py`: 2 PASS; `tests/browser/report08-admin.spec.mjs`: 1 PASS, фильтр→открытие→назад, смена организации и поздний ответ. PDF и customer projection используют сохранённый M8. |
| AC04: legacy не действует | PASS | Карта `LEGACY_MAP.md`; HTTP `410` старым GET/POST и личному legacy PDF; удалены routes/builders/exports/entries/assets; `node --test tests/frontend/*.test.mjs`: 354 PASS. |
| AC05: список 1440/390 | PASS локально | `evidence/list-1440.png`, `evidence/list-390.png`; browser подтверждает отсутствие горизонтального скролла 390. Человеческая визуальная приёмка новой композиции остаётся у владельца. |

Дополнительно: unit `1133 PASS, 606 deselected` (системный `ps` разрешён только для локальных тестов); REPORT_04–06 browser `9 PASS`; `npm run lint:js` PASS; `npm run ready:prepare -- --base-ref main --candidate 2.1.21` PASS; `git diff --check` PASS. `npm run lint:dead` FAIL из-за существующих конфигурационных/исторических предупреждений (`knip`); новые runtime imports проверены сборкой и ESLint. Реальные LLM/письма не запускались. Обязательный CI актуального PR остаётся отдельным gate.
