# Task 10.2 — воспроизводимый изолированный стенд

## Разведка и план

Актуальный main после fetch: `14cf514e5420fe095a45285619498024b73c0c0e`.
Начало работы: `4c051f2d0967a351576071a9fd5df9e2bd7b7d0b`, чистая ветка
`codex/task11-1-recommendation-basis`, общий Draft PR #32. По решению владельца
10.2 — второе изменение общего PR, отдельный коммит; merge/deploy запрещены.

Прочитаны README, CONTRIBUTING, EVC workflow/matrix/artifact recipe,
контекст Change 01 и ранее выбранные источники, Task 10/10.1/11, database/config,
main, auth/web sessions, M10 flow/orchestration, тесты и CI.
Блокер: отсутствует исходная схема до добавочных ensure_core_schema migrations.
Обнаружена также скрытая несовместимость: _owned_profile сортирует по created_at,
а каноническая M4 таблица имеет frozen_at (тестовая fixture скрывала дефект).

1. Выполнено: восстановить версионируемый bootstrap из потребителей SQL и существующих
   контрактов; отделить структуру, миграции и seed. Исторические рабочие БД не трогать.
2. Команда одноразового локального стенда с собственными PostgreSQL/processes,
   явной конфигурацией, защитой повторов/чужого контура и test gateway.
3. Синтетические исходные данные; настоящий owner HTTP/worker путь до Report/PDF.
4. Два чистых запуска, негативные проверки, CI и минимальная browser-проверка;
   инструкция и передача 10.3. Результаты проверок приведены ниже.

Совместимость: bootstrap предназначен для пустого изолированного контура и его
собственных версий; неизвестная существующая схема не принимается автоматически.
Исторического DDL в Git не найдено; не объявлять миграцию рабочих БД проверенной.
Откат: остановить и удалить только созданный стенд; рабочие контуры не меняются.

## Результат и решения владельца

Реализован bootstrap v1 → существующие ensure-миграции → отдельный synthetic seed →
настоящий main:app/workers → owner HTTP до сохранённого C-67/PDF. Команды и версии:
[инструкция](../test-stand.md). Технические AI-ответы заменяет только явно включённый
изолированный gateway; рекомендации исполняются штатно, на общей версии с 11.1.

Владелец в текущей сессии: «нужно по возможности убирать все legacy». Вместо
восстановления отсутствующего user_assessment_progress удалены его потребитель и
legacy-агрегация dashboard в Api/routes.py. Экран читает Cycle/AS/Report; фиксированные
«5 кейсов» и промежуточный процент убраны. Совместимые поля API сохранены; старые
записи не удалялись. Полное удаление auth/profile/admin legacy не входит в эту
инфраструктурную задачу. Это ограничение, а не утверждение о готовности всего legacy UI.

Дополнительно исправлены два выявленных блокера: M4 lookup использует frozen_at
(реальное поле канонической таблицы); optional legacy templates/rules не ссылаются
на отсутствующие паспорта F04/F08 при чистом старте. Новые предметные нормы и
паспортные данные не придуманы. Импортируемые подсистемы не отключены.

## Источники, версии, границы

Прочитаны README.md, CONTRIBUTING.md, docs/evc/{agent-workflow,verification-matrix,
artifact-recipe,review-checklist}.md; docs/architecture/product-4k/1.0/context.md,
registry.md, 1.0/updates/2026-10-01/README.md и выбранный manifest Change 01;
ADR 002 и контракты текущего Cycle runtime; отчёты задач 10/10.1/11/11.1.
Технические источники: Api/{database,config,agent,auth_service,web_session_service,
m10_product_flow,m10_test_gateway}.py, main.py, tests/conftest.py, tests/README.md,
package.json, CI, test_m10_product_path_db.py. Постановка: Task 10.2, редакция 1,
05.10.2026 (путь исходного TXT указан в сообщении владельца).

M1 v1.4 FROZEN / CURRENT=NO остаётся понятийным источником; CURRENT не присвоен.
PM-04 выполняет Turns, PM-05/06/07 рассчитывают/интерпретируют/представляют по
существующим контрактам. Task 10.2 меняет инфраструктуру их запуска, не методологию.
Seed v1 находится в scripts/test_stand_seed.py; M2/M3 публикуются штатным QA lifecycle,
M4 snapshot создаётся штатно. M5 использует изолированный synthetic fixture-допуск
существующего integration-теста. Исходные пакеты не перепубликуются и не меняют статус.

Пробел: достоверного полного исторического base DDL нет. Происхождение bootstrap
описано в database/bootstrap/v1/README.md. Совместимость подтверждается только для
собственного v1 и повторного запуска; миграция неизвестной исторической БД запрещена.
Стоп-условия проверены: новых предметных контрактов/артефактных форматов, переноса
рабочих данных, изменения прав или внешних интеграций нет. Создание схемы разрешено
постановкой только в собственной автоматически создаваемой disposable БД.

## Изменённые пути

- database/bootstrap/v1/{base.sql,README.md}, Api/schema_bootstrap.py: базовая
  структура, версия/checksum, fingerprint структуры, отказ для неизвестной схемы.
- scripts/test_stand{,_seed,_smoke,_check}.py: создание/владение/cleanup, входные
  fixtures, реальный HTTP, два старта и сохранение того же результата.
- Api/config.py, Api/m10_test_gateway.py, main.py: явная изоляция, запрет .env
  fallback, проверка схемы при старте/readiness, обозначение режима gateway.
