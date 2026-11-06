# R10-STATUS-DIAG-01-FIX — устойчивый scoped итог подключения

Основание: владелец подтвердил «Да, исправить локально» на узкое сохранение
feedback подключения при render с exact identity/organization/program,
регрессиями и EVC-проверками. База4f2e884eac9e00f6f169dddfe5fad6d7a910aaa9;
product base bf637af, ветка codex/path-final-audit. Main/test последний
подтверждённый946a46c/2.0.68. Все release flags false: без рабочей БД/LLM,
server/admission/repair, bump, push/PR/merge/deploy, публикации/активации.

## Разведка и решение

Прочитаны R10-STATUS-DIAG-01 и первичные current118/1/comparison3FAIL,
organizations.js (reset/scope/drafts, tracking/status, connect/readback, render),
wiring submit и frontend/browser потребители. Неизменённые README/CONTRIBUTING,
workflow/matrix/recipe/review, архитектурные context/Registry/Change01/manifest и
M1v1.4 FROZEN/CURRENT=NO переиспользованы из прошлых шагов этой сессии.
Новая предметная норма не нужна: исходный R10 assertion493 уже требует сохранения
успешного итога после завершения анкеты. PM/server/владение данными не меняются.
Источник → terminal UI outcome → organizations.js render → настоящие browser
regressions. Техническое состояние живёт только в памяти текущей UI-сессии,
не в localStorage, не новый артефакт и не допуск программы.

Решение: сохранить terminal outcome с identity epoch/user/org/program и снимком
подключённой программы, восстановить только в той же форме после drafts restore.
Новые действия/смена org/program/identity/logout инвалидируют outcome и поздний
feedback старой операции; exact server PUT/GET и operation_id не ослаблять.
Не восстанавливать глобальный последний status в другую карточку.
Все8 стоп-условий workflow — нет в согласованном узком scope. Откат: revert нового
локального commit; данных/миграции нет. Нового artifact debt нет.

## План и проверки

1. Сохранённые before FAIL на bf/dea переиспользовать, добавить browser-регрессии
   после успешного/503 questionnaire, lost PUT, re-render, program/org/account
   change и новой операции. Только HTTP fixtures/реальные entry/dist, без sleep
   или подмены методов/DOM/fetch продукта.
2. Исправить lifecycle feedback в существующем UI модуле. Адресные browser и
   весь frontend, lint/build/idempotency45, структурные guards как дополнение.
3. Один полный auth/admin browser gate. Existing negative exact readback,
   unknown/deadline/lost reply и auth regression должны сохраниться. Backend/HTTP
   из bf неизменённые, адресные HTTP перепроверить; integration неприменим без
   изменения БД/server. Любой новый сбой сохранить/разобрать, не объявлять PASS.
4. EVC report/STATE, локальный working commit и независимый пакет с primary
   evidence/code identity/diff/bundle. Старые manifests170/183/76 не обновлять;
   replay только immutable checkout. CI/review/release NOT_RUN.

Шаги1–4 завершены с локальной фиксацией и передачей пакета: before1 FAIL →
targeted10 PASS, frontend145/backend920/HTTP108/full browser129 PASS, lint/build45
и idempotency PASS. [Отчёт/команды/evidence](../reports/r10-status-fix.md).
Новый release/CI/human review не выполнялись; отдельный release gate остаётся закрыт.
PREP-DIAG-01 UNKNOWN, auth114/1 NOT_ESTABLISHED и прежние
R10/ADM timeout UNKNOWN сохраняются отдельно от подтверждённого status-loss.
