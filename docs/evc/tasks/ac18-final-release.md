# AC18-FINAL-REL-01 — единый финальный выпуск исправления readiness

## Результат и область

Передать один независимо принимаемый кандидат исправления AC18-AUTH-READY-01:
готовность password form только после server validation, semantic-ready ожидание
runner и safe failure capture активного актора. Не повторять уже выполненные
исправления AUTH/R10/другие выпуски. Один финальный test deploy, не серия промежуточных.

Основание07.11.2026: после PASS полного branch-run владелец ответил «делаем» на
следующий шаг единого финального выпуска. Конкретный номер ещё ожидает владельца:
штатный preflight на свежем main339aff9/2.0.74 предлагает PATCH2.0.75.
Человеческое code review точного PR head и разрешение merge/deploy не получены.

Включены существующий code c4a6a0c/handoff38bf8244, сохранение primary run evidence,
однократная release metadata/build после решения версии, PR и обязательный CI.
Исключены новый paid PATH/LLM, `.env`/постоянная БД/программа/подключения,
prompts/admission/repair, schema/migration, публикация предметных пакетов и pilot deploy.

## Источники, применимость и решения

Прочитаны актуальные AGENTS/README/CONTRIBUTING, EVC workflow/matrix/recipe,
template/review-checklist, architecture context1.0/Registry, Change01 README и
task manifest; release_version/prepare_release/prepare_ready_release,
package scripts, UI diff/fixtures/tests и действующие ac18-auth-readiness card/report.
Профильassessment-first-case/1.1 и path-ac18-final-plan переиспользованы неизменными
с учётом2.0.74 и отдельного разрешения branch-run, не как разрешение deploy.

Предметные этапы M0–M8, CURRENT и PM ответственности не меняются. Адрес изменения:
UI/auth readiness +техническая browser orchestration, без server auth/PM-03/04 правил.
Цепочка: принятый UX validation-before-password → UI pending/generation guards →
unit/browser HTTP regressions → actual HTTP/PostgreSQL/provider PATH на38bf8244.
Артефактный контур не расширяется, долг/legacy исключения не расширяются.
Старые ошибочные/неполные diagnostics сохраняются со своей областью; PREP-DIAG-01 UNKNOWN.

Все8 stop checks workflow: первые5 нет (сущности/API/schema/данные/артефакты не
меняются); sixth — deploy ещё требует разрешения, seventh нет (rollback к339aff9,
schema unchanged), eighth — bump заблокирован до решения номера, merge/deploy до
review/отдельного допуска. Независимая подготовка docs/evidence разрешена и продолжается.

## План, флаги и состояние

1. Fresh origin/main/branch/foreign work +canonical preflight — выполнено.
2. Сохранить actual branch-PASS primary evidence и провести code review агента;
   номер PATCH ожидает владельца — активный этап.
3. После номера: canonical ready preparation, idempotency/diff checks, применимые
   бесплатные проверки/сопоставление exact tested bytes, release commit, push/PR/CI.
4. Получить человеческое review точного head; merge/deploy только после отдельного
   разрешения и fresh main/mandatory CI. Один deploy, затем бесплатный readback.

`branch_push=true`, `pr=true` — по «делаем» в контексте единого выпуска;
`version_bump=false` до конкретного решения версии;
`merge=false`, `deploy=false`, `artifact_publish=false`, `paid_run=false`.
Исходная ветка codex/ac18-auth-readiness, clean38bf82448e63e55414ff55ac45fa126e9c4385f0;
main339aff9034ff005bc20d072876b3fbef4f834c5e /2.0.74. Чужой root branch и3 untracked
документа сохранены. PR/new CI/deploy пока NOT_RUN.

## Проверки, риски и откат

Матрица: JS behavior +auth HTTP +сборка/release +docs. Уже выполненные browser127/
frontend146/backend956/HTTP108 PASS и lint/build45 PASS применимы к runtime c4a6a0c;
actual real-provider PATH exact38bf PASS. В release не добавлять продуктовых изменений.
После metadata/build — сравнить старые/новые source bytes (version-only исключения
явно по release contract), повторить затронутые frontend/auth/release tests.
Обязательные CI frontend/pytest/full-verification точного head/base не заменяются
локальным успехом. Integration локально не требуется: server/SQL/DB поведение неизменно;
реальные PG binding/start уже проверены новым full PATH, CI всё равно выполнитintegration.

Данные/миграции/рабочая БД: изменений нет. Безопасность: fail-closed/session guards
сохранены, секреты не экспортированы. Deploy риск: пока не разрешён; штатный smoke/
rollback после разрешения. Откат — отдельный revert code/release либо штатный возврат
к339aff9 при неуспешном deploy, без восстановления БД. Не отключать проверки ради PASS.

Критерии: один согласованный номер; ровно заявленный diff; primary evidence доступны
из Git; проверки и head/base однозначны; human review отдельно; main/test/приёмка
не смешаны с branch-PASS. [Evidence](../evidence/ac18-branch38-path/README.md).
