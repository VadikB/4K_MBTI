# Проверки P4K-REPORT-03

Рабочая ветка `codex/p4k-report-03`; база `a37a4519`; кандидат `2.1.15`.
Тесты используют только синтетические данные. PostgreSQL принадлежит этой задаче:
`/private/tmp/p4k-report03-pg-20261116`, `127.0.0.1:55433`, база
`p4k_report03_pytest`; один worker, retries=0, LLM=0, почта=0.

| Критерий | Статус | Доказательство и предел |
| --- | --- | --- |
| AC01 четыре исхода, 3/3 и 2/3, ноль, техническая ошибка | PASS адресно | `tests/unit/test_m8_results.py`, `test_m8_report_comparison.py`; browser `report03-outcomes.spec.mjs`. Таблица ожидаемых текстов — `TASK.md`. |
| AC02 неизменность C-56/чисел M6 | PASS адресно | Исходный `score` копируется без перерасчёта; `tests/integration/test_integrated_acceptance_db.py` проверяет 0, 1.75, 1.5 и `null`. |
| AC03 запись/чтение Report, HTTP и PDF | PASS адресно | Integration `test_four_saved_outcomes_and_ai_independent_read` (5 вариантов) и извлечение текста PDF через pypdf. Единый сохранённый C-67; рендер первой страницы отдельного синтетического PDF визуально проверен; артефакт `/private/tmp/p4k-report03-example.pdf`, скрин `/private/tmp/p4k-report03-example-page1.png`. |
| AC04 frozen план | PASS адресно | Unit проверяет 3/3, 2/3, route positions и сохранённую `plan_revision_id`; не читает актуальный каталог. Динамическая замена программы после прохождения не проверялась отдельным DB-тестом. |
| AC05 сопоставимость по навыку | PASS адресно | `test_incomplete_cycle_uses_saved_skill_relevance_not_global_prohibition`: отсутствие глобального запрета, `remaining_plan_relevant` true/false/unknown. REPORT-07 определяет дальнейшую полную матрицу. |
| Визуальная проверка | PASS адресно | Реальные действия Playwright: 1440/390/320 px и увеличение корневого текста 200% на 390 px; 2 passed, screenshots `evidence/report-scope-1440.png`, `report-scope-390.png`. Это проверка увеличенного текста, а не измерение браузерного zoom; полная компоновка — REPORT-04/05. |
| Предметный пакет | PASS | `m8_basic_report/1.5.0` draft, SHA-256 `template.json` совпадает с manifest; прежний `1.4.1` не изменён. |
| Release preflight | PASS | `npm run ready:prepare -- --candidate 2.1.15` на `origin/main=a37a4519`; `web/dist` собран. |
| Backend | PASS | `npm run test:backend`: 1126 passed, 602 deselected, код/версия 2.1.15; `/private/tmp/p4k-report03-backend-2.1.15.log`. Первый sandbox-прогон процессных тестов дал PermissionError; штатный прогон с доступом к собственным процессам PASS. |
| HTTP | PASS | `npm run test:backend:http`: 175 passed, 15 deselected; `/private/tmp/p4k-report03-http-2.1.15.log`. |
| Frontend | PASS | `node --test tests/frontend/*.test.mjs`: 343 passed; `/private/tmp/p4k-report03-frontend-2.1.15.log`. |
| Integration | PASS адресно | `TEST_DATABASE_URL=… .venv/bin/python -m pytest -q --run-integration ...`: 8 passed, 21 deselected; `/private/tmp/p4k-report03-integration-2.1.15.log`. Полный integration-набор остаётся за обязательным CI. |
| JS lint / сборка / diff | PASS | `npm run lint:js`, `npm run build:web` в `ready:prepare`, `git diff --check`; на рабочем дереве release кандидата. |
| Push / PR / CI / TEST / Prod | NOT_RUN | Auto-review отклонил `git push -u origin codex/p4k-report-03`: публикация приватного кода и артефактов на GitHub не подтверждена явным разрешением или доказанным доверенным назначением remote. Повтор через иной инструмент запрещён; `gh auth status` также показывает отсутствие входа. Обязательные CI jobs и release deploy отсутствуют; локальные результаты их не заменяют. |

## Восстановление

Схема БД и опубликованные исторические Results/Reports не меняются. При откате
вернуть предыдущий release и его default dependency; новый draft `1.5.0`
останется файлом, старый `1.4.1` и frozen manifests сохранены.
Собственный PostgreSQL остановлен (`pg_isready 127.0.0.1:55433` — no response);
локальный preview завершён после browser-тестов.
