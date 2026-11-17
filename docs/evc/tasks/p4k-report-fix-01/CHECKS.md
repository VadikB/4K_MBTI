# CHECKS — P4K-REPORT-FIX-01

17.11.2026. База `0aadde0` / 2.1.27, ветка `codex/p4k-report-fix-01`.
Исправления F01/F04/F05 завершены локально. Полномочие и границы — [TASK](TASK.md).
Источники и их хеши на базе — [sources.json](evidence/sources.json).

## AC01–06

| Критерий | Результат и доказательство |
| --- | --- |
| AC01 | **PASS**, Chromium: настоящий HTML/JS, синтетические ответы API. A с отличимыми программой, навыком, основанием и нулём → история → B503. URL содержит B; detail, chart, skills, summary, notices и PDF очищены. Resize 1440→390 не возвращает A. Повтор Enter показывает только B и 2.25. `report04-personal`, тест `FIX-01 AC01`. |
| AC02 | **PASS** в применимой области: параметризация 403/404/network/timeout и admin503 на общей функции открытия. Поздний A после успешного B игнорируется и после resize. Timeout реально прерывает fetch через AbortController; в тесте только интервал 30000 мс ускорен до 30 мс. Запросы сценария — GET; fixture остаётся побайтово неизменной. Глубокое равенство сохранённых C-67 проверяется unit/HTTP. Рабочая БД не использовалась; это не SQL integration всего контура. |
| AC03 | **PASS**: история, админский список и сравнение × 503/network/JSON200/ошибочная сигнатура/timeout, затем клавиатурный повтор. Адрес, страница/фильтры администратора и выбранная пара сохраняются. Существующие owner/customer кнопки открытого отчёта проходят 503/retry и успешное скачивание; REPORT-06/08/09 проходят открытие/возврат и исправления. |
| AC04 | **PASS**: HTTP routes проверяют имя и реальные PDF bytes; browser сравнивает скачанные файлы побайтово с настоящим Typst PDF выбранного отчёта/пары. Контрольные программа, даты, навык и 0 проверены pypdf. Comparison сохраняет current ID в пути и previous ID в query; admin использует `/users/admin/m8-access/…`. JSON и тело без `%PDF-` не скачиваются. Поздние ответы после смены отчёта/пары подавлены, двойной click не создаёт второй запрос. |
| AC05 | **PASS**: четыре исхода, подтверждённый 0, причины и неизвестные ограничения сохранены. API и настоящий PDF содержат одну совместимую русскую подпись; исходные C-67 не изменены. Четыре старые служебные подписи переводятся reader-проекцией. Raw completeness и ложная фраза о неопределённой полноте удалены из UI. Конфликт исхода/подписи/полноты/числа сохраняет outcome/score и добавляет consistency с безопасным сообщением. Browser проверяет четыре исхода и отсутствие служебного текста; PDF v3 убирает повтор в карточках, v2 неизменён. |
| AC06 | **PASS**: 1440/390 без горизонтального переполнения, сообщения видимы, повтор Enter доступен. Стили используют `--text-muted`, `--fs-caption`, `--space-*` соответствующего окружения; отдельная палитра не вводится. Lint/build/frontend/backend/HTTP и 32 browser PASS. Повторная сборка даёт те же 45 файлов и SHA-256. Preview остановлены, контрольные localhost-порты свободны; БД не запускалась, LLM=0, писем=0. |

## Команды и фактический результат

Команды выполнялись из корня checkout. Backend/HTTP с
`PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0`, без developer `.env` и реальных сервисов.

| Команда | Статус / evidence |
| --- | --- |
| `.venv/bin/python -m pytest -q tests/unit/test_m8_results.py tests/unit/test_m8_pdf_export.py tests/unit/test_m8_report_comparison.py tests/unit/test_m8_recommendations.py` | PASS, **76**, [log](evidence/targeted-python-final.log.gz). |
| `npm run test:backend` | PASS, **1217**, 661 deselected, exit 0; [log](evidence/backend-final.log.gz). |
| `npm run test:backend:http` | PASS, **201**, 15 deselected, exit 0; [log](evidence/http.log.gz). Новая проверка API→real PDF для owner/admin, ACL-регрессии сохранены. |
| `node --test tests/frontend/*.test.mjs` | PASS, **404**, exit 0; [log](evidence/frontend-final.log.gz). |
| `npm run lint:js` | PASS, exit 0; [log](evidence/lint.log.gz). |
| `npm run build:web` | PASS; [log](evidence/build.log.gz), [повторная сборка](evidence/build-identity.txt), [SHA-256](evidence/build-sha256.json). |
| `npx playwright test tests/browser/report04-personal.spec.mjs tests/browser/report06-history.spec.mjs tests/browser/report08-admin.spec.mjs tests/browser/report09-correction.spec.mjs tests/browser/report10-pdf.spec.mjs --reporter=line` | PASS, **32**, exit 0; [log](evidence/browser-final.log.gz). Существующие fixture/preview, нового тестового контура нет. |
| `pdftoppm -scale-to 1100 -png -singlefile …` | PASS, контрольные отчёт и сравнение просмотрены: кириллица читается, сообщения/ноль/программы/даты сохранены, наложений и обрезания нет. PDF: [отчёт](evidence/selected-report.pdf), [пара](evidence/selected-comparison.pdf). |
| `git diff --check` | PASS, exit 0. |
| `lsof -nP -iTCP:18964 -iTCP:18966 -iTCP:18968 -iTCP:18969 -iTCP:18970 -sTCP:LISTEN` | Вывода нет, exit 1 = нет слушающих preview; afterAll закрыл серверы и Chromium. |

