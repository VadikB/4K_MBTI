# UX-ADM28-ADD01 v2 — путь администратора на HTTPS

## Результат и область

Основание: запрос владельца «выполни START_CODEX.txt», продолжение 28.10.2026.
Один результат и один PR: TASK01 → TASK02 → TASK03 внешнего пакета v2.
Включено: видимые операции, конечное подтверждение с восстановлением неизвестного
исхода, согласованные получатели и назначения; управление/собственная оценка;
восстановление сессии, публичная статика, единый PATCH-кандидат и test HTTPS.
Не входят: M1–M8, нормативные таймеры, production/pilot, публикация артефактов.

## Источники и решения

База: `9d7c9eaacf101fd3c48d7059bd68a96cf7176d87`, `origin/main`, 2.0.32.
Ветка: `codex/ux-adm28-add01-v2`. Исходная рабочая копия сохранена.
Прочитаны: README.md, CONTRIBUTING.md; docs/evc/{agent-workflow,
verification-matrix,artifact-recipe,task-template,review-checklist}.md;
docs/architecture/product-4k/{1.0/context,registry,m1/v1.4/README}.md;
Change 01 README, task SourceSet manifest, ADR-002, change01-traceability;
карточки UX-ADM27/28; START_CODEX, REPORT, TASK01–03, CHECKS внешнего пакета.
M1 1.4 FROZEN/CURRENT=NO, Change 01 WORKING; применимость — сохранение границ
PM-02/03/04/07, прав и снимков, без изменения методологических норм.
Подтверждение контекста/назначение не начинает Cycle, оценку или таймер.

Решение владельца в START_CODEX: одна ветка/один PR, push, один PATCH bump,
merge после зелёного CI актуального head и технического review, deploy только
https://test.4k-assistant.ru/. Визуальная приёмка владельца/маркетолога PENDING.
Стоп-условия рабочего цикла: все восемь — нет в согласованной области;
схема/API сохраняются, данные не мигрируют, новые предметные нормы не вводятся.
Пробел: фактические версии/целостность HTTPS ещё требуется установить;
полная браузерная матрица зависит от доступных платформ.

## План и состояние

1. TASK01 реализован и проверен адресными HTTP/PostgreSQL/браузерными тестами.
2. TASK02 реализован; Chromium и сверка четырёх ширин выполнены.
3. TASK03 реализован; единственный кандидат 2.0.33. Активны итоговая integration,
   передача одним PR, обязательный CI, человеческое review и выпуск на HTTPS-test.

## Проверки

Матрица: JS с поведением, HTML/CSS, backend, поведение БД, публикация/auth,
сборка/release. План: lint/build/frontend; backend unit; HTTP;
PostgreSQL integration на изолированной test/pytest-БД; Playwright с mock API
и отдельный синтетический путь на реальном изолированном backend;
визуальная сверка 1440/1280/390/320; проверка HTTPS release assets;
обязательный CI frontend/pytest. PASS/FAIL/NOT RUN фиксируются фактически.
Реальные письма и LLM не требуются. Секреты/PII в evidence не сохраняются.

## Откат и риски

Совместимый revert PR; опубликованные контексты и назначения сохраняются.
Штатный deploy_test_remote.sh откатывает код при неуспешном smoke.
Схема/предметные пакеты не меняются. Неизвестный исход POST восстанавливается
чтением точной редакции; автоматического повторного POST нет.

## Передача

## Результат и причины

- H01: общий статус вынесен из скрываемой create-card. Результат/loading/error
  также показываются рядом с действием, с aria-live и фокусом; у блокировки
  назначения есть переход к данным конкретной выбранной оценки.
- C01/C02: confirmed POST сразу отражается, дополнительный GET выполняется отдельно.
  GET ограничен 15 секундами, остальные запросы — 30; deadline включает чтение body.
  Неизвестный исход POST блокирует повтор этой редакции и даёт «Проверить результат».
  Новый scoped GET читает точную редакцию, сохранённые recipient mapping/IDs.
  Дополнительный сбой readiness после commit возвращает известный успех с
  `readiness_refresh_required`, а не ложный rollback.
- Реальный backend обнаружил `KeyError: C02b`: продуктовая форма передаёт ранний
  минимум без необязательного вопроса. Отсутствующий ответ остаётся пустым;
  обязательные поля и методологические правила не меняются.
- H05: единая нормализация получателей вызывается и при событии, и после восстановления
  draft/render. Обязательный участник readonly; скрытые IDs не отправляются.
  Во время POST выбор заморожен. Новый account/assessment/preview не затирается
  поздним подтверждением. Повтор с теми же получателями идемпотентен;
  другой набор у confirmed-редакции даёт 409.
- C03: readiness участников и legacy-подготовки использует одну scope-выборку:
  действующие прямые назначения UNION совместимые legacy invitations,
  active organization/membership, выбранная оценка, без дублей и revoked.
