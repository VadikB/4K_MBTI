# Task 10.3 — браузерная приёмка общей сборки

## Разведка, границы и план

Постановка: редакция 1 от 05.10.2026, предоставлена владельцем с запросом
«делаем 10.3». Исходный HEAD `7aebd3cffc0b2338fa3bf48d8a4b9fbd48d1402b`,
ветка `codex/task11-1-recommendation-basis`, дерево чистое. После fetch main:
`14cf514e5420fe095a45285619498024b73c0c0e`. Общий Draft PR #32 по ранее
согласованному решению собирает три изменения. 10.1/11 входят в main,
11.1 — 4c051f2, 10.2 — ed5d80b/ae8b1fc/7aebd3c. Merge/deploy запрещены.

Повторно использованы прочитанные README, CONTRIBUTING, EVC workflow/матрица/
рецепт/review, context/Registry, Change 01 manifest, ADR 002 и отчёты 10/11/11.1/10.2.
Дополнительно прочитаны относящиеся M5–M8 runtime, UI, workers, тесты и контракты.
M1 v1.4 FROZEN/CURRENT=NO, M6 v1.8, M7 v1.3, M8 v1.2; нормативные статусы,
admission и production defaults не меняются. Редакция 2 задания 11 ранее
не найдена; требования 11.1 и явная матрица 10.3 используются для данной проверки.

Legacy: действует последнее решение владельца «по возможности убирать все legacy».
Старый runtime не восстанавливается; история сохраняется, скрытый fallback запрещён.
Все данные synthetic, новый автоматически созданный стенд по 10.2; рабочие .env/БД
и платные AI не используются. Fixture-ответы допустимы только на AI-границе,
с настоящими ссылками на полученные Turns. Редкие fixtures отмечаются отдельно.

План выполнен локально; CI проверяется отдельно по актуальному HEAD PR.

1. Подготовить минимальный Playwright runner и управляемые входы AI/time
   до старта, определить ожидаемые состояния по контрактам.
2. Выполнить реальные UI S10-A + clarification + положительный T11-10, S10-B,
   S10-C1/C2. Фиксировать первый сбой, исправлять адресно и повторять.
3. Проверить N1–N5, права, восстановление/повторы, значения и версии с явным
   разделением browser, HTTP и backend доказательств.
4. Сохранить скриншоты/PDF/read-back, выполнить итоговый suite и EVC минимум/CI,
   обновить исторические отчёты ссылкой без переписывания прошлых результатов.

Ожидаемый результат заранее: A — настоящая рекомендация с основанием в своём
материале; B — новый Session ID при прежнем Cycle/deadline/остатке, без копирования
Turns; C1/C2 — фоновое закрытие без клика/нового Turn, поздний ответ отвергается;
повтор GET не меняет revisions, owner scope сохраняется, PDF соответствует C67.

При разведке все B10.3 были NOT_RUN; итоговые статусы приведены ниже.
Реальный provider, 8.1, экспертный просмотр, GC/Reliability
оцениваются отдельно; technical PASS не означает нормативного допуска.
Откат: остановить/удалить только свои стенды; revert адресных коммитов 10.3,
сохранить 11.1/10.2 и существующие данные. Управляющие документы не изменяются.

## Решения и выявленные дефекты

Владелец 05.10.2026 явно разрешил **отдельный synthetic версионированный кейс**
для механики ответа персонажа. `CASE-TDISC-04` не допущен planner из-за
`CASE04_ASYA_BRANCH_CONDITION_REQUIRES_METHOD_OWNER_DECISION`. Это решение не снято.
`tests/browser/fixtures/sources/character-case-v1.json` — отдельный
`CASE-BROWSER-CHARACTER-01/synthetic-v1`, структура производна от CASE-TDISC-04,
условные ветви раскрытия исключены; проверяются mandatory update/character reaction.
Manifest фиксирует SHA-256 и прежние M2/M3 dependencies. Synthetic seed публикует
технические входы только в disposable БД; это не допуск исходного кейса, не GC.

