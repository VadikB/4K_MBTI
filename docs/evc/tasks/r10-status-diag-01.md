# R10-STATUS-DIAG-01 — исчезновение итога подключения после загрузки анкеты

Статус: **REPRODUCED / FIX_NOT_AUTHORIZED**, отдельный от AUTH-DIAG-01 и timeout.
Область — UI обратная связь, не потеря подключения, admission или записей сервера.

## Первичные факты

На `bf637af8e1ee89c1a8d5621c4ce694a52bb0806e` свежий широкий browser run:
118 PASS/1 FAIL, retry0,3.5min. FAIL в существующем
`auth-r03.spec.mjs:445`, assertion493. Состояние до auth-fix
`dea8c44a183c2ac5f4b527e53cdeed0a39bcf454`: тот же тест3/3 FAIL на493.
Product source `organizations.js` и тест между этими commits побайтово одинаковы.
Значит, этот воспроизведённый дефект существовал до AUTH fix; он не является
доказанной причиной прежних R10/ADM timeout (другие тесты/шаги).

В trace обеих версий: PUT подключения и exact GET успешны; assertion490
подтверждает local status «Опубликованная версия программы подключена».
Затем test отпускает pending questionnaire503; assertion493 видит отсутствие
`[data-operation-status]`. PNG/readback UI сохраняет «Подключено: …1.1».
Fixtures синтетические: org3/program11/user18, fake HTTP, без реальной БД/публикации.

## Причина и основание

`organizations.js::setStatus` добавляет статус в текущий DOM по operationAnchor;
устойчивого outcome для этого подключения нет. `connectAdminOrganizationProgram`
после exact readback рисует подтверждённую программу, вызывает setStatus и запускает
background questionnaire с `render:false`. Но исходный `loadAdminOrganizations`
ещё ждёт свою Promise.all загрузки анкет и затем **безусловно** вызывает
`renderAdminOrganizations` (495). Этот render заменяет карточку, не восстанавливая
добавленный DOM-only статус; общий status остаётся скрыт после local rendering.
`render:false` одного фонового запроса не устраняет завершающий render исходной
загрузки. Причина нового status-loss подтверждена trace/кодом/повтором до fix;
почему отдельные старые прогоны проходили, отдельно не установлено.

Техническое ожидание уже закреплено существующей регрессией R10: успешное
подключение не ждёт анкету, и его подтверждённый итог сохраняется после её ответа.
Новая методологическая норма здесь не вводится. Источник → UI lifecycle →
setStatus/loadAdminOrganizations/render → старый browser тест493 →16 сохранённых
trace всего диагностического пакета, из них4 — этот status-loss.

## Предлагаемое отдельное исправление

Сохранять terminal outcome подключения по exact identity + organization + program
и восстанавливать его при render; новое действие/смена связки/account/logout
должны инвалидировать старый outcome. Не восстанавливать глобальный последний
status в чужую карточку. Не ослаблять точные PUT/GET refs, unknown/fail-closed,
operation_id и session generations. Добавить регрессии окончания initial load,
503/успешного ответа, re-render и смены scope, без sleep/ослабления assertions.
Затем применимые EVC проверки, один полный browser gate.

Нужен допуск владельца на этот узкий локальный UI fix. Сейчас продукт не менялся.
БД, LLM, methodology/admission/repair, bump, PR/push/merge/deploy не входят.
Нельзя закрывать этим fix исторические timeout, auth114/1 или PREP-DIAG-01 UNKNOWN.
Evidence и команды — [диагностический отчёт](../reports/browser-timeout-diagnostic.md).
