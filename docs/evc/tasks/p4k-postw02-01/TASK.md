# P4K-POSTW02-01 — кабинет участника

> **Текущий follow-up: шапка, имя и цвета доработаны по новому запросу владельца.**
> [Результат 1440/390 и fallback](HEADER_REVIEW.html), [сверка и проверки](POST_REVIEW.md).
> Предыдущие исправления A01–A18 сохранены; нижележащие записи — история этапа.
> PR для текущей ветки не найден; его update/CI NOT_RUN до получения ссылки. Новый PR,
> merge и deploy не выполняются. Identity: evidence/header-review-refine/identity.json.

> **Текущий результат: локальные исправления A01–A18 выполнены и проверены.**
> [Исправленный вариант](FIXED_COMPARISON.html), [итоги и ограничения](REFERENCE_FIXES.md).
> Ниже сохранён прежний отчёт/план; исходный FAIL относится к e1b07b3.
> Новый source/dist snapshot — evidence/corrected/identity.json. Публикация запрещена.

16.11.2026. Прямой запрос владельца: «нужно выполнить задание 01. референс в отдельном документе».
Требования: P4K_POSTW02_01_Cabinet.txt rev1.1 + REFERENCE_CURRENT.txt.
Во время работы владелец прямо выбрал «Новую 1.1 с эталоном v10»; исходная rev1.0
и REFERENCE_V9_AUDIT.txt остаются историей входа.
Вложения задают требования, не самостоятельные полномочия на внешнюю публикацию.
Base: `2afcc37912fb2219f0710a5836b7417ce01d8e8e`, fresh origin/main, 2.1.11.
Ветка `codex/p4k-postw02-01`, отдельный worktree `p4k-postw02-01`.

Результат: сохранённый полный план и предъявленная позиция одного Cycle/plan revision,
различимые server-owned состояния; композиция report-history v9, доступные прежние действия.
PM-04 LU-04.2/04.3/04.5/04.6 и UI-проекция, существующий PM-07 history consumer.
API аддитивен: planned_total/current_position_no/last_completed_position_no/plan_revision_id;
старые total_cases/completed_cases сохраняются. Новая схема и миграции не нужны.

## Источники и границы

Прочитаны AGENTS.md, README, CONTRIBUTING, evc agent-workflow/verification-matrix/
artifact-recipe/task-template/review-checklist/decision-register; архитектурные context,
Registry, Change01 README/source И1/2 и адресные C24/34/45/46/67 ADR002;
source-set manifest 2026-10-01, M7 v1.3 §§5.3–5.5/6.3, return-time-integration,
completion-contract и saved R1 v2 policy. Проверены первичные LK01 и REMAIN06 TASK,
W02 FIX STATE. Глоссарий WORKING 30.09: внешний extracted source из
P4K_REPORT_TASKS_2026-11-15/reference/sources, адресно вводная/термины Cycle/Session/LU.
Статусы источников не повышаются. M0 unavailable не блокирует данную проекцию.
Reference v10: Site appgprj_6ad211b93f948191a7bc6106570630ea, commit
e44fa78efb1ec8605b28cf9bc2c2272da2b9122a. Версия/SHA/succeeded publication сверены
через read-only Sites API. Прочитан REFERENCE_CURRENT.txt; сцены report-history-active/
preparing/ready/return/result сверены по этой спецификации, композиция v9 сохранена.
Точный source и авторизованный браузерный reference NOT_RUN: available Sites tools
дают metadata без чтения archive, local v10 checkout отсутствует. Google login не повторялся.
Shared tokens W02 уже содержат контрольные цвета; вынесение aliases сохраняет их значения.

Не входят: POSTW02-02, вопросы W02, корпоративная анкета, профилирование, радар,
расчёт результатов, PDF/сравнение/генерация, админский доступ, scheduler, snapshots.
Никаких real LLM/mail/данных пользователей, Prod, Docker или общего PATH.
Существующая история Cycle переиспользуется, один Cycle отображается один раз.

## План

1. Read-only projection full plan/current/last presented + подготовка/возврат.
2. Renderer/композиция и явная навигация в кабинет, без запуска подготовки при входе.
3. Адресные unit/HTTP/renderer и один bounded browser fixture (1440/390, overflow320),
   before/after с одинаковым viewport, lint/build/diff; CI сохраняется.
4. Review, локальный commit, конкретный reviewable результат и один PR при наличии допуска публикации.

Локальные изменения/проверки/собственные коммиты разрешены прямым запросом исполнения.
branch_push/pr: требуются заданием; прямое полномочие внешней публикации проверяется
отдельно после подготовки результата. merge=false, deploy=false, version_bump=false,
artifact_publish=false. Draft PR не меняет номер приложения и не выдаётся за Ready release.
Стоп-условия: смысл/нормы/границы PM/ACL/схема/данные не меняются; аддитивные поля
прямо требуются заданием, старые потребители сохраняются. Новых контуров/артефактов нет.
Откат: revert собственных code/build/test commits; доменные записи не меняются.

## Проверки

Адресные projection/HTTP с fake connection (только SELECT), fake clock/provider.
M=8 при каталоге9/materialized1 и3; N=3 при unknown completed; не N+1 между AS;
нет генерации/старта при открытии готовности/кабинета, явный Continue сохраняется.
Frontend tests, lint/build/diff. Общий локальный backend не запускается по более узкому
прямому заданию; обязательный CI репозитория не меняется. До merge обязательны все gates.
Browser run `postw02-cabinet-01`: worker1/retries0, whole180s/test60s/idle60s,
только localhost ephemeral static server, все API stubbed, LLM/mail/DB=0;
afterAll/finally закрывают сервер, runner group TERM/grace1/KILL при deadline.
Снимки только synthetic. Состояние/результаты — STATE.md и CHECKS.md.
