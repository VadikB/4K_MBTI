# AC18-AUTH-READY-01 — готовность формы после проверки ссылки

07.11.2026. Владелец явно разрешил узкое локальное исправление и бесплатные
регрессии: «Да, исправить локально и проверить бесплатно».

## Результат и границы

До завершения server confirm/reset validation нельзя вводить или отправлять
пароль. После валидной проверки доступны штатные два шага; отказ остаётся
fail-closed. PATH29 ждёт готовую форму, а failure evidence снимает активную вкладку,
не пустую вкладку участника. Ни server auth, ни права, ни PM-03/04 не меняются.

Все release flags `false`: bump, push, PR, merge, deploy, artifact publication.
Рабочая БД/.env, prompts/admission/repair и новые полные PATH/LLM исключены.
База свежего origin/main: `339aff9034ff005bc20d072876b3fbef4f834c5e` /2.0.74;
отдельная локальная ветка `codex/ac18-auth-readiness`. Чужой root worktree сохранён.

## Первичное исполнение и неизвестное

После официального Resolved07:56UTC разрешённый one-shot AC18 run
`2835475f27a64c89b273887ee3e38a76` завершился FAIL08:06:24UTC, до preparation/LLM.
Ожидание: auth step2; факт: step1 (5s). HTTP email confirm200, register не начат.
Owned cleanup и отдельный maintenance READ ONLY/rollback absent readback PASS.
Новый run не повторялся. Original failure PNG — пустая вкладка участника;
она НЕ доказывает вид формы администратора. Историческая причина этого run
UNKNOWN, связь с воспроизведённой гонкой NOT_PROVEN. PREP-DIAG-01 — отдельно UNKNOWN.

Без БД/LLM на неизменённом UI воспроизведена ранняя доступность формы до завершения
confirm: ввод обнуляется поздним configureAuthCredentialForm. Semantic-ready control
доходит до step2. Synthetic HTTP component не объявляется real PostgreSQL/PATH.

## Источники и решение

Прочитаны AGENTS.md, README/CONTRIBUTING, EVC workflow/matrix/template, действующий
assessment-first-case/1.1 и path-ac18-final-plan с учётом выпущенного2.0.74;
`path-auth-fix.md`, UX-02 auth-часть, `web/js/{main,wiring}.js`, auth markup,
auth-r03/frontend auth regressions, PATH29, receipt persistence и runner identity.
Архитектурные context/Registry/Change01/manifest переиспользуются неизменёнными:
методология/предметные артефакты не затронуты, M1 CURRENT не назначается.
Цепочка: существующая UX-02 проверка ссылки → hidden/disabled pending form →
штатная password registration/reset → regressions. Новых норм оценки/порогов нет.
Все стоп-условия workflow — нет в согласованных локальных границах;
release/LLM остаются внешними решениями, не задачей этого исправления.

## План и проверки

1. Сохранить неизменённое отрицательное evidence и deterministic before-regression.
2. Узкая UI блокировка/ready state и generation guard; semantic-ready helper;
   активная вкладка + allowlisted failure context без password/token/cookies.
3. Targeted browser (pending registration/reset, отказ, safe failure page),
   весь frontend, lint/build/dist idempotency, backend/unit и HTTP по auth-строке
   матрицы. Integration не требуется: server/SQL/БД поведение не меняется.
4. Содержательное review, docs/STATE, локальный рабочий commit и доступный пакет.
   CI NOT_RUN: push/PR не разрешены. Последующий AC18 только на выпущенном SHA
   после отдельного решения; тесты исправления не закрывают AC18.

## Риски и откат

Сохранить existing operation-generation guards, ошибки/повтор проверки ссылки,
password policy и валидируемую сервером identity. Секреты не сохранять в context;
password/token inputs маскировать на failure PNG. Схемы/миграции нет.
Откат — revert только нового локального commit, без изменения данных/main/test.

Статус: активная локальная реализация. Итог проверок и точный SHA будут в отчёте.
