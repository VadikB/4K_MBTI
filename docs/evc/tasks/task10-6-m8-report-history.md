# 10.6 — История M8 и повторный доступ

## Результат, источники и границы

Реализована одна карточка на assessment Cycle, состояния подготовки/ошибки/готовности,
явные Results/Report revisions, owner + tenant + assessee scope, история после
повторного входа, защита от устаревших ответов и смены пользователя.
Legacy-архив сохраняется отдельно; пересчёт, миграции, новый UX, merge/deploy не входят.

База `010c2b39dc462a1245e1d4ba376c163111ccb6db` — 11.2 поверх 10.5/10.4.
Ветка `codex/task10-6-m8-report-history`. Fetch main:
`8654b97ed6605d560111c37cd291f98f82c41457`.
Повторно использованы прочитанные README/CONTRIBUTING/EVC workflow/matrix/recipe,
context/Registry/Change01/M1 v1.4 CURRENT=NO/ADR-002 и M8 v1.2 §6–7.
Для задачи прочитаны routes dashboard/profile-summary/M8 owner API,
m8_results list/read, schemas, frontend reports/report/profile/session/state,
browser REV-02 и DB/HTTP 11.1/10.5. Применимость источников не меняется.

REV-03 уже частично исправлен: saved M8 list и выбор Report revision существуют.
Остаток: список только готовых отчётов; нет tenant/QA проверки direct Report ID;
нет защиты M8 report fetch от смены пользователя/выбранного Report.
PM-07 owner read/presentation; PM-05/06 факты не изменяются.
Все восемь стоп-условий — нет: существующий контур, additive API,
совместимость сохранена, новые предметные нормы/миграции не вводятся,
права сужаются до заданного scope, откат ниже, область разрешена постановкой 10.6.

## Реализация и трассировка

Выбранные версии и SHA-256 исходников повторно сверены: [sources.json](artifacts/task10-6/sources.json).
Исходная постановка: [request.txt](artifacts/task10-6/request.txt).
M1/Change 01: Cycle отделён от расчётной и презентационной редакций →
`m8_results.list_owned_cycles` группирует по Cycle → DB regression и два браузерных Cycle.
M8 v1.2 §6–7: сохранённые Results/C-67, разные аудитории, повторное чтение без
изменения фактов → read-only list/direct JSON/PDF → hashes полного набора строк
IA/Results/Reports до/после повторного чтения.
PM-07: UI карточки/версии и выбор PDF; PM-05/06 и генерация рекомендаций не менялись.
Проверка идентичности источников не является новой нормативной приёмкой.

`Api/m8_results.py`: общий owner/tenant predicate, список всех assessment Cycle
со статусами и версиями; совместимый список готовых Report использует тот же predicate.
`Api/routes.py` и `Api/schemas.py`: additive история, profile-summary,
проверка прав до чтения содержимого сохранённого Report/PDF; существующие cycle M8
routes проверяют тот же tenant. Другие M7 маршруты не менялись.
`web/js/screens/reports.js`: готовые/ожидающие/ошибочные карточки, явная версия,
legacy-архив отдельно. При открытии legacy Report из URL удаляются Cycle/Report IDs;
reload остаётся в legacy-контуре, кнопка PDF восстанавливается.
`report.js`, `session.js`, `state.js`: очистка кэша,
identity/request epoch, отказ от устаревшего ответа; при возвращении во вкладку
проверяется cookie через session/restore. Несовпадение владельца очищает локальный
экран без logout сессии другого пользователя.

Миграции и изменения опубликованных пакетов отсутствуют. Новых runtime-политик,
предметных defaults и расширений legacy-исключений нет; artifact-debt не расширен.

## Контракт и совместимость

