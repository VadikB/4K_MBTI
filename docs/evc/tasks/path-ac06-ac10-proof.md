# PATH AC06/07/09/10 — реальные HTTP/PostgreSQL, подготовка AC18

## Результат и границы

Прямое задание владельца 06.11.2026: закончить бесплатные проверки четырёх AC,
исправить подтверждённые ошибки в этом же задании и подготовить, **не запускать**, AC18.
Только синтетические данные и новая owned PostgreSQL; никакой рабочей БД, почты,
LLM, публикации, bump, push/PR/merge/deploy. PREP-DIAG-01 отдельно, причина UNKNOWN.
AUTH/R10 2.0.69 закрыт, не переоткрывается.

База после свежего fetch: main/origin/main `3f42bba992e1a556e1961ca4abdaa0954a367153`,
2.0.69, tree `23f065e1c8827a141a48c57fb97b6b4251439e6c`.
Ветка `codex/path-ac06-ac10-proof`, отдельный worktree. Три прежних untracked файла
корня и остальные worktrees сохранены. Это не baseline.

## Источники и применимость

Прочитаны AGENTS.md, README.md, CONTRIBUTING.md, workflow/matrix/artifact-recipe,
task-template/review-checklist; архитектурные context/registry; M1 v1.4 README
(FROZEN/CURRENT=NO), Change01 README/source И-1/И-6/И-7 и manifest 2026-10-01.
Повторно использован неизменённый контекст предыдущего чтения CONTRIBUTING/matrix.
Прочитаны path-final-audit-2068.md, path-start-1.3.txt, assessment-first-case-profile.md
(assessment-first-case/1.1), tests/README.md и tests/browser/README.md;
ADR-003 и pilot-plan-start-admission-contract v1.
Старый audit — карта пробелов доказательств, не доказательство текущего дефекта;
старые ожидания AUTH/R10 заменены закрытием PR174.

Правило Change01 И-6 (права/повторы) → ADR-003/program+assignment/questionnaire
контракты → Api.routes/assessment_programs/assessment_assignment_sources/
questionnaire_sources → новые реальные HTTP+PG проверки. Успешные resolver,
Connection и authorization не подменяются. Синтетические опубликованные test
источники не являются новым методологическим или human QA допуском.

Применимые первичные результаты: questionnaire_sources_db (SQL stale/foreign),
arch30_membership_db (конкурентный SQL), path29_participant_owned_stand (реальные
HTTP/sessions/SQL); adm27_assignment_http использует fake Connection/resolver и
сам по себе AC09/10 не закрывает. Точные новые результаты — в итоговом отчёте.

## Стоп-условия

1. Новый предметный смысл без решения: нет; проверяется существующее поведение.
2. Новый публичный контракт/схема/PM без допуска: нет; при обнаружении остановить
   только зависимое изменение, технические bugfix совместимы.
3. Миграция сохранённых данных: нет; только marker-owned disposable test DB.
4. Нет источника предметного значения: нет; новые нормы не вводятся.
5. Новый контур артефакта: нет; существующие runner/profile/seed.
6. Новая передача чувствительных данных/прав: нет; синтетика, реальная проверка guard.
7. Неопределённый откат: нет; локальный diff, без миграции/выпуска.
8. Выход за разрешённый scope: нет для локальных free checks; выпуск и AC18
   ожидают отдельного прямого разрешения.

## План

- Завершено: fresh Git, отдельный worktree, чтение источников, карта пробелов.
- **Активно:** настоящие HTTP/PG baseline и регрессии AC06/07/09/10; сохранять
  ожидание → actual → причина → fix → rerun до cleanup.
- Затем: применимый локальный минимум матрицы, проверка отсутствия внешних вызовов.
- Затем: AC18 exact-source/command/limits/viewports plan; итоговый отчёт и пакет.

## Проверки и приёмка

- AC06 actual ordinary admin PUT program + foreign writes: отказы и SQL no-write.
- AC07 stale/foreign confirm: отказы, current revision: штатное подтверждение.
- AC09 повтор/конкуренция/потеря ответа/readback: одна assignment/binding,
  никаких Cycle; SQL rollback при позднем отказе.
- AC10 invalid program/role/scope/questionnaire: exact errors, no partial writes.
- Полный применимый Python non-LLM, targeted HTTP+PG; frontend/browser если затронуты.
- Cleanup только owned DB/container после сохранения первичного evidence.
- AC18 NOT_RUN: один real-provider PATH после отдельного разрешения и выпуска
  окончательного кода; платная генерация на ширинах не повторяется.

## Выпуск и откат

branch_push=false; pr=false; merge=false; deploy=false; version_bump=false;
artifact_publish=false; paid_llm=false. Новый CI не запускается локальной задачей.
Откат — revert только своих локальных commits/diff; постоянные данные не затронуты.
Риски: техническая синтетика не подтверждает реальное качество AS; финальный PATH
и разные ширины ещё не выполнены на окончательном SHA.
