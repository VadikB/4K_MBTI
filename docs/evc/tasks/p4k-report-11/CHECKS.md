# CHECKS — P4K-REPORT-11

База итогового прогона: `fffd501a51cae673a4e0ee87ec5d6cbc83069e21` (main,
2.1.26). Предыдущая база `02596d7` была заменена после #241; её результаты
сохранены как диагностика. `PASS` означает только указанную синтетическую проверку.
PR #242, первый head `b769055478df0e8fba9a637e2bf65af0fea8a0fe`.
Его обязательный CI выявил описанный ниже дефект S05. Владелец согласовал
PATCH 2.1.27; итоговый CI относится к следующему head после push.

| Сценарий | Источник | Первичное доказательство | Результат на `fffd501a` | Граница |
| --- | --- | --- | --- | --- |
| S01 Закрытие, возврат, одна публикация | seeded valid pre-close Cycle, HTTP/SQL | `report11-bridge-receipt.json`, `report11-history.json`, `report11-selected.json`, `report11-bridge.pdf`; `test_report11_http_close_reaches_saved_report_history_and_pdf` | PASS: 1 Cycle → 1 Results → 1 revision → 1 Report, чтение без writes | Путь от приглашения не повторялся. |
| S02 Обрыв/повтор/конкуренция | isolated PostgreSQL | `test_m10_product_path_db.py`: recovery, restart, concurrent worker/publication tests | PASS для этих отказов | Не полный перебор сети/БД. |
| S03 Исходы/сообщения | saved synthetic C-67 | `test_integrated_acceptance_db.py`, `test_m8_results.py`, `report03-outcomes.spec.mjs`, `saved-bridge-390.png` | PARTIAL: четыре исхода, 0, short/incomplete, technical failure | Реальный bridge содержит английские диагностические фразы; качество живого русского текста не подтверждено. |
| S04 Исторический контекст | frozen snapshots | `test_m10_product_path_db.py`, `test_m8_recommendation_basis_db.py`, `test_m8_results.py` | PARTIAL: frozen route/plan и сохранённая основа | Нет одного теста одновременной подмены назначения, анкеты W02 и программы. |
| S05 Радар/размеры | saved UI и actual bridge | `report05-radar.spec.mjs`, `auth-r03.spec.mjs`, `rad01-report-radar.test.mjs`, `radar-1440.png`, `radar-390.png`, `saved-bridge-390.png` | PARTIAL: 0/пропуск, выбор, 320 px и увеличение шрифта 200% без overflow | Разные каталоги двух snapshots и настоящий browser zoom 200% не проверены. |
| S06 История Cycle | saved DB/UI rows | `test_review_report_history_db.py`, `report06-history.spec.mjs`, `history-390.png`, `report11-history.json` | PARTIAL: группировка, открытие, возврат | Нет общей browser-сессии с двумя Cycle, попытками и исправлением. |
| S07 Сравнение | exact synthetic pairs | `test_m8_report_comparison.py`, `test_m8_report_comparison_http.py`, `auth-r03.spec.mjs`, `comparison-390.png` | PASS для сопоставимых/частичных/несопоставимых пар и 0 | Не методологический допуск живого сравнения. |
| S08 Доступ | isolated PostgreSQL/HTTP | `test_m8_report_access_db.py`, `test_m8_report_access_http.py`, `test_p4k_report_09_correction_http.py` | PARTIAL: owner/admin, актуальное членство, PDF, retired legacy | Не вся матрица ролей × endpoint. |
| S09 Админский список | saved UI | `report08-admin.spec.mjs`, `admin-1440.png` | PARTIAL: страницы, поиск, статусы | Не все сочетания дат/фильтров/ролей. |
| S10 Исправление | immutable DB revisions/UI | `test_p4k_report_09_correction_db.py`, `test_p4k_report_09_correction_http.py`, `report09-correction.spec.mjs`, `correction-390.png` | PARTIAL: атомарность, исходник, конкуренция и запрет чужого источника | Нет одного связанного browser/PDF прогона после исправления того же C-67. |
| S11 PDF | real Typst + fixtures | `report11-bridge.pdf`, `report11-bridge-page-1.png` … `-6.png`, `test_m8_pdf_export.py`, `report10-pdf.spec.mjs` | PARTIAL: 6 страниц A4, текст/радар, exact Report, renderer fail closed; unit long/comparison/limited/corrected | Не все PDF-варианты визуально пересмотрены на этом head. |
| S12 Сеть/timeout/stale/cleanup | HTTP/UI, owned process group | `report04-personal.spec.mjs`, `report06-history.spec.mjs`, `report10-pdf.spec.mjs`, `resource-receipt.json` | PARTIAL: stale/error/retry и teardown PASS | Общий network-chaos прогон не выполнялся. |

## Прогоны, расхождения, ресурсы