Новый GET `/users/assessment/m8/history` выводит доступные Cycle владельца
при текущем членстве в активной организации Cycle. `assessments_total` — число Cycle; `reports_total` —
число Cycle с assessee Report (не revisions); `completed_assessments` — число
Cycle с закрытым сбором. Карточка: cycle_id/status/dates, latest Results ref,
выбранный последний assessee Report ref и `versions` в порядке Results revision,
затем Report revision. `report_id` в URL всегда означает конкретную версию;
без него открывается последняя доступная версия Cycle. GET ничего не создаёт.
`profile-summary.cycle_reports` и dashboard остаются совместимы для готовых Report;
полный список состояний передаётся отдельным additive полем/API.
Dashboard `reports_total` — число Cycle с доступным Report; profile-summary
`total_assessments` — все доступные Cycle, `completed_assessments` — с закрытым
сбором. Legacy не прибавляется к этим счётчикам: отдельное `legacy_assessments_total`.
`latest_results_revision_*` — самая новая расчётная редакция; `results_revision_*`
у готовой карточки соответствует выбранному последнему доступному Report.
Порядок versions: Results revision DESC, Report revision DESC.
Технический сбой рекомендаций не скрывает готовый базовый Report.
Восстановление processing выполняет существующая очередь; кнопка истории
«Обновить состояние» только перечитывает данные.

## Проверки и откат

Воспроизведение до реализации: `before.log`, 1 FAIL — новый history GET возвращает 404.
Последующие промежуточные FAIL сохранены отдельно: HTTP mocks и минимальные DB
fixtures дополнены новым tenant/pipeline контрактом; browser login handler теперь
регистрируется один раз, ожидание готовности проверяет видимость Report panel.
Assertions доступа/неизменности не ослаблялись.

- `npm run test:backend`: 354 passed, 125 deselected, exit 0 (`unit-final.log`).
- `npm run test:backend:http`: 39 passed, exit 0 (`http-final.log`).
- `node --test tests/frontend/*.test.mjs`: 4 passed, exit 0 (`frontend.log`).
- `npm run lint:js`, `npm run build:web`: PASS; dist пересобран.
- Owned DB/HTTP адресно: 1 passed (`owned-http.log`); полный integration:
  **79 + 3 passed**, exit 0 (`integration.log`).
- Browser REV-02 с реальными HTTP/DB: 1 passed (`browser-targeted.log`); полный набор: **10 passed**, 0 retries, 12.2 минуты (`browser.log`,
  `browser-summary.json`). После финальной правки legacy URL/PDF: **1 passed**, 0 retries, 1.3 минуты
  (`browser-final-history.log`, `browser-final-summary.json`) на пересобранном frontend.
- `git diff --check`: PASS для текущих изменений.

Полный integration: `STAND_ADMIN_URL=<local maintenance> TEST_DATABASE_URL=<local pytest maintenance> .venv/bin/python docs/evc/tasks/artifacts/task10-6/integration-run.py`.
Полный browser: `STAND_ADMIN_URL=<local maintenance> npm run test:browser`.
Только собственные одноразовые БД bootstrap/seed 10.2, synthetic gateway; не shared DB.
Реальные LLM/экспертная приёмка не используются и не заявляются.
Откат к базе 010c2b3 без удаления истории и новых пересчётов. Tenant/QA проверку
сохранить отдельным исправлением при откате UI; уязвимый доступ не восстанавливать.


## Критерии приёмки

| Критерий | Проверка и статус |
| --- | --- |
| H10.6-01 | PASS: 1 Cycle, 0 legacy, dashboard=1, карточка и её PDF |
| H10.6-02 | PASS: logout через меню → login → «Мои отчёты» → select старой версии → open/reload/download |
| H10.6-03 | PASS: второй Cycle через UI; отдельные Results IDs; две карточки |
| H10.6-04 | PASS: регенерация первого Report, две versions внутри карточки; явный Report ID сохраняется после reload |
| H10.6-05 | PASS DB/HTTP: collecting/processing/failed и восстановление; generator failure оставляет базовый Report |
| H10.6-06 | PASS DB/HTTP: anonymous/other owner/другая организация; QA Cycle/customer/methodology_qa Report не выдаются |
| H10.6-07 | PASS DB/HTTP: повторные GET/PDF сохраняют полные строки и hashes IA/Results/Reports; существующая защита 11.1 сохраняется |
| H10.6-08 | PASS: две вкладки и новый аккаунт; legacy-session не меняет Cycle history; frontend clear regression |
| H10.6-09 | Локально PASS: integration/browser/build; CI финального commit фиксируется в PR |

