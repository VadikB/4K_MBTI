# CHECKS — P4K-REPORT-06

База `7e96d4dc` (2.1.18), кандидат 2.1.19; точный commit будет указан после фиксации. Synthetic browser fixtures, один worker, retries=0, LLM/письма=0. Test PostgreSQL15 создана только для этого прогона, остановлена/удалена, порт 55466 свободен.

| Критерий | Статус | Доказательство и предел |
| --- | --- | --- |
| AC01 Cycle/revisions/порядок | PASS локально | `test_m8_report_access_db.py::test_owner_and_admin_http_scope_ignores_legacy_recipient_list`: 1 PASS на реальной isolated PostgreSQL. Два revisions одного Cycle дают одну запись; сортировка по закрытию сохраняется при иной дате Report. |
| AC02 историческая программа/deep link/возврат | PASS локально | Новый HTTP test сохранённой программы 1 PASS; browser REPORT-06: точный `cycle_id/report_id`, reload, direct link и возврат на страницу 2 из 2; прежняя программа не меняется при переименовании конфигурации. |
| AC03 состояния/ошибка/пусто | PASS локально | Browser: processing → failed → ready в одной карточке; 503 даёт ошибку и повтор, успешный пустой ответ даёт пустое состояние. |
| AC04 legacy/UI/W02 | PASS локально | В действующем экране нет version-selector/legacy-архива, старый `session_id`-адрес переводит в историю с пояснением. W02/LK01 browser 4 PASS. Исходные таблицы и аудит сохранены. |
| AC05 права/страницы/1440/390 | PASS локально | PostgreSQL/HTTP подтверждают доступ бывшего участника и запрет чужому; browser 12 Cycle → 10+2 без дублей, скрытая текущая оценка, снимки `evidence/`. На 1440/720/390/320 нет горизонтальной прокрутки; 720 — прокси 200%, не реальный browser zoom. Человеческое visual review отдельно. |
| Регрессия REPORT-04/05 | PASS локально | Browser 6 PASS: сохранённая шапка, поздний ответ, радар/панель. |
| Backend/HTTP | PASS с ограничением | `pytest -m 'not integration and not e2e and not llm'`: 1117 PASS, 9 FAIL только `PermissionError` subprocess в sandbox; адресный повтор `test_synthetic_limits.py` с разрешённым запуском: 19 PASS. Адресный HTTP: 33 PASS. |
| Frontend/release | PASS локально | `node --test tests/frontend/*.test.mjs`: 354 PASS; `npm run lint:js`, `npm run ready:prepare -- --candidate 2.1.19`, release unit: 11 PASS. |
| Diff/CI/выпуск | PARTIAL | `git diff --check` PASS. CI точного head, review, TEST/Prod не выполнены. |