Три представительских снимка:

- [Ошибка B после A, 390 px](evidence/open-error-390.png).
- [Ошибка PDF в истории, 390 px](evidence/pdf-error-history-390.png).
- [Ошибка PDF в админском списке с фильтром и страницей, 390 px](evidence/pdf-error-admin-390.png).

## Review, промежуточные сбои и ограничения

Self-review: проверены вызывающие entrypoints, прежние маршруты/ACL, чистота
проекции, фиксация ID/пары, старые callbacks/resize, дедлайн чтения тела и защита
finally при переключении общего PDF-контрола. Новых методологических правил,
миграций, предметных артефактов и внешних побочных эффектов нет. Исторические
снимки REPORT-04/06/08/09, перезаписанные существующими тестами, восстановлены;
новые доказательства сохранены только в каталоге этой задачи.

Первый browser не смог открыть localhost из sandbox (`listen EPERM`); разрешённый
повтор PASS. Первый полный backend: 9 отказов sandbox на `ps` плюс исправленная
совместимость исторического `skills=[1]`; окончательный полный набор PASS с доступом
к своим дочерним процессам. Начальные логи: [backend](evidence/backend-initial.log.gz),
[browser](evidence/browser-initial.log.gz). При переносе PDF-обработчика был пропущен
экспорт в `entries/report.js`; существующий browser выявил дефект, экспорт исправлен,
окончательные 32 PASS включают эту кнопку. Три старых frontend source-assertion
актуализированы под новую точку обработчика и единое объяснение; поведение
проверяется реальным браузером и HTTP/PDF.

NOT_RUN: PostgreSQL integration (схема/БД не меняются, применимая строка матрицы
закрыта HTTP); полный путь оценки/реальные LLM/письма (вне области); CI, push/PR,
merge/deploy и bump версии (не были поручены на момент локальной передачи `32ecd71`). Это локальная техническая приёмка;
человеческая приёмка владельца и будущий обязательный CI остаются отдельно.
FIX-02/REPORT-11 не выполнялись. Упомянутый 00_START не найден; ограничение
и область поиска сохранены в TASK, F01/F04/F05 не зависели от новой оболочки.

Откат — обратный diff этого изменения, включая сборку и подключение PDF v3.
Первичные Results/C-67/история/рабочая БД не менялись. Следующий шаг — приёмка
владельца готовых локальных исправлений.


## Этап выпуска по поручению «выкладывай на main»

Полномочие: прямой запрос владельца после локального результата `32ecd71`.
Следующий PATCH от свежего `main=0aadde0` / 2.1.27 — **2.1.28**.
`branch_push/pr/merge/version_bump=true`, `deploy=test` штатным workflow,
`artifact_publish=false`; pilot/production/LLM/письма не включены.

- `npm run ready:prepare -- --candidate 2.1.28` — PASS, [лог](evidence/ready.log.gz).
- `npm run lint:js` — PASS, [лог](evidence/release-lint.log.gz).
- `node --test tests/frontend/*.test.mjs` — 404 PASS, [лог](evidence/release-frontend.log.gz).
- Адресный M8/release unit — 45 PASS, [лог](evidence/release-unit.log.gz).
- `npx playwright test tests/browser/report10-pdf.spec.mjs --reporter=line` со штатным выбором Python — 17 PASS, [лог](evidence/release-browser.log.gz).

Кандидат включает только версию/сборку, поддержку BROWSER_PYTHON в тесте и обновление
записи передачи поверх проверенного приложения. Предыдущие code-identity/build hashes
относятся к локальному этапу; текущая версия — в release-identity.json.
PR/обязательные CI и deploy на этом этапе ожидаются; их итог будет передан владельцу
по фактическим URL и SHA. Откат — revert squash commit приложения/сборки.
