# P4K-W02-01 — знакомство и действия участника

Основание: прямое поручение Дмитрия 14.11.2026 «задание на исполнение. Запускай»
с двумя приложенными файлами редакции 1.0 (побайтовые копии в gzip рядом, SHA-256 в evidence/input-sha256.json). Файлы задают требования;
полномочие исполнения происходит от сообщения владельца. Исполнитель — Codex.

Результат: путь знакомства W02, единая форма трёх ответов до подтверждения,
сообщение о неточности на сведениях и сводке, read-only история. Один PR.
Архитектурный адрес: UI пути участника → PM-02 / LU контекста; контракты consent,
answers и issues прежние. Контекст не Evidence; источник вопросов — briefing,
`participant-context-corporate@1.0`, stable keys и answer_1–3 не меняются.
Не входят: подготовка/старт следующей карточки, смена роли, организационная анкета,
профилирование, API/БД/миграции, опубликованные артефакты и snapshots.

База: fresh origin/main `07166475b478c843243102c748d51f8564b7cec0`, 2.1.5.
Worktree `p4k-w02-01`, ветка `codex/p4k-w02-01`. Исходный checkout
`codex/remain-02` и его untracked docs сохранены. PR #220 другой задачи не включён.

Прочитаны: AGENTS, README, CONTRIBUTING; EVC workflow, verification-matrix,
review-checklist, artifact-recipe, task-template, decision-register; architecture
1.0/context, registry, Change01 README, SourceSet manifest; M1 v1.4 §M1.4,
M4.Context v1.0 §§M4.2–4 (оригинал DOCX); UX-CTX01 task, соответствующие
Api/acquaintance.py, questionnaire_sources.py, onboarding UI и tests.
Применимость: Product Architecture v1.0 + Change01 WORKING, M1 v1.4 FROZEN /
CURRENT=NO, M4 Context v1.0 FROZEN. Глоссарий W011–16 применяется в достаточном
изложении входа; повторная загрузка не нужна. PILOT-120/ARCH-A05 проверены по
первичной карточке arch-a05-coverage-pilot.md; числовые демонстрации не переносятся.
ADR-003 просмотрен: назначенная immutable роль сохраняется. Исторические полномочия
CODEX-WORKFLOW-02/PATH/F02 к этой задаче не относятся.

Стоп-условия (все нет): новый предметный смысл, публичный контракт, миграция,
конфликт источников, новый артефактный контур, права/чувствительные данные,
неопределённый откат, выход за scope. Изменяются UI и адресные fixtures.
Принятые тексты W02 — UI-пояснения, не новые нормы оценки. Старые briefing
с произвольными вопросами сохраняют исходные подписи. Динамические сведения,
роль и серверный текст/версия согласия сохраняют свои источники.

Флаги этапа по прямому запуску приложенного задания владельцем:
branch_push=true, pr=true, version_bump=true (PATCH от актуального main);
merge=false, deploy=false, artifact_publish=false. Разрешены собственные commits,
push ветки, один Ready PR, связанные fixes, наблюдение обязательного CI.
Граница окончания: готовый PR с CI точного head, затем остановка. Human review
отдельно; TEST не разворачивается этой задачей. Номер вычисляется штатно перед
`npm run ready:prepare -- --candidate X.Y.Z`.

План: 1) разведка (завершена); 2) UI/общие формы (активен); 3) адресные browser
и frontend, проверка layout 1440×1024/390×844/320; 4) PATCH + локальный минимум;
5) commit/push/PR/обязательный CI, evidence и передача.
AC01–05 соответствуют исходной карточке, результаты — CHECKS.md.
Проверки: diff-check/lint/build/frontend; browser с реальным frontend и controlled
contract responses, один worker/retries=0, общий deadline 600s/no-progress90s.
Новые регрессии только для общей формы/ошибок/scope; существующие late-readback
и scoped-draft переиспользуются. Backend не изменяется; права issues подтверждены
существующими HTTP/integration регрессиями в mandatory CI. LLM=0, письма=0.

Риски: только UI/совместимость fixtures; CSS ограничен onboarding-panel. Общие
стили проверяются computed styles. Откат: revert собственного PR, данные и snapshots
сохраняются. Сайт прототипа недоступен (web open и DNS curl); локальный HTML не
найден. Используется достаточный текстовый эталон, пиксельная сверка HTML ограничена.