- H02/H03/H04: первый org-admin попадает в управление; восстановление показывает
  нейтральную оболочку и конечный retry при временном сбое. Superadmin сохраняет
  global dashboard. Собственная оценка маршрутизируется по server journey,
  имеет одну навигацию и согласованное пояснение self-assignment. Локальный
  выбор организации/подраздела/оценки хранится по user ID и проверяется сервером.
- H06/H07: при нуле завершённых оценок сервер не отдаёт выводов о сильной/слабой
  группе. Убраны лишние вложенные карточки org-admin, сохранены все поля и API;
  Onest в графиках, графит в hover/focus/disabled, шапка «4К Ассистент».
- C04: restore делает одну загрузку организаций и анкет. Оба middleware пропускают
  session lookup и DB audit для уже публичной статики; API сохраняют auth/audit.
  Синхронные lookup/audit выполняются в threadpool. Session DDL выполняется при
  штатном startup, а не внутри запросов.
- TASK03: release-рецепт генерирует и проверяет статические badge из единого номера;
  version endpoint не блокирует первую отрисовку и не подменяет frontend release.
  Политика no-store/retention immutable chunks не менялась без измерений.
  Workflow сообщает конкретную фазу ошибки Configure SSH, fingerprint неизменён.

## Изменённые файлы

- `Api/questionnaire_sources.py`, `Api/routes.py`: подтверждение, readback,
  recipient projection, выборка назначений, пустая сводка.
- `Api/web_session_service.py`, `main.py`: startup DDL, public static, threadpool.
- `web/js/{api,main,router,session,wiring}.js`, `web/js/entries/admin-organizations.js`,
  `web/js/screens/admin/{organizations,charts}.js`: транспорт, навигация и операции.
- `web/index.html`, `web/styles/screens/admin-organizations.css`, `web/dist/`:
  оболочка/компоновка и собранный кандидат.
- `scripts/release_version.py`, `pyproject.toml`, `uv.lock`, `web/js/config.js`:
  единый PATCH 2.0.33; `.github/workflows/backend-tests.yml`: диагностика SSH.
- `scripts/adm28_browser_fixture.py`, `scripts/check_https_release.py`, адресные
  unit/frontend/HTTP/integration/browser tests и evidence: воспроизводимость.

## Источники и прослеживаемость

START SHA-256: `37b615b57103666a1b9f3f8b0abd30a096e8b7414563f744c926bff357b84565`;
REPORT: `4a9ae04da0e9758d34c472ecbff1626cb99870d78166f232559379242039bc0b`;
CHECKS: `87554e0c613d4f924cedc51102c4f456db2d5b181b094b37a65f3c39833dbd74`.
Prototype identity: `998be27831d8a35aab0b7930d5ac1fccb8431738e20d3922e9332cc6b5a18228`;
18/18 файлов совпали, source commit `26076fd9b9f2de4806803034b16ac2916e2d82bd`.
Прочитаны DESIGN_CONTRACT и исходная раскладка эталона; эталон не менялся.
Change 01: И-1, И-2, И-6/7; M1 source 1.4 checksum в task manifest
`5fa5ab5735dfe57fac6ef3c93aca50d149fbd7abd365edf80d362c10e2d7a975`.

| Правило / граница | Контракт / данные | Реализация | Доказательство |
| --- | --- | --- | --- |
| M1/И-2: подготовка не запускает Cycle/время, PM-02/03 → PM-04 | questionnaire revision и assignment; journey | confirm/readiness/assignment, admin navigation | real isolated browser: starts=0, roles=incomplete, preparation=idle, затем W02 |
| И-6: версии, повторы, права | immutable confirmed revision + recipients; scope organization/user | idempotent confirm, 409 на замену, scoped GET | PostgreSQL + HTTP foreign scope 403; lost-response browser check |
| T12 / PM-07: выдача по действующим правам | recipient mapping и report-access revision | сохранён существующий m8_report_access lifecycle | integration report-access и неизменные API gates |
| UI не создаёт фактическую оценку | ноль завершённых сессий | пустое состояние `_build_admin_dashboard` | real isolated browser: нет strongest/weakest выводов |

Подключение источника и проектирование методологии этой задачей не выполняются;
runtime M1–M8 не объявлен соответствующим всему комплекту. Предметные пакеты и
исторические snapshots не изменены, ART-долг не расширен. Изменений управляющих
документов нет. Человеческое review и визуальная приёмка остаются отдельными.

## Проверки (фактические команды)

- `npm run lint:js` — PASS; `node --test --test-reporter=dot tests/frontend/*.test.mjs` — PASS, 82.
- `npm run build:web`; `scripts/check_release_version.py` — PASS, 2.0.33.
- `.venv/bin/python -m pytest -m 'not integration and not llm' -q` — PASS, 679:
  598 unit и 81 HTTP, реального LLM и рабочей БД нет.
