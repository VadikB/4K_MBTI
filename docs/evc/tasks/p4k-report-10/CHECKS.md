# CHECKS — P4K-REPORT-10

Основание: `TASK.md`; тестовые данные синтетические. Локальная PostgreSQL 15 запущена отдельно на `localhost:55440`, пустая БД `agent4k_pytest` на этой инстанции. Это не БД разработчика и не общий test-контур. CI использует PostgreSQL 16.

| Проверка | Итог |
| --- | --- |
| `PYTHONPATH=. .venv/bin/python -m pytest -q tests/unit/test_m8_pdf_export.py tests/unit/test_m8_results.py tests/unit/test_m8_report_comparison.py` | PASS: 51. Реальные PDF bytes, текст, page count, ноль/пропуск, partial, correction, comparison, unsupported model, Typst failure/timeout и убийство группы процессов. |
| `TEST_DATABASE_URL=… STAND_ADMIN_URL=… .venv/bin/python -m pytest --run-integration -q tests/integration/test_integrated_acceptance_db.py tests/integration/test_m8_recommendation_basis_db.py tests/integration/test_m8_report_access_db.py` | PASS: 14 после переноса макета в `v2`. Настоящий C-67 → HTTP PDF/text, ACL, 503/retry. |
| `TEST_DATABASE_URL=… STAND_ADMIN_URL=… .venv/bin/python -m pytest --run-integration -q tests/integration/test_m10_product_path_db.py tests/integration/test_m6_evidence_db.py tests/integration/test_m6_substantive_admission_db.py tests/integration/test_preparation_observation_db.py` | PASS: 61 после переноса `v2`. |
| `npm run test:backend:http` | PASS: 193, 15 deselected. |
| `node --test tests/frontend/*.test.mjs` | PASS: 364. |
| `npm run lint:js` | PASS. |
| `npm run ready:prepare -- --base-ref origin/main --candidate 2.1.25` | PASS; release 2.1.25, web build и preflight. |
| `npx playwright test tests/browser/report10-pdf.spec.mjs --reporter=line` | PASS: 1, Chromium. Кнопки owner/customer, 503 и повтор. |
| `git diff --check` | PASS. |
| Полный `npm run test:backend` на стабильном коде | PASS: 1209, 645 deselected, 1 warning (Starlette deprecation). |
| Полный `TEST_DATABASE_URL=… STAND_ADMIN_URL=… npm run test:backend:integration` на изолированной `agent4k_pytest` | PASS: 446, 2 SKIP (real LLM), 1405 deselected, 1 warning (Starlette deprecation). |
| CI точного PR head | NOT_RUN до push/PR. |

Реальные PDF и отрендеренные страницы (10 сценариев): `evidence/normal`, `partial`, `unscored`, `empty`, `long` (2 страницы), `comparison-limited`, `comparison-separate`, `corrected`, а также `radar-full` и `radar-gap` (`.pdf` и `.png`; для вторых страниц `*-page-2.png`). Сверены имена программы, даты, исходы, числа, сообщения, ограничения и разрешённые объяснения; нет `0%`, служебных revision и raw coverage. Визуальный просмотр: кириллица и кольца 0–3 читаются, длинный текст не обрезан, пустой отчёт и несопоставимое сравнение не рисуют вымышленных линий, лишних пустых страниц нет.

Промежуточные сбои: первый backend-прогон дал 9 FAIL из-за запрета sandbox на `ps`; отдельный повтор 19 тестов `test_synthetic_limits` с процессным доступом PASS. Первый полный integration использовал Unix socket, тогда как часть старых owned-stand fixtures требует явный `localhost` URL и БД `agent4k_pytest`; второй полный прогон запущен во время переноса шаблонов и прочитал `v1` с новым payload. Все 16 затронутых сценариев после переноса повторены адресными наборами выше и PASS. Финальные полные наборы PASS. После последних печатных уточнений адресные PDF unit-тесты повторены; обязательный CI проверит точный PR head. Первый browser запуск без сетевого разрешения получил `listen EPERM`; повтор с локальным preview PASS.

Не запускались реальные LLM, письма, production/test данные. Локальные проверки не заменяют обязательный CI и человеческую приёмку.
