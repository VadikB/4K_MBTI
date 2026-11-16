# Проверки P4K-REPORT-01

База `2afcc379`; tested SHA до коммита — рабочий diff PATCH-кандидата 2.1.12. Все DB
проверки: собственный `p4k_report01_pytest` на локальном PostgreSQL 15,
`PYTHON_DOTENV_DISABLED=1`, без реальных LLM и писем. Результаты ниже
относятся к указанному коду; CI на будущем commit ещё не выполнялся.

| Критерий | Статус | Доказательство и предел |
| --- | --- | --- |
| AC01 закрытие → Results/Report → открытие | PASS local | `tests/browser/runtime.spec.mjs` S10-A на 2.1.12, controlled gateway, 1 worker, retries=0; saved JSON/PDF и открытый экран. Не живое качество объяснения. |
| AC02 обрыв после Results/Report, повтор, конкурентные worker | PASS local | `tests/integration/test_m10_product_path_db.py`: `test_restart_after_results_commit_finishes_one_report`, `test_restart_after_report_commit_reconciles_pipeline_without_generation`, `test_concurrent_workers_do_not_generate_second_report`, `test_concurrent_direct_report_publication_keeps_one_assessee_report`; IDs/checksums/число строк. Реальный kill процесса и истечение lease не воспроизводились. |
| AC03 ошибка Report и служебное восстановление без M6 | PASS local | `test_report_failure_recovers_saved_results_without_recalculation`: прежние calculation ID/C56 hash и Results ID/payload hash; M6 повторный вызов запрещён тестом. Сбой после записи C-67 защищён idempotency key, отдельный power-loss не воспроизводился. |
| AC04 повторное чтение и запрет regenerate | PARTIAL | HTTP `tests/e2e/test_m6_evidence_http.py` и `test_m10_processing_recovery_http.py` 11 PASS; прямой regenerate 404 и админ организации 403. Isolated history readback в `test_profile_to_m4_owned_stand.py` PASS. Полный аудит SQL writes/DDL на каждом GET не выполнялся. |
| AC05 экран 1440/390, возврат | PASS local | Controlled browser S10-A на 2.1.12: waiting/ready на серверном пути, failed/offline через сетевые fixtures; 8 снимков в `evidence/`. Горизонтальный overflow отсутствует на 320/390/720. 720 CSS px моделирует 1440 при 200% масштабе, отдельная настройка браузерного zoom не применялась. |
| Frontend | PASS local | `node --test tests/frontend/*.test.mjs` 334 PASS после PATCH; `npm run lint:js` PASS; `ready:prepare` и `npm run build:web` PASS. |
| Unit | PASS local | `npm run test:backend` 1117 PASS после повторного запуска вне sandbox, где тестам нужен `ps`; `test_release_version.py` 11 PASS после PATCH. Первый sandbox-прогон: 9 FAIL из-за запрета `ps`, остальные 1108 PASS. |
| Integration потребителей | PASS local | Полный `test:backend:integration`: 393 PASS, 25 setup ERROR из-за жёсткого допустимого имени DB в legacy `EXEC-FIX-02` fixture; эти 25 повторены отдельно на собственной `agent4k_pytest`: 25 PASS. M10: 23 PASS в полном модуле, исправленный новый сценарий повторён отдельно 1 PASS; M6 substantive/history 7 PASS, M4 owned stand 1 PASS. Полный прогон не был единым зелёным запуском. |
| PDF | PASS local | `scripts/verify_browser_pdf.py` сравнил текст с C-67; Poppler: 4 страницы A4, все страницы отрендерены и просмотрены без обрезки. Доказательство обновлено после browser на 2.1.12. Содержание synthetic, без реального LLM. |
| Diff/CI | PARTIAL | `git diff --check` PASS до коммита; обязательные PR jobs `frontend`, `pytest`, `full-verification` NOT_RUN без PR. |

Снимки и PDF созданы на synthetic fixture; они не являются доказательством
методологической валидности и не содержат production-данных.
