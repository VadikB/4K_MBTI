# P4K-W02-FIX-01 — интерфейс W02

Основание исполнения: прямое сообщение Дмитрия 15.11.2026 «запусти задание»
с файлом FIX-01 rev1.0. Вложение задаёт требования; полномочие происходит от
прямого запуска владельцем именно этой задачи. Дополнительный путь HTML получен
от владельца в том же чате. Исполнитель — Codex на машине Дмитрия.
Base: `e8773ca80b9e3089a0faec16e9722680d126d8bb`, fresh origin/main, версия 2.1.9.
Отдельные worktree `p4k-w02-fix-01` и ветка `codex/p4k-w02-fix-01`.
Чужие worktree, untracked RELEASE_STATUS W02-02 и процессы сохранены.

## Результат и границы

AC01–05: раннее ожидание, форма неточности, competencies/process, карточки готовности
и ошибок W02; шесть desktop и два mobile сравнения. UI существующих PM-02/PM-04,
LU контекста/пути участника. Контекст не Evidence; исходные данные и роль неизменны.
API issues остаётся `{message}`; вид кодируется префиксом `Поле: …\n`.
Схема/БД/backend/вопросы corporate@1.0/профили/таймеры/подготовка/допуск не меняются.
FIX-02, полный PATH, ответы оценки, Report/GC, Prod и предметная публикация вне задачи.

## Прочитанные источники

На base прочитаны AGENTS, README, CONTRIBUTING, agent-workflow, verification-matrix,
artifact-recipe, task-template/review-checklist, decision-register; architecture
1.0/context/registry, Change01 README/адресные страницы, task SourceSet manifest;
M1 v1.4 и M4.Context v1.0 (адресные разделы, DOCX), TASK/STATE W02-01/ADD01/W02-02;
onboarding/router/readiness/flow/CSS, API report_issue и его DOM/test consumers.
Product Architecture+Change01 WORKING; M1 FROZEN/CURRENT=NO, M4 FROZEN.
Глоссарий W011–16 — применимое изложение задачи; LU=Local Unit, Component=компонент
навыка. Новые предметные нормы не вводятся. Decision ADR-003: immutable назначение;
SYN-CONTOUR-OWNERSHIP: только собственные synthetic ресурсы; исторические полномочия
других задач не перенесены. PILOT-120 не источник UI-чисел: время из сервера.
Текстовый REFERENCE rev1.0 в gzip, HTML v5 прочитан без встроенных fonts/base64.
Его SHA256 `2ae50fbe1ef73b4eb9fa6c808fec16d31475fb5cf79bb3d69ff275d41447170c` совпал.
Исходные FIX-01/HTML приложены побайтово в gzip. TASK.RULES v1.0 отдельным файлом
не найден адресным поиском repo/архитектурного каталога; явные требования FIX-01
и действующий EVC процесс применены, отсутствующие нормы не придуманы.

Восемь стоп-условий workflow: нет — смысл/API/PM/владение/схема/миграции/предметные
значения/формат/права/среда/откат/область остаются прежними. ART debt не меняется.
Откат: revert собственного PR без удаления данных.

## План и полномочия

1. Разведка/base/эталон — завершено.
2. UI и регрессии — завершено.
3. Адресный browser и визуальная сверка, frontend/lint/build/diff-check — завершено.
4. PATCH2.1.10 подготовлен; commit/push/Ready PR и CI точного head — активно.

`branch_push=true`, `pr=true`, `version_bump=true` (PATCH), `merge=false`,
`deploy=false`, `artifact_publish=false`. Эти действия — часть прямо запущенной
задачи с указанной границей Ready PR. Человеческий review/merge/TEST отдельно.
Допуск действует до завершения или прямого стопа владельца. LLM=0, письма=0.
Публичный origin VadikB/4K_MBTI; настроенная Git-аутентификация без чтения секретов.
Автоматический отказ browser login к эталону зафиксирован; после получения HTML
вход не нужен. Позднее владелец разрешил вход, но он не выполнялся.

Проверки по JS-behavior + HTML/CSS строкам матрицы; backend не изменён, контракт
сохранения переиспользован, права/БД проверяются существующим CI. Browser — production
frontend с controlled API, 1 worker, retries=0, <=600s/no meaningful progress90s;
штатный Playwright и scripts.owned_process.run_bounded из SYN-LIMITS-FIX-01.
Не сокращать mandatory frontend/pytest/full-verification точного PR head.
Риски: UI/fixtures; внешний API и данные совместимы. Human visual TEST PENDING.

Публикация отдельно подтверждена владельцем 15.11.2026: «согласен, поехали»
в ответ на точный запрос public GitHub VadikB/4K_MBTI, ветка FIX-01/Ready PR,
перечислены передаваемые код/документы/синтетические evidence. Merge/deploy=false.

Ready PR: https://github.com/VadikB/4K_MBTI/pull/224. Обязательный CI запущен;
финальный SHA/result фиксируется локальным RELEASE_STATUS.json после завершения.

## ADD01 — 15.11.2026

Владелец передал ADD01 сообщением «вот задание на доделывание» в том же чате.
Продолжается текущая задача/ветка/PR224 в ранее разрешённых пределах push и CI;
merge/deploy/TEST/Prod/FIX02 не разрешены. Вложение — требования, полномочие —
прямой запрос пользователя и ранее подтверждённое сопровождение текущего PR.
ADD01 заменяет требование видимого reason и достаточность старого visual PASS.
План: проверить происхождение PNG/bytes HTML; исправить ранний waiting, section/live
и подтверждённую scoped геометрию; прямой чистый reference; 8 продуктовых кадров
(preparing/failed-locked/ready + early, desktop/mobile), адресные browser, frontend,
lint/build/diff-check; обновить тот же PR и mandatory CI точного head.
HTML SHA прежний, применимые неизменённые источники из TASK переиспользованы;
AGENTS/workflow/matrix/decision-register и TASK/STATE/CHECKS перечитаны адресно.
Main изменился: f505340 (PATH GUARD #225), версия2.1.10. Интегрирован merge8935b31
без сброса ветки; source-конфликт index — сохранён auth waiting header, generated
dist пересобран. PATH guard изменения сохранены. Нужен штатный PATCH2.1.11.
Архитектурные инварианты/API/данные прежние. Rollback — revert своего PR.
Reference противоречит заявленному происхождению; это блокирует visual PASS,
не независимые разрешённые UI-правки. Локально1worker/retries0/600s/no-progress90s,
owned registry/status-stop до запуска, cleanup после каждого исхода; DB/LLM/mail0.
