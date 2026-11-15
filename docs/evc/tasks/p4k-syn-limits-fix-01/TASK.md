# P4K-SYN-LIMITS-FIX-01 rev1.0

Основание: прямое поручение пользователя выполнить файл от 15.11.2026.
Base: 68a52a7c21bfe7759d2522a644ad194f7d111f4e, свежий remote main совпал.
Ветка codex/p4k-syn-limits-fix-01; worktree /private/tmp/p4k-syn-limits-fix-01.
Основной грязный checkout bc63a8ee сохранён без изменений.

## Результат и границы
AC01–AC06: конечные шаги/ASK, общий срок и отсутствие прогресса, бюджет повторного
входа actual _strict_json_call/DeepSeekGateway, собственное дерево процессов,
запрет real в controlled профиле, сохранение ошибки export/readback.
Не входят: нормы участника/Cycle, admission, расчёт/Report, миграции, полный PATH,
платные вызовы, mail, общие TEST/Prod, глобальные бюджеты/перестройка очереди.

## Источники и решения
Прочитаны AGENTS, README, CONTRIBUTING, agent-workflow, verification-matrix,
artifact-recipe, task-template, review-checklist; context/registry v1.0,
Change01 WORKING README/И-1–7; manifest SourceSet 01.10.2026; M1 v1.4
M1.5–6/9–10 и M7 v1.3 время/QA (FROZEN/CURRENT=NO), ADR-002 C-34/45/46.
Decision-register 08.11 SYN-CONTOUR-OWNERSHIP/PATH-START-01-SCOPE и связанные
profile/handoff использованы только внутри текущего узкого допуска.
Полный исходный REPORT и diagnostics/probes.py/.mjs прочитаны; исходная карточка
Downloads/P4K_SYN_LIMITS_01_Check_2026-11-14.txt — история аудита, не новые лимиты задачи.
P4K.DEV.PRINCIPLES v1.0 — Downloads/P4K_UX_Fixes_2026-10-20/reference/
P4K_Product_Development_Principles.txt. Глоссарий30.09 и Task_Setting DOCX14.11
не найдены адресным поиском имён в repo/Downloads; нормы не реконструируются.
Технические пределы заданы прямым текущим поручением. LU=Local Unit.

Прослеживаемость: M1.5/C-34 → PM-03 strict JSON/gateway → fake transport регрессия;
M1.6/C-45/46 → PM-04 test driver/cleanup → controlled page/export регрессии;
M1.9/M7.5.3 → отдельный технический budget runner, время Cycle не меняется;
M7.9 → первичные evidence и пределы вывода AC01–AC06.
Предметные артефакты и ART debt не меняются. Восемь стоп-условий workflow: нет;
нет изменения смысла/API/PM/схемы, миграции, новых предметных значений/формата,
чувствительных данных/прав, неизвестного отката или выхода за scope.

## План
1. Завершено: разведка, свежий main, отдельный worktree, сохранение audit evidence.
2. Активно: минимальные исправления и адресные регрессии.
3. Далее: обязательный локальный набор, review, кандидат/PR и CI точного head.

## Выпуск и откат
branch_push=true, pr=true — поручено сдать один PR. merge=false, deploy=false,
artifact_publish=false. version_bump=true: PATCH 2.1.8 подтверждён владельцем в ответе на вопрос текущего чата; `npm run ready:prepare -- --candidate 2.1.8` PASS.
Откат: revert собственных коммитов; сохранённые diagnostic state не удалять.
Исходный аудит [REPORT](../../evidence/p4k-syn-limits-01-2026-11-15/REPORT.md)
скопирован побайтово и проверен audit-copy.json. Audit worktree detached сохранён;
отдельной ветки аудита нет, единственных нужных материалов в нём нет.

## Проверки
Backend минимум npm run test:backend; transport fake gateway contracts;
JS lint/build и node --test tests/frontend/*.test.mjs; затронутые fixtures/driver
исполняются с controlled adapters. Нет изменения БД — integration БД не требуется,
если сохранность проверяется только на файлах, это явно ограничивается.
Микропробы последовательно: внутренние короткие пределы, внешний <=30s,
внешний teardown <=30s. Полный кандидат — штатные пределы CI, без 30s wrapper.