- Api/database.py, Api/m10_product_flow.py: блокеры чистого старта, указанные выше.
- Api/routes.py, web/js/screens/dashboard.js, web/dist: удаление legacy dashboard.
- tests/unit/test_test_stand.py, tests/integration/test_clean_bootstrap_db.py,
  tests/integration/test_m10_product_path_db.py: регрессии и реальный entrypoint.
- .github/workflows/backend-tests.yml: uvicorn для subprocess smoke, обязательные
  jobs сохранены; .gitignore: SQL bootstrap в Git, state стенда исключён.
- docs/evc/test-stand.md и этот отчёт: запуск, ограничения, передача.

## Проверки

Команды выполнены на синтетическом локальном PostgreSQL 15.16, localhost:55491;
рабочая БД и .env не использованы. Безопасный TEST_DATABASE_URL задан явно.

| Команда | Результат |
|---|---|
| npm run test:backend | PASS, exit 0, 340 passed / 109 deselected |
| npm run test:backend:http | PASS, exit 0, 29 passed |
| .venv/bin/python -m pytest --run-integration -m integration | PASS, exit 0, 76 passed / 372 deselected (до последней проверки source_hash; затронутая регрессия повторена отдельно) |
| pytest --run-integration -m integration tests/integration/test_clean_bootstrap_db.py -q | PASS, exit 0, 2 passed; два независимых положительных прогона и отдельные отрицательные |
| npm run lint:js | PASS, exit 0 |
| npm run build:web | PASS, exit 0 |
| node --test tests/frontend/*.test.mjs | PASS, exit 0, 3 passed |
| git diff --check | PASS, exit 0 |

Deselected — разделение по маркерам, не пропуск обязательной проверки.
Полный GitHub CI на новом head ожидает push; локальные проверки не заменяют CI.

| Критерий | Статус и доказательство |
|---|---|
| E10.2-01 | PASS локального пути: create подтверждает application_tables=0, настоящий main и workers, HTTP/UI. Дополнительная проверка чистого checkout фиксируется ниже. |
| E10.2-02 | PASS: test_two_empty_database_application_starts_and_owner_http_reports создаёт два разных UUID/БД, без fixtures схемы. |
| E10.2-03 | PASS: каждый прогон повторяет bootstrap/seed, рестарт и чтение того же report_id/revision; данные не сбрасываются. |
| E10.2-04 | NOT_RUN историческая миграция: достоверного предыдущего base нет. PASS повтор собственного v1; неизвестная схема/структурный drift отклоняются. |
| E10.2-05 | PASS: unit unsafe/missing config и отрицательный integration с чужим marker; destroy только своей БД, без FORCE. |
| E10.2-06 | PASS: обычный password login, start/resume, два Turns и owner completion, реальные subprocess/workers. |
| E10.2-07 | PASS: сохранённые C-67/PDF, повторные чтения равны, после рестарта тот же ID, другой участник получает 403. |
| E10.2-08 | PASS для неприменённой/повреждённой схемы и отсутствующего provider: реальный entrypoint отказывает, adapter не включает mock. Отдельное отключение живого PostgreSQL во время работы не выполнялось. |
| E10.2-09 | PASS локальная регрессия; добавлена в обязательный integration CI, без TEST_DATABASE_URL — fail. CI нового head ожидается. |
| E10.2-10 | PASS минимальный UI: synthetic other login → подтверждение профиля → Продолжить → Начать → активная AS «Запуск в пятницу: что именно готово?», console errors []. Cleanup собственной БД проверяется автоматическими прогонами. |

Артефакты ручного прогона: /tmp/e102-d/{create.log,app.log,smoke.log,smoke.json,
report.json,report.pdf}; state.json содержит credentials и не публикуется.
Cycle f775f6a4-5418-4793-b480-593692abbd0d,
Results revision a8cec29e-1301-443f-b972-a604c89c000a,
Report aff13d80-23ab-495a-9fe8-3b5eaa314099, revision 1,
report mechanism m8_basic_report 1.2.0,
checksum 3242ad6a95ce5b8d6457b2732a6b71b650b377e190aa7dddd737f8f1b66f4e54.
Режим synthetic; recommendation_status=ready. Это техническое доказательство
сохранения/выдачи общей версии 11.1+10.2, не содержательная валидизация оценок.

## Риски, откат и передача

Конфиг: stand читает только явный localhost admin URL и локальный state; state
0600, случайный пароль, в Git не попадает. Схема: marker/source/fingerprint
защищают собственный контур; частичный base атомарен, успешный schema_hash
выставляется после миграций. При неизвестной схеме нет автоматического ремонта.
Деплой: test/prod не изменялись; merge/deploy в этой задаче не выполняются.
Откат: остановить свой foreground serve (Ctrl+C), выполнить destroy по инструкции;
отмена реализации — revert коммита 10.2. Рабочие snapshots и БД не затрагиваются.

Review выполнено по EVC: смысл оценки/пакеты/права сохранены, управляющие документы
не ослаблены, bootstrapping не скрыт fixtures, регрессии выполнены. Человеческая
приёмка и CI обязательны перед merge. Baseline не присваивается.

S10-A/B/C, T11-10 и реальный provider — NOT_RUN. Следующий этап 10.3: новый чистый
state без предварительного smoke, общая сборка 11.1+10.2 и полная browser-трасса.
Методологические GC/Reliability этой задачей не утверждаются. Открытых вопросов,
блокирующих техническую реализацию стенда, нет.