## Ревью и передача

Самопроверка по EVC review-checklist: scope PM-07, additive контракт,
owner+tenant+audience до чтения, snapshots неизменны; критерии тестируются
на синтетических данных. Это не человеческое review.
Ограничения: UI показывает состояние восстановления, но не вводит новый ручной
recovery API. Групповых/продольных отчётов и сравнения разных Cycle нет.
Полная методологическая валидность, admission 8.1, реальные GC и LLM не заявляются.

Дополнительный выход за основной M8-сценарий выявил **FAIL существующего legacy
read на чистом bootstrap**: `get_skill_assessments` требует отсутствующую колонку
`competency_skill_id`. Этот SQL и схема не менялись в 10.6; неполнота исторического
DDL ранее записана в 10.2. Доказательство: `browser-legacy-bootstrap-gap.log` и
`legacy-bootstrap-limitation.txt`. Миграция неизвестной исторической БД не выполнялась.
H10.6-08 проверяет реальный совместный список и независимость M8; дополнительная
проверка legacy URL/reload использует явно синтетические ответы двух legacy API.
Она **не подтверждает** полную работу исторического backend/PDF на новой БД.
Восстановление полного legacy read — отдельная задача с историческим контрактом.

Проверяется общий стек 10.5 + 11.2 + 10.6. Зависимый PR #35 на точном
`010c2b39dc462a1245e1d4ba376c163111ccb6db` прошёл PR CI #162 и push CI #161.
[Draft PR #36](https://github.com/VadikB/4K_MBTI/pull/36) создан к ветке 11.2;
merge/deploy не выполняются.
CI финального head фиксируется в PR после завершения, старый PASS не переносится.

Код и локальные доказательства: `0de7a26ac7df47e1f6d08dca33be78cd10036c74`.
Diff реализации: `git diff 010c2b39dc462a1245e1d4ba376c163111ccb6db..0de7a26ac7df47e1f6d08dca33be78cd10036c74`.
Коммит передачи `b66d421ddf0739fb38440a9967c6123d0d0cf986` прошёл frontend,
но CI #166 выявил UTC-расхождение сериализации в одном из 82 integration-тестов.
Оно воспроизведено локально: `utc-before.log`, 1 FAIL / 1 PASS для UTC/+03.
Новый `M8HistoryResponse` использует тот же Pydantic serializer, что profile-summary;
строгое сравнение сохранено. После исправления: 354 unit, **39 HTTP**, адресный
owned DB/HTTP **1 PASS** (`unit-final.log`, `http-final.log`, `owned-http-final.log`).
Контракты дат согласованы без изменений данных/схемы/прав. Frontend не менялся.
Окончательный SHA и новые CI `frontend`/`pytest` фиксируются в PR #36; прежний
красный запуск не выдаётся за успешный.

`history-receipt.json`: 18 IA revisions, 2 Results revisions, 6 Reports (включая
синтетические скрытые аудитории); полные строки и hashes неизменны после GET/PDF.
`scripts/browser_report_fixture.py --kind archive-session` создаёт только
синтетическую legacy-сессию в owned stand для проверки совместного списка.


## Безопасные доказательства

[История после входа](artifacts/task10-6/history-list.png),
[два Cycle и отдельный архив](artifacts/task10-6/two-cycles-and-legacy.png),
[выбранный исторический Report](artifacts/task10-6/history-report.png),
[его JSON](artifacts/task10-6/selected-report.json) и
[скачанный PDF](artifacts/task10-6/selected-report.pdf).
`scripts/verify_browser_pdf.py` повторно сопоставил выбранный PDF с этим C-67:
Cycle ID, навыки, рекомендации, контекст, ограничения и цитаты совпали; 6 страниц.
Все 6 страниц просмотрены после Poppler render; наложений/обрезания текста нет.
Карточки и отдельный legacy-раздел визуально проверены на снимке 1440×1000.
Все записи и материалы синтетические, персональные данные рабочих контуров не использовались.
