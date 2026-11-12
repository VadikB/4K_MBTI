# P4K-F05-F09-ONE — сведения и переходы оценки

Основание: поручение пользователя от 12.11.2026 и приложенная постановка
`P4K_F05_F09_ONE_TASK_2026-11-12.txt`, редакция 1.0. Внешний файл задаёт
критерии; факты о коде, базе и готовности проверяются отдельно.

## Результат и граница

Один локальный кандидат для F05–F09: действующая подтверждённая редакция при
новом черновике; защита назначения от поздних ответов; правдивый исход Turn;
ограниченное клиентское ожидание Finish и Next с readback той же команды.
F03/F04, платный LLM, реальные письма, методологические нормы и публикация
артефактов не входят.

База `origin/main@c06e94d5ff3784b2788b44089091a62a3921d301` после fetch
12.11.2026. Ветка `codex/f05-f09-one`, worktree `/private/tmp/p4k-f05-f09-one`.
Исходный checkout содержит чужие изменения и не редактируется. `gh auth status`
показал отсутствие входа; push/PR/merge/deploy не санкционированы прямым
поручением и локально не выполняются. `version_bump=false`,
`artifact_publish=false`.

## Источники и решения

Прочитаны `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
`docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`,
`docs/evc/review-checklist.md`, `docs/architecture/product-4k/1.0/context.md`,
`docs/architecture/product-4k/registry.md`, Change 01 `README.md` и task
`manifest.json` от 01.10.2026. Применяются M4 v1.0, M5 v1.1, M7 v1.3,
Change 01 WORKING, действующие контракты и опубликованные snapshots; это
не присвоение CURRENT и не допуск нового содержательного runtime.

Принятые роли доступа, подтверждение сведений, C04, snapshots, ASK и явный Next
не меняются. Технические клиентские пределы ожидания не являются серверным
deadline и не превращают неизвестный исход в отказ.

Выбранные основания (SHA-256): постановка 1.0 `d0c98e22ce27579e9fb591c9da59e917ea57bfe754fa2448d9bdad85f03e6b13`;
SourceSet manifest `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8`;
Change 01 README `ac082bb94aac1b86c61d7e39589d76c886c6703ef3afc07bc8fecf1676a0a26d`;
M1 v1.4 README `f772f8d244c46f6a52924e18ac58dcbea3b603163b3b1da806e574e4cc077795`;
M1 v1.4 source `282e69b87585c28b52327e657d71a620c15842f7ade134467788252829833299`;
Change 01 source `ee03f59d78e441f69964352bcd94a1e7c375c2ce306433a8d0cd056ba3af93d2`;
M7 v1.3 derived `9b65a8eee1520fed57286b209a28ce73e33cd394ba8c9353c240673867483ec8`;
ADR 002 `4a4e0170bee7faf137301b342fec46b3e8e0209acd26dcb6b2dc7a788c58b25f`;
traceability `e528baedfa7bfa2f6aa8fdf9ea2ec4c3e092c32cedb5fa4068f0abc0af1d3eaa`.
Прочитаны относящиеся к задаче И-2/3/4/5/6 и M1.4–10 через маршрут Change 01,
M5 execution и M7 planning/clarification/completion contracts; не пересматривалась
вся история M1.

Связь требований: M1/И-2/3 и C-24/34 → подтверждённый источник организации,
точная область назначения → `Api/questionnaire_sources.py`, `Api/routes.py`,
`web/js/screens/admin/organizations.js` → E3/E4/E5. M1.6–8, C-45/54 и T05–T09
→ один Turn, ASK и закрытие AS → `web/js/screens/interview.js` → E1/E4/E7/E9/E11.
M1.9–10, C-46 и T10 → явный Next и bounded техническое ожидание →
`web/js/product-cycle-preparation.js`, `web/js/screens/interview.js` → E1/E4/E6/E9/E11.
Код не вводит новые предметные нормы, артефакты и схемы БД.

## Активный план

1. F05: API и UI для действующей редакции и черновика; адресная регрессия.
2. F06: поколение экрана и защита всех ветвей назначения; адресная регрессия.
3. F07: известный отказ и неизвестный исход Turn; адресная регрессия.
4. F08: Finish, bounded wait, readback и восстановление; адресная регрессия.
5. F09: Next, bounded poll, статус и адаптивная кнопка; адресная регрессия.
6. Общие 18 AC и MERGE-AC01, локальный минимум, browser/owned PostgreSQL,
   review, пакет передачи одного кандидата.

## Проверки и откат

Применима объединённая строка матрицы для JS с поведением, HTML/CSS и backend:
`git diff --check`, `npm run lint:js`, `npm run build:web`, frontend tests,
`npm run test:backend`, HTTP-контракты, integration на изолированной owned
PostgreSQL test/pytest и browser acceptance. Фактические итоги — в `CHECKS.md`.
CI `frontend`, `pytest`, `full-verification` требуется до слияния.

Откат: revert только изменений этой ветки и пересборка `web/dist` на исходном
SHA. Схема БД и опубликованные определения не изменяются.

## Описание одного PR для передачи

**Заголовок:** F05–F09: подтверждённая редакция, защита назначения и восстановление Turn/Finish/Next.

**Содержание:** API отдаёт последнюю редакцию отдельно от действующей
подтверждённой; UI назначения проверяет точную область и поколение экрана;
интервью различает известный отказ и неизвестный исход, сохраняет идентификаторы
команд до отправки, ограничивает ожидание и проверяет исход той же команды;
карточка Next читаема на мобильных экранах. Публичный API дополнен полем
`effective_confirmed`, схема БД и опубликованные артефакты не меняются.

**Проверки:** команды и фактические результаты по всем 19 критериям в
`CHECKS.md`; локально 19 PASS. Объединённый E32/E33 путь использует
опубликованный источник и контролируемый тестовый provider без внешнего LLM;
первый явный Next проверен в browser/owned PG, полный PATH/F22 и качество
реального LLM не заявлены. Исходный кандидат `5091e13e` получил в полном
integration gate E34 один R03 FAIL, воспроизведённый на неизменённом
`origin/main`. Прежняя запись `Retry-After: 0` была ошибочным прочтением
pytest: точный HTTP readback показал 10807 секунд при cooldown 7 и зоне
Europe/Moscow. Отдельный R03 commit `4e6bffa4` проверен вместе с кандидатом
во временном checkout `b6996a54`: полный локальный integration gate E35 —
393 PASS, 2 SKIP явного real-provider, 0 FAIL. Изначальная ветка F05–F09 не
получала R03 fix; после принятия PR #213 база обновлена до `e7cd26dc`.
Ветка отправлена в `origin`, создан draft PR
[#214](https://github.com/VadikB/4K_MBTI/pull/214); быстрый CI на `6b23f69e`
прошёл (`frontend`, `pytest`), полный CI для draft штатно пропущен.
Полный CI, TEST и human review F05–F09 ещё не выполнены. Отдельный
R03 PR [#213](https://github.com/VadikB/4K_MBTI/pull/213) на
`a3f8eb54ba2378c25bafe62ebd6389b9243cb881` прошёл полный CI после
повтора одного непостоянного browser timeout на том же SHA; владелец принял
human review и разрешил squash merge с test deploy. R03 вошёл в `main` как
`e7cd26dc`; `deploy-test` #973 PASS. Объединённая ветка F05–F09 локально
прошла frontend 271, backend unit 1089, HTTP 153, lint/build/diff PASS;
полный local integration точного merge SHA не повторялся. Следующие действия:
проверить CI нового draft SHA, согласовать новую версию для F05–F09, выполнить
Ready preflight и полный CI, затем отдельные приёмка/merge/TEST по процессу.

## Адресный review кандидата 12.11.2026

Свежий `git fetch origin main` оставил базу `c06e94d5ff3784b2788b44089091a62a3921d301`.
Проверен diff `origin/main...e5d903496c53c516ff46e6977ab732b43feaa221`:
`Api/questionnaire_sources.py` и `Api/routes.py` добавляют действующую
подтверждённую редакцию без смены схемы и предметных источников;
`web/js/screens/admin/organizations.js` удерживает scope назначения и
раздельно показывает draft; `web/js/screens/interview.js` и
`web/js/product-cycle-preparation.js` сохраняют ID команд, ограничивают
клиентское ожидание и делают readback; `Api/m10_test_gateway.py` и
`scripts/test_stand.py` меняют только изолированный синтетический контур.
Публичное поле `effective_confirmed` добавлено, существующие поля сохранены;
новых миграций, runtime-предметных defaults и публикации артефактов нет.
Адресные регрессии и owned browser/PG для этих границ указаны в `CHECKS.md`.
`git diff --check origin/main...HEAD` — PASS, рабочее дерево до этого
документального checkpoint было чистым. Новых дефектов review не выявил.
Остаточный риск: прежние записи и старые клиентские состояния проверены только
в описанных синтетических сценариях; полный PATH/F22 и реальный LLM не заявлены.
