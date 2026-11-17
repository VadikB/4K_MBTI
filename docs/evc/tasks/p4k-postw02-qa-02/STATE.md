# QA-02 — приглашения

## Актуальный этап: разрешено слияние в main

17.11.2026, прямое сообщение владельца в этом чате: «сливай PR на main».
По CONTRIBUTING/CONTRIBUTING-MERGE-AUTH-01 разрешены публичный экспорт этого
конкретного QA02 состава, branch_push=true, pr=true, version_bump=true (следующий
PATCH2.1.29 от актуального main2.1.28), Ready=true, merge=true после обязательного CI
и review; deploy=test штатным workflow. artifact_publish=false, pilot/production=false,
реальные письма/LLM0. Повторное разрешение шагов выпуска не требуется.
Проверенный исходный commit39eb435; fetch подтвердилmain71a9c535cee4aea094d2b49c2b73f39e22f99bbe.
Аккаунт gh имеет WRITE; правила protected main сохраняются, bypass не используется.
Следующий шаг: штатный ready:prepare, commit/push, один PR, required CI точного head,
squash merge и проверка штатного deploy. Ниже сохранён предыдущий локальный этап.

Прямой запрос владельца 17.11.2026: «запусти задание» с QA02 и матрицей редакции1.1.
Вложения — требования к результату, не самостоятельное полномочие внешней публикации.
Base свежего origin/main71a9c53 (2.1.28), ветка codex/p4k-postw02-qa-02,
отдельный worktree p4k-qa02-invitations. Чужие изменения REPORT-FIX-02 не затронуты.
QA-05 уже выполнен: outputs/p4k-qa05-diagnostics-20261117/RESULT.md — PARTIAL,
обе invitation-причины UNKNOWN, SSH Permission denied. Повтор TEST-ревизии исключён.

Этап: локальная реализация/controlled проверки/передача одного результата.
branch_push/pr=false до конкретной внешней передачи; merge/deploy/version_bump/
artifact_publish=false. Реальные mail/LLM0; тестовая owned БД,1worker,0retries,
browser run≤300s, шаг≤20s. Номер версии не назначается.

Прочитаны AGENTS, README, CONTRIBUTING, workflow/matrix/recipe/review/template,
decision-register, architecture context/Registry, Change01 WORKING README/источник,
SourceSet2026-10-01, M1v1.4 README/определения, M7v1.3 §§5–6,
сохранённая glossary-sections.txt (вторичная выдержка WORKING30.09),
REMAIN03 и QA01 STATE, QA05 report, production invitation/API/transport/UI и тесты.
Точные предоставленные постановки сохранены рядом; REFERENCE_V10 source e44fa78,
используется как композиционный эталон, не runtime/правила допуска.
Decision SYN-CONTOUR-OWNERSHIP и CONTRIBUTING-MERGE-AUTH-01 рассмотрены;
исторические полномочия других задач не перенесены.

Архитектурная область: admin UI→invitation API/ACL→mail adapter; readiness —
потребитель PM02. Методология, программы, snapshots, новые LU и блокеры не меняются.
Восемь стоп-условий workflow: нет — совместимое добавление безопасных полей
утверждено постановкой, без миграции, новых прав, формата предметных артефактов,
изменения оценки/источников, деплоя; откат revert ограниченного diff.
План: разведка завершена; активен общий контракт и сохранение; далее UI,
регрессии/HTTP+SQL/browser1440/390/320, обязательные локальные gates, отчёт/commit.


## Локальная передача завершена

Все изменения и локальные проверки завершены, подробности REPORT.md/CONTRACT.md.
429 frontend,1247 backend,216 HTTP,61 controlled,28 targeted SQL/HTTP,15 browser PASS.
Полный integration:459PASS/2SKIP/1FAIL; FAIL неполной fixture исправлен и повторён
адресно, не выдан за единый зелёный полный run. Повторный fetch подтвердил71a9c53.
Активных вычислений/серверов нет: PostgreSQL55439 остановлен, pg_ctl status3,
pg_isready2; browser-cleanup listening=false. Реальные mail/LLM0, TEST не менялся.

Следующий шаг — решение о внешней публикации конкретного локального состава:
код, тесты, матрица/отчёт и синтетические PNG в публичный VadikB/4K_MBTI,
одна ветка и draft PR. До этого branch_push/pr=false, CI NOT_RUN.
Ни текущая постановка во вложении, ни допуски QA01/REPORT не перенесены как
самостоятельное разрешение публичного экспорта. Автоматического отказа approval
в QA02 не было: операция публикации не запрашивалась. Merge/deploy/version bump
и Ready этим этапом не выполняются. Код/проверки не требуют нового решения;
остаток QA05 — прежние серверные причины UNKNOWN и адресный операторский сбор.
Финальный локальный SHA и пакет: outputs/p4k-postw02-qa-02-20261117/DELIVERY.json
родительского workspace. Собственный откат — revert всего QA02 commit.


Штатный preflight `npm run ready:prepare -- --candidate 2.1.29` PASS: изменены только
pyproject/uv.lock/config/index cache keys и штатный dist. Публикация — Ready PR,
чтобы запустить обязательный полный CI. Прямой допуск владельца на merge является
принятием представленого результата; самостоятельный agent self-review не выдаётся
за отдельное человеческое GitHub review. Protected ruleset и серверный merge gate
применяются без bypass. Прежняя ветка39eb435 сохранена в локальном пакете.
