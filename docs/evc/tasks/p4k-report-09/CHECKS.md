# CHECKS — P4K-REPORT-09

| Критерий | Локальное доказательство | Статус |
| --- | --- | --- |
| AC01: адресный кандидат, права, причина и источник | `tests/e2e/test_p4k_report_09_correction_http.py`, `tests/integration/test_p4k_report_09_correction_db.py` | PASS |
| AC02: повтор, конкуренция, stale expected, откат | Реальная изолированная PostgreSQL: 4 адресных integration-теста, включая два конкурирующих writer и отказ pointer trigger | PASS |
| AC03: оригинал, protected diff, одна строка истории | Те же integration + HTTP public projection; старый C-67 равен снимку | PASS |
| AC04: объяснение без смены Results, расчёт только с сохранённой C-56 | Отдельные fixture в `test_p4k_report_09_correction_db.py`; новая генерация оценки не вызывается | PASS |
| AC05: список/радар/сравнение/PDF и старый экран | PostgreSQL проверяет указатель в истории, админском списке и автосравнении даже после более поздней технической редакции; browser REPORT-04/05/06/08/09: 11 PASS; новый сценарий 1440/390, `evidence/correction-{1440,390}.png` | PASS локально |

Релизный кандидат `2.1.24`: `npm run ready:prepare -- --base-ref origin/main --candidate 2.1.24` PASS; `npm run build:web` PASS; `npm run test:backend` 1195 PASS / 644 deselected; `npm run test:backend:http` 193 PASS / 15 deselected; `node --test tests/frontend/*.test.mjs` 364 PASS; `npm run lint:js` PASS; Chromium REPORT-04/05/06/08/09 — 11 PASS, финальный REPORT-09 — 1 PASS и снимки 1440/390 после релизной сборки. Полный `npm run test:backend:integration` на итоговом коде и отдельной PostgreSQL `agent4k_pytest`: 439 PASS / 9 SKIP / 1392 deselected. SKIP: 7 тестов требуют отдельный `STAND_ADMIN_URL`, 2 — реальный LLM. Реальные LLM/письма и production/test данные не использовались. `git diff --check` PASS. Обязательный CI точного PR head и человеческая приёмка ещё не выполнены.

Промежуточные сбои локального контура устранены и повторены полными наборами: первоначальный backend запуск получил 9 FAIL из-за запрета системного `ps` в песочнице; после разрешения команды полный набор PASS. Первоначальный integration на Unix socket не удовлетворял контракту старых fixture (`localhost`, явный пользователь, имя БД с `pytest`); на совместимом изолированном контуре полный набор PASS. Первый HTTP запуск выявил устаревший fake connection REPORT-08; после исправления полный HTTP набор PASS.