- Bridge на `fffd501a`: `1 passed`, 22 controlled gateway calls, 3 worker rounds,
  1 Report, 0 платных LLM, 0 писем. Browser на его сохранённом C-67:
  `1 passed`, exact `report_id` на экране/PDF, IDs не выводятся участнику.
  SHA-256 выбранного JSON `54f4a45437b6f5ae163609691373f22d83ff27b6de967c6584068cf5990522b3`,
  PDF `0cc2ac78e16a9b16c09a541fc5d596b2dcb46c7426d172e539b5551cf26bce2d`.
  Первый FAIL лимита 15 сохранён в `bridge-initial-budget.log`; лимит повышен
  до 30 до повторного прогона, продуктовый код не менялся.
- На `fffd501a`: интеграция `44 passed` (97.22 с, `integration-rebased.log`),
  unit/e2e `60 passed` (`unit-e2e-rebased.log`), frontend `14 passed`
  (`frontend-rebased.log`), browser `173 passed, 1 skipped` за 3.4 мин
  (`browser-rebased.log`, один worker, retries=0, per-test timeout 30 с).
  На `02596d7` диагностически было 44/60/14 и browser 14+1.
- Просмотрены реальные экраны: радар 1440/390, сравнение 390 и
  `comparison-200pct-equivalent.png`, админ 1440, исправление 390,
  сохранённый отчёт 390; 320 проверен на overflow. Нативный select предыдущей
  оценки сокращает дату при 390 px. Список остаётся доступным; расхождение
  открыто. Эквивалентная CSS-ширина не названа реальным browser zoom.
- `run_id=report11-20261117-02596d7`; PostgreSQL 15 PID 4029, порт 55441,
  `p4k_report11_pytest`, 1 worker, retries=0. `pg_ctl -m fast stop` завершился
  штатно; `lsof -iTCP:55441 -sTCP:LISTEN` пуст, log содержит `database system
  is shut down`; process registries удалены. `lsof` не нашёл preview на 189xx.
  Файл диагностической БД пока сохранён выключенным, сервис и restart queue
  отсутствуют. Полный PATH от приглашения, TEST после выпуска
  и пилотная методология: `NOT_RUN`. Merge/deploy не разрешены этим этапом.

Для пилота нужны живые содержательные источники и отдельная приёмка, а также
решение по частичным строкам матрицы. Откат PR — revert test/docs; собственная
БД уничтожается после остановки сервиса. В первом опубликованном head runtime
и предметные артефакты не менялись; локальная CSS-правка описана ниже.

## Сбой CI и адресная регрессия

На `b7690554` jobs `CI / frontend`, `CI / pytest`, четыре runtime browser lanes
и integration — PASS; `Full verification / browser (fast)` — FAIL, поэтому
обязательный `full-verification` — FAIL. Лог job
`https://github.com/VadikB/4K_MBTI/actions/runs/44101667980/job/134103008056?pr=242`
показывает `QA19-04`: на Linux SVG подписи `13.8927 px` при ожидаемых `>=14`,
деления `11.8819 px` при ожидаемых `>=12`, overflow=false. Правило и CSS
`15.2px`/`13px` существовали в `main` `fffd501a`, PR их не менял. Сбой относится
к S05 и выявляет действительную потерю читаемости при масштабе SVG.

Минимальная правка `web/styles/screens/report.css`:
подписи `16px`, деления `13.5px`. При наблюдавшемся Linux scale ≈0.914 это
даёт ≈14.62/12.34 px. `QA19-04`, REPORT-05 и REPORT-11: `5 passed`,
frontend radar/report: `9 passed`, `npm run build:web`: PASS. После согласования
владельцем `version_bump=true`, `npm run ready:prepare -- --candidate 2.1.27`
PASS; на 2.1.27 те же адресные browser `5 passed` (`radar-fix-targeted.log`).
`saved-bridge-1440.png` и `saved-bridge-390.png` обновлены; 390 просмотрен
визуально. Полный Linux CI после исправления — `NOT_RUN` до push.
Откат продуктовой правки — revert CSS, версии и сборки; merge/deploy отдельно.

Review по `docs/evc/review-checklist.md` первого коммита: новые пути только `tests/` и
`docs/evc/tasks/p4k-report-11/`; API/схема/runtime/версия в нём не изменены,
данные синтетические, внешние вызовы выключены. `git diff --cached --check`
PASS после удаления trailing whitespace из исходного диагностического лога.
Review PATCH: `report.css` меняет только 2 размера текста; `pyproject.toml`,
`uv.lock`, `web/js/config.js`, `web/index.html` и `web/dist` — согласованный
механический выпуск 2.1.27. `npm run lint:js`, `npm run build:web`,
`git diff --check` PASS; API/БД/предметные артефакты не меняются.