| Первый дефект / наблюдение | Адресное исправление и регрессия |
| --- | --- |
| Вместо условий кейса показывался только заголовок | UI читает фактические поля participant_payload; A/B и character branch |
| Ответ не отправлялся: createOperationId отсутствовал в imports | Исправлен импорт; lint расширен на корневые web/js/*.js, удалены 5 неиспользуемых imports |
| Завершение проверяло только legacy session_code | Новый Cycle допускается в обработчик finish; legacy client-event не отправляется с пустым session_code |
| Turns показывались до всех событий, уточнение дублировалось | Общая сортировка sequence_no; один показ question Turn |
| Пользовательский start/trace раскрывал execution envelope | Projection только предъявленного материала; unit-регрессии и browser read-back; admin trace сохранён |
| Reload нового интервью возвращал к подтверждению профиля | cycle_id в URL; восстановление после проверки owner API; B/C и две вкладки |
| Additional Session создавалась сразу, без фактического прерывания | Раздельные действия «Прервать и продолжить позже» / «Продолжить…»; B |
| Retry мог потерять request/turn identity из-за перерисовки | Pending row сохраняется; повтор использует тот же endpoint/request_id/turn_id; потерянный ответ и непринятый запрос |
| После отправки прекращался опрос runtime | Опрос возобновляется после успеха; по закрытому состоянию открывается обработка |
| Предварительно назначенный plan не предъявлял первую AS | start_or_resume предъявляет первую AS prepared Cycle; C1/C2 |
| Противоположный порядок блокировок Turn и close | Cycle блокируется перед AS; regression с двумя настоящими соединениями, закрытие выигрывает без позднего Turn |
| Пустой маршрут позволял ввод при отсутствии AS | Ввод/finish отключены, показана необходимость подготовки назначения |
| Headless/обычный Playwright удерживает visibility=visible | Для C1 обычный Chromium через CDP noDefaults, реальная смена вкладки и assert hidden; DOM не подменяется |

Изменения не затрагивают схему или сохранённые пользовательские данные. Сужение
owner-проекций удаляет недопустимые служебные поля; используемые UI participant/turn
поля сохранены. Admin диагностика не меняется. Порогов и предметных правил не добавлено.
Новые предметные тексты находятся только в явно synthetic fixtures.

## Карта источников и границ

- M1/ADR 002: материал принадлежит AS/Session/Cycle → M5 storage/trace и lock order →
  browser A/B/Recovery, integration `test_browser_turn_close_lock_order_and_late_turn`.
- M6 v1.8 / C-45/C-54: только фактические Turns, промежуточный и окончательный IA →
  m10_orchestration + m6 workers; positive/clarification и негативные gateway-примеры.
- M7 v1.3 / C-46: прежний budget/deadline при продолжении, фоновое закрытие →
  m7_completion_worker, browser B/C1/C2; production время не меняется.
- M8 v1.2 / C-56/C-67, 11.1: основание, сохранённые Results и revision Report →
  реальный m8_results, basis resolver, deterministic Recommendations, PDF → T11-10/N1–N5.
- Фактическая интерпретационная политика admission остаётся механизмом из 10/8;
  корректность её нормы — отдельная 8.1. Передача ограничений проверяется отдельно.

Нормативные пакеты, manifest Change 01, AGENTS, EVC/CONTRIBUTING не изменены.
UI/контроллер, предметные workers и инфраструктура тестового стенда разделены.
Правила и source snapshots прежних оценок не переписываются. Stop-условие по
исходному CASE-TDISC-04 сохранено; разрешённый synthetic вход закрывает только
техническую ветвь. Иных открытых стоп-условий для адресных исправлений нет.

## Метод проверки и режимы

Старт/ответы/уточнение/finish/прерывание/продолжение/ожидание Report/скачивание PDF
выполняет Playwright 1.63.0, Chromium 153.0.8010.12, viewport 1440×1000, ru-RU.
Обычные сценарии headless. C1 — обычный headed Chromium: CDP noDefaults отключает
принудительную активность Playwright, другая вкладка действительно делает интервью
hidden; после серверного закрытия восстанавливаются стандартные настройки скачивания
в том же браузере с прежними cookies/storage. Для CI настроен запуск этого режима под Xvfb.
C2 — реальная пауза и закрытие страницы, затем новая страница с серверным read-back.

M5: серверный runtime, controlled semantic/character AI только на границе адаптеров.
M6 Evidence/IA и M7 clarification: явный `acceptance-v1` AI gateway, точное совпадение
с сохранённым synthetic ответом, реальные Turn/fragment/evidence IDs. M7 planner,
expiry worker, orchestration, admission/агрегация, M8 и PDF — штатные механизмы.
Recommendations — deterministic, без LLM. Во время основной трассы готовые
Evidence/IA/Results/Report не вставляются; superadmin финализация не используется.

N3/N4 выполняются **после** полного positive T11: отдельный helper в owned stand
создаёт synthetic историческую Report revision / вводит сбой на границе генератора.
Он проверяет неизменность checksum Results. Далее работают реальные owner GET,
UI, PDF и HTTP regenerate; повтор ключа не создаёт новую revision. История не удаляется.

Заранее ожидаемые числа positive fixture: только K1.I13 и K1.I17 дают L1;
по одному допущенному вкладу соответствующего компонента → Score 1/1 у K1.3/K1.4,
оба результата partial. Два допущенных Indicator из полного набора 61, два компонента
из 35; IE K1.I16 перед L1 K1.I17 не становится основанием. Эти ожидания заданы в
тесте независимо от ответа сервера. Score не объявлен Skill Level.

PDF сверяется с сохранённым C-67 по каждому goal/practice/context/progress_signal,
цитатам материала и ограничениям через pypdf; номера страниц исключаются из
сравнения текста. Визуальный просмотр проверяет кириллицу, длинные строки,
переносы, таблицы, footer и пагинацию. Сравнение не требует побайтового равенства UI/PDF.

## Матрица B10.3 и соответствие прежним критериям

| Критерий | Проверка и область |
| --- | --- |
| B10.3-01 | Общая ветка поверх указанного main содержит 10.1/11 + 11.1/10.2; каждый тест создаёт пустую owned DB и применяет штатный bootstrap |
| B10.3-02 / S10-A / U10-08 | UI от входа до clarification/Report/PDF; отдельный разрешённый synthetic character case; авторство и порядок, отсутствие execution envelope |
| B10.3-03 / S10-B | UI interrupt/reload/Additional Session; 2 разных Session в одном Cycle, прежний deadline и остаток; отдельная AS без копирования Turns. Запрет после close и новый независимый Cycle — owner HTTP; старый Report неизменён |
| B10.3-04 / S10-C1 | Budget=30 до старта; реальная hidden вкладка; worker закрывает без Turn; поздний Turn 409; восстановление UI, Report/PDF, причина time_budget |
| B10.3-04 / S10-C2 | Calendar=30 до старта, budget=3600; pause/закрытие страницы; worker; поздний Turn 409; UI/Report/PDF, причина calendar_deadline |
| B10.3-05 / T11-10 | Positive UI/C-67/PDF с точными IA/Evidence/fragment/Turn и Results refs, read-back после reload, собственный Cycle |
| B10.3-06 | K1.I13: 3 поддерживаемых типа; K1.I17: только Development. Цели/практика/контекст/признак/ограничения сравниваются по C-67/PDF; семантическая приёмка экспертом отдельно |
| B10.3-07 / N1 / R11.1-01 | IE K1.I16 перед допустимым L1 K1.I17 в сохранённых observations; basis только L1, отсутствие IE как проявления; browser + real owner GET |
| B10.3-07 / N2 | Character fixture проходит настоящий путь без подтверждённого основания, рекомендации unavailable; no_result — integration S10-D без предъявленного материала, не подменяет positive |
| B10.3-07 / N3 | Отдельная инъекция сбоя генератора; базовый UI/PDF остаётся доступен, generation=failed, не ready; восстановление через явную regenerate |
| B10.3-07 / N4 | Отдельная историческая C-67 fixture: owner UI/PDF не выдаёт недопустимый блок, исходный JSON в БД неизменён, GET не меняет revision |
| B10.3-07 / N5 | Owner regenerate: новая revision, прежний Results и те же допустимые основания; повтор key возвращает тот же id. Это HTTP-проверка команды и browser/PDF выдачи |
| B10.3-08 | Browser: reload/две вкладки, принятый запрос с потерянным HTTP-ответом и непринятый запрос; прежние request_id/turn_id, ровно два исходных Turn. DB: гонка close/Turn; existing concurrent claim, expired lease, late attempt, immutable revisions |
| B10.3-09 | Второй обычный user получает 403 для чужих Cycle/AS/Results/Report/PDF; смена пользователя скрывает прежний UI. Auth/session серверные, никаких admin прав |
| B10.3-10 | Browser positive — partial 1/1 и no_result, версии/цитаты/лимиты C-67/PDF. Unit — Score 2.4/Target L2 остаётся NOT_COMPARABLE, zero ≠ no_result; integration — result_without_score и frozen processing/profile после изменения источников. Все четыре исхода не объявляются браузерными |
| B10.3-11 | Минимальный Playwright runner, точные команды и артефакты; CI сохраняет frontend/pytest и добавляет browser в pytest job с isolated bootstrap и Xvfb |
| B10.3-12 | Ниже — отдельные статусы provider, 8.1, исходного CASE-TDISC-04, экспертной приёмки и GC |

Дополнительные backend-доказательства переиспользованы **с повторным запуском на
данном кандидате**, а не переименованы в browser: `test_m6_evidence_db` (failure ≠ IE,
retry, expired lease, concurrent claim, поздние результаты, неизменяемость),
`test_m8_recommendation_basis_db` (mixed/empty/qualitative/denied/history/regeneration),
`test_m10_product_path_db` (S10-D/E, нулевой Score, новый расчёт сохраняет историю),
`test_m8_results` (Score/Level/Target), `test_m5_cycle_runtime_db` (владение и снимок).

## Ограничения и передача

- Реальный M5/M6 provider: **NOT_RUN** — штатный оплачиваемый доступ/бюджет для
  этого прогона не предоставлен; секреты не искались. Для deterministic Recommendations
  provider smoke **не применим**.
- 8.1: предметная корректность admission не утверждается; в 10.3 проверяется
  исполнение существующего механизма и передача его ограничений.
- Исходный CASE-TDISC-04: методологический блокер остаётся; нужен методологический
  ответ по условию ветви Аси. Synthetic character fixture проверяет только механику.
- Экспертный просмотр рекомендаций и approved GC: не выполнены, требуется
  методолог/эксперт. Reliability в сохранённой выдаче — `not_verified`.
- Merge/deploy/пилот/Prod и FROZEN/CURRENT/baseline не выполняются и не утверждаются.
  Решение о приёмке и выпуске остаётся у владельца.

Ревью: собственные изменения ограничены данной цепочкой; миграции/удаление истории
отсутствуют, server ownership сохранён; сгенерированный web/dist соответствует исходникам.
В test gateway нет production fallback; guard требует owned local `product4k_pytest_*`.
Откат — revert изменения 10.3 и штатное уничтожение только созданных им стендов.


## Итог локальной проверки и воспроизведение

Проверена общая сборка от исходного `7aebd3c` с diff данной задачи. Точные SHA-256
изменённых исходников, fixtures, тестов и сборки перечислены в
[снимке кандидата](artifacts/task10-3/candidate.json); это идентификация проверенного
дерева, не присвоение baseline. Версии/хеши источников —
[sources.json](artifacts/task10-3/sources.json).

| Команда / проверка | Фактический результат |
| --- | --- |
| `npm run test:backend` | PASS: 342, deselected 111 |
| `npm run test:backend:http` | PASS: 29 |
| `TEST_DATABASE_URL=postgresql://vadim_bogachev@127.0.0.1:55491/task11_pytest npm run test:backend:integration` | PASS: 78, deselected 375; только выделенный локальный кластер |
| `node --test tests/frontend/*.test.mjs` | PASS: 3 |
| `npm run lint:js` | PASS: корневые и ранее проверяемые JS-файлы |
| `npm run build:web` | PASS, web/dist включён в изменение |
| `STAND_ADMIN_URL=postgresql://vadim_bogachev@127.0.0.1:55491/postgres npm run test:browser` | PASS: 6, retries=0, без skips |
| `git diff --check` | PASS |
| GitHub CI `frontend`, `pytest` | Проверяется после публикации данного кандидата; локальный PASS не заменяет CI |

Команды создания стенда/зависимости и Linux Xvfb:
[tests/browser/README.md](../../../tests/browser/README.md).
Окружение локального прогона: Python 3.12.13, pytest 9.1.1, Chromium (точная версия
во вложениях). Реальные пользовательские аккаунты не задействованы.

**B10.3-01–10 и B10.3-12: PASS в явно указанной в матрице технической области.**
У B10.3-11 локальная воспроизводимость PASS; удалённый CI до запуска NOT_RUN.
Составные подпроверки не расширяют своё покрытие: новые Cycle, regenerate и запреты
проверены owner HTTP; четыре исхода, leases и часть гонок — backend. Исходный
CASE-TDISC-04, реальный provider, нормативная 8.1, GC и экспертное заключение
остаются отдельными ограничениями, перечисленными выше.

Доказательства: [index.json](artifacts/task10-3/index.json) содержит название,
статус, длительность и SHA-256 каждого вложения. Папки scenario-1…6 соответствуют
A/positive/N1–N5, B, C1, C2, Recovery, synthetic character. В них находятся реальные
скачанные PDF, сохранённые Report/Results, UI, безопасные HTTP-ответы и серверные
логи. C1 отдельно фиксирует `visibility=hidden`, состояние до/после expiry и поздний
Turn 409. Первые падения сохранены в файлах a2/bc/all2/all3/visibility/headed и сопоставлены с таблицей дефектов.
После последнего исправления выполнен полный browser suite; выход и смена аккаунта
проверяются реальной кнопкой «Выйти».

Визуально просмотрены PDF: кириллица, длинные названия/цитаты, таблицы,
рекомендации, ограничения и перенос между страницами читаемы; обрезания текста
не обнаружено. Автоматическая сверка каждого скачанного PDF с C-67 — PASS.

Результат для владельца: пользователь проходит новый runtime, уточнение, Additional
Session, восстановление после фонового закрытия и получает сохранённый Report/PDF.
Подтверждены ссылки допустимых Recommendations на материал, ограниченный набор типов
и безопасные отрицательные варианты. Техническое ревью агента выполнено по EVC;
человеческая приёмка и решение о выпуске остаются за владельцем. Общий
[Draft PR #32](https://github.com/VadikB/4K_MBTI/pull/32) сохраняет статус Draft.

При упаковке текстовых логов удалены только хвостовые пробелы; PDF/PNG сохранены
побайтово. Локальный .gitattributes отмечает бинарные PDF/PNG для корректного Git diff.
