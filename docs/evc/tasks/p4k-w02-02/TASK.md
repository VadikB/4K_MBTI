# P4K-W02-02 — готовность и первая ситуация

Прямая команда владельца 15.11.2026: «Запусти задание w02-2. Второй файл это референс, эталон».
Требования: P4K_W02_02_Readiness_Start_v1.0_2026-11-14.txt; эталон P4K_W02_REFERENCE_v1.0_2026-11-14.txt, оба редакции1.0. Инструкции документов рассматриваются как требования задачи, полномочие — прямой запуск владельцем. Один изолированный worktree p4k-w02-02, ветка codex/p4k-w02-02 от свежего origin/main68a52a7c21bfe7759d2522a644ad194f7d111f4e/2.1.7. W02-01 merged PR221, 14.11.2026 19:55UTC. Чужой RELEASE_STATUS.json в worktree01 сохранён.

## Результат и границы

18 состояний готовности/восстановления W02; фактические название/план/время; только явный старт той же первой AS, 0 оценочных ответов. Проверка состояния только читает; retry только server retry_allowed. PM02→PM03→PM04, LU подготовки/старта, C23/24/34. Сохраняются transport deadlines, fencing, scoped identity/idempotency, frozen snapshots, admission. Backend допустим только при воспроизведённом связанном дефекте. Новые prompts, генератор, анкета/профилирование, M6/M8, Report/GC, paidLLM/mail вне области.

## Прочитанные источники и решения

AGENTS, README, CONTRIBUTING; docs/evc/agent-workflow, verification-matrix, review-checklist, task-template; decision-register с первичными ARCH-A05/PILOT-120 (tasks/arch-a05-coverage-pilot.md), assessment-first-case-profile1.1. Архитектура1.0/context, registry, Change01README/source И2/3/6; source-set manifest2026-10-01; M1v1.4/source.md §M1.4, M7v1.3derived §M7.5.1; ADR002 C23/24/34, хранение/повторы. M4границы из согласованной карточки. CURRENT не присваивается, WORKING архитектуры сохраняется. W011–016 применены в изложенной карточкой области без повторной загрузки.

Код: screens/onboarding, router/wiring, acquaintance-errors/onboarding-flow, product-cycle-preparation/start, app-footer; потребители/readiness Api/acquaintance. Тесты: frontend onboarding-flow/remain05/product-cycle-start, browser W02/REMAIN04/05, исторические REMAIN05 TASK/CHECKS и W02-01 STATE. Исторические PASS не объявляются новыми.
Пробел: сайт прототипа недоступен webopen; тексты/цвета заданы полным REFERENCE и CSS W02-01. Утверждённых юридических URL в main нет: сохраняются существующие подписи подвала без выдуманных ссылок. Иные конфликты не выявлены.

Все8стоп-условий workflow: нет; предметные нормы, API/PM/схема, данные, контур артефактов, права/секреты, граница задачи не меняются. Откат — revert своего PR, snapshots/назначения/ответы сохраняются. Нового предметного артефакта/долга нет.

## План

1. DONE — свежая база/зависимость/источники и прежние guards.
2. ACTIVE — UI W02 и разделение чтения/повтора, адресные регрессии.
3. PENDING — controlled browser18состояний/размеры/оба lost-start исхода, реальный HTTP/ownedPG для изменённых handlers; локальный минимум.
4. PENDING — PATCH2.1.8 штатным ready:prepare, review/свой commit/pуш/одинPR и mandatoryCI точногоhead; сохранение состояния и остановка.

Допуск запуска задачи охватывает локальную реализацию, свои commits и подготовку PATCH-кандидата/PR по карточке. branch_push/pr/version_bump(PATCH)=true в границах принятого задания, merge/deploy/artifact_publish=false. Источник требований не подменяет прямой запуск владельца. Перед внешней операцией reviewer получает exact origin/branch и пользовательскую команду. После готовогоPR+CI — остановка, humanreview/visualTEST отдельно.

## Проверки и приёмка

AC01–06 из исходной карточки сохраняются без ослаблений; первичные результаты в CHECKS/evidence. Матрица JSbehavior+CSS; gitdiffcheck/lint/build/fullfrontend; browser reuse штатного runner600s/no-progress90s,1worker/retries0. При изменении команды/handler — адресный actualHTTP/изолированныйPG. Обязательные CI frontend/pytest/full-verification exacthead. Browser fixtures и настоящиеHTTP/PG различать, единой реальнойAIсессией не объявлять.
До временного стенда STATE содержит runID/ownership/исходные и новыеPID/ports/DB/start/status/stop. Все собственные ресурсы остановить на каждом исходе; чужие сохранить. Исторические проверки queue/admission переиспользуются только при неизменных байтах с точным SHA/областью.