- Полный integration на собственном `agent4k_pytest`, localhost:55448: первый прогон
  165 PASS / 2 FAIL / 2 llm SKIP. Причина двух FAIL — fixture без явного startup
  web-session schema после выноса DDL из запросов. Fixture исправлена;
  повтор двух затронутых файлов — PASS, 15. Повтор полного набора выполняется.
- `npx playwright test tests/browser/adm28-real.spec.mjs tests/browser/auth-r03.spec.mjs`
  — PASS, 60; после финальных адресных правок — PASS, 16 затронутых сценариев.
  Один реальный локальный backend/PostgreSQL, остальные UI mocks различены.
- `sh -n scripts/deploy_test_remote.sh`; YAML parse workflow; `git diff --check` — PASS.
- Реальная выдача HTTPS до выпуска:
  `scripts/check_https_release.py --url https://test.4k-assistant.ru/ --ref …`
  — PASS как диагностика: 71/71 asset совпал с `0b44c26541f26adac067c7f5f08eda3d416ff862`,
  frontend/backend 2.0.31. Свежий main 9d7c9ea / 2.0.32 на HTTPS не опубликован.
  [Хеши и время сетевых запросов](../evidence/ux-adm28-add01-v2/https-before.json).
- CI main: frontend/pytest PASS, deploy-test FAIL на Configure SSH до удалённого
  deploy: [run 40681057735](https://github.com/VadikB/4K_MBTI/actions/runs/40681057735).
  Логи не определяют однозначно, какая команда Configure SSH завершилась с 1;
  добавлена фазовая диагностика. Это не доказательство ошибки самого приложения.

## CHECKS: среда, статус, предел доказательства

| № | Локальный результат | HTTPS после выпуска |
| --- | --- | --- |
| 0 выпуск | PASS: свежий main, 2.0.33 candidate, хеши старой публикации | NOT RUN: новый release ещё не deployed |
| 1 вход | PASS: существующий пароль, org-admin management; mock superadmin global; own journey | NOT RUN |
| 2 refresh | PASS: neutral restore, retry на 503, реальные reload management/W02 | NOT RUN |
| 3 данные | PASS: карточка, draft, автор/поля после нового GET/reload | NOT RUN |
| 4 preview/recipients | PASS: пустой выбор, допустимый выбор, возврат по вкладкам, stale source guard | NOT RUN |
| 5 публикация | PASS: real PostgreSQL/HTTP/readback; mock delayed GET/lost response/409/invalid JSON/new preview | NOT RUN |
| 6 назначение | PASS: self + colleague без письма/аккаунта, revoked/foreign/dedup scope | NOT RUN |
| 7 моя оценка | PASS: no-assignment explanation/возврат; assigned W02/reload; start=0 | NOT RUN |
| 8 оформление | PASS: локальная Chromium-сверка 1440/1280/390/320, keyboard/layout; human acceptance PENDING | NOT RUN |
| 9 загрузка | PASS: одна загрузка ресурсов, static cookie без DB, HTML badge до JS; CI ожидается | NOT RUN |

Полная iOS Safari/Яндекс/Chrome, Android Chrome/Яндекс, Windows Chrome/Яндекс,
macOS Safari/Chrome/Яндекс — NOT RUN: доступен автоматизированный Chromium, который
не доказывает эту матрицу. Внешний deploy и сопоставимые HTTPS-измерения до/после
— NOT RUN до разрешённого выпуска; имеющиеся durations — настоящие сетевые
измерения одного состояния, не «ускорение» и не длительность инструмента.
Отправка реального письма — NOT RUN: в owned stand mail provider выключен;
проверен видимый отказ 503, а успешная интеграция provider — controlled-sink HTTP
и PostgreSQL regressions. Реальные пользовательские права не менялись.

## Review, риски и следующий шаг

Технический self-review выполнен: API только расширен scoped GET/полями;
схема и параметры среды не меняются; auth/expiry/revocation и DB audit защищённых
API сохранены, published snapshots не меняются. Дополнительный риск — consumers,
вызывающие WebSessionService вне приложения: они должны явно вызвать startup
ensure_schema (production main и штатный stand уже делают это).
Риски config/schema: нет миграции; deploy: существующий SSH gate требует исправного
доступа environment test; безопасность: fingerprint/StrictHostKeyChecking сохранены;
откат: revert PR, штатный test rollback, без удаления опубликованных контекстов.

Следующий шаг: завершить полный integration, один PR и CI актуального head,
человеческое review; после этого merge/test deploy и повторная HTTPS-сверка.
Визуальное принятие владельцем/маркетологом — PENDING. Baseline не присваивается.
