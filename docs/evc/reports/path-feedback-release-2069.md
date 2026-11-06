# PATH-FEEDBACK-R1 — кандидат 2.0.69 для PR/CI/review

## Результат

Подготовлен единый PATCH-кандидат: terminal feedback не исчезает после поздней
асинхронной очистки AUTH и перерисовки карточки подключения R10. Согласованные
локальные реализации сохранены без нового изменения поведения; источник
`c59b024ebfae98790e545eae16d043a2280b9384`. База main
`946a46cb71e5ca5cc99778f036807d6c193188dc` / 2.0.68, release-ветка
`codex/path-feedback-2069`. Точный финальный head/tree фиксируется Git и PR после
commit; версия не является заменой SHA. Это не сдача полного PATH или всех 18 AC.

## Изменённые файлы

Продуктовый diff к main: `web/js/session.js`, `screen-loaders.js`,
`screens/chat.js` — синхронная очистка старого auth feedback и сохранение нового
при lazy reset; default reset и generation guards сохранены.
`screens/admin/organizations.js` — scoped transient outcome по user/epoch/org/
selected+connected program, invalidation новых intent/selection/session и поздних
callback, восстановление без повторного фокуса. Exact PUT/GET и operation_id прежние.
Регрессии: `auth-recovery.spec.mjs` (4), `program-connection-feedback.spec.mjs` (10),
два затронутых frontend-набора; старый `auth-r03.spec.mjs` не изменён.

После c59b024 изменены только четыре release metadata, штатный `web/dist` и новые
release docs/evidence/STATE. Api/scripts/schema/assessment_definitions/tests и
остальные UI sources совпадают с локально проверенной реализацией. Диагностические
материалы перед fixes, отрицательные результаты и immutable manifests сохранены.

## Источники и решения

Владелец отдельно разрешил локальные AUTH/R10 fixes, затем подтвердил:
«Да, 2.0.69: PR/CI/review». Допуск включает bump, push, Ready PR, обязательный CI
и передачу на человеческое review; НЕ включает merge/deploy/программу/БД/LLM.
[Карточка и прочитанные источники](../tasks/path-feedback-release-2069.md).
Использованы неизменённые README/AGENTS/CONTRIBUTING, EVC workflow/matrix/recipe/
review, architecture context/Registry/Change01/manifest и M1 v1.4 FROZEN/CURRENT=NO.
Новая методологическая норма или CURRENT не присваивается.

Связь: existing PATH feedback assertions и controlled reproduction → UI lifecycle
AUTH/R10 → соответствующие sources → 4+10 browser regressions и прежние 115.
Подробные before/after и применимость: [AUTH](path-auth-fix.md),
[R10](r10-status-fix.md), [диагностика](browser-timeout-diagnostic.md).
Открытых предметных решений для этого узкого выпуска нет; все stop categories
проверены, расширения контура/API/данных/прав нет, откат определён.

## Проверки

Команды, первичные stdout/JSON, контрольные суммы и offline checker:
[новое release evidence](../evidence/path-feedback-release-2069/README.md).
На candidate 2.0.69: preflight + идемпотентный повтор PASS (4 metadata/45 assets),
lint PASS, frontend 145 PASS, release/CI 22 PASS, backend 920 PASS,
HTTP 108 PASS. Полный browser 115+4+10: exit0, **129 PASS**, 230.598s,
retries0/skipped0/flaky0. Diff/links/source equality/inventory проверены до commit.
CI старого main не подменяет обязательный CI нового head/base.

## Непроверенное и границы доказательств

Browser использует настоящий entry/dist с synthetic HTTP, не реальную авторизацию,
рабочую PostgreSQL или generation/tester/challenger. Backend/HTTP запущены с
закрытым localhost DB sentinel, без .env/credentials; real LLM 0.
Локальный DB integration неприменим к изменению UI/metadata; штатный CI всё равно
проверяет изолированную PostgreSQL и все browser lanes. До его завершения CI не PASS.
Новый real-provider/final-SHA/post-deploy PATH NOT_RUN и не разрешён.

Исторический PREP-DIAG-01 UNKNOWN отдельно; auth114/1 causality NOT_ESTABLISHED,
старые R10/ADM timeout UNKNOWN. Установленные AUTH cleanup и R10 status-loss
не объявляются их доказанными причинами. Негативные пакеты не заменены новым PASS.
Старые manifests 170/183/76/209 проверяются на immutable commits, а не на новом
dist/STATE; повторное пересчитывание ради bump запрещено и не выполнялось.

## Риски: конфиг / схема / деплой / безопасность / откат

Предметные config/prompts/admission/repair, опубликованные определения и M0–M8,
API/схема/постоянные данные/права не меняются. Outcome — память UI, без localStorage;
реальные доступ, связь и готовность по-прежнему определяет server. Главный риск —
асинхронный lifecycle UI; проверены поздний callback, новая identity/выбор/action,
failed readback и re-render. Новый test deploy здесь запрещён; последнее
подтверждённое test 946a46c / 2.0.68, свежего live server readback не было.
Откат — revert соответствующего UI/tests и согласованного metadata/build commit;
миграция или восстановление БД не нужны. Не удалять historical evidence.

## Следующий минимальный шаг

Агент: commit/push/Ready PR и обязательные frontend/pytest/full-verification точного
head/base, затем передача человеку. Владелец: human code review именно этого head;
принятие прежних PR не переносится. Merge/deploy требуют отдельного разрешения.
Baseline не назначен. Статусы после CI фиксируются в PR без status-only commit.

## Открытые вопросы

Человеческое review нового head пока NOT_DONE; merge/deploy не разрешены.
Задача текущего этапа заканчивается передачей проверенного кандидата на review,
а не его слиянием или скрытым расширением PATH.
