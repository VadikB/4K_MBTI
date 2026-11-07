# AC18-FIX-02 / P2-AC04 — readback после потерянного ответа подготовки

Статус: локальный кандидат отдельного PR. Основание — `START_CODEX.txt`, `TASK.txt`
и `SOURCES.md` пакета `P4K_AC18_FIX_02_Preparation_Start_2026-11-07.zip` (редакция 1.0,
07.11.2026). Содержимое пакета задаёт критерии, но не разрешает выпуск или LLM-вызов.

## Результат и границы

После потери ответа `POST /users/assessment/cycles/prepare` перезагрузка страницы
сначала читает сохранённый `operation_id` через owned `GET`. Она не отправляет
повторную команду подготовки. Повторный POST остаётся только за явным действием
`retry` после подтверждённого failed; серверную политику retry эта задача не меняет.

Base: `origin/main@157d77d11a0eb8e504a5f5c822f0151f3e288fe6` (2.0.76).
Ветка: `codex/ac18-fix02-coverage-close`; worktree: `/tmp/4k-ac18-fix02-coverage`.
Ранее приняты и слиты: #182 (продукт), #183 (визуальные свидетельства), #184
(план provider verification). Их результат не переносится в этот diff.

## Источники и решение

Прочитаны `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
`verification-matrix.md`, `artifact-recipe.md`, `task-template.md`,
`review-checklist.md`, архитектурные `context.md` и `registry.md`,
`docs/architecture/product-4k/1.0/updates/2026-10-01/README.md`,
`docs/methodology/source-sets/2026-10-01/manifest.json`,
`docs/adr/002-cycle-as-dialogue-contracts.md`,
`docs/architecture/pilot-plan-start-admission-contract.md`, а также адресные
`web/js/screens/onboarding.js`, адаптер подготовки и browser/frontend-тесты.
M1 v1.4 — FROZEN/CURRENT=NO, не включается в runtime; Change 01 и его manifest
не изменяются. Новых предметных правил и артефактов нет.

Прослеживаемость: P2-AC04 (`TASK.txt`: неопределённый исход команды — сначала
readback, reload без новой подготовки) → owned-operation contract →
`web/js/screens/onboarding.js` → `tests/browser/auth-r03.spec.mjs`.
PM-03 готовит AS, PM-04 исполняет; изменение относится только к UI orchestration,
не к предметному admission или содержанию AS. Владельцем operation остаётся сервер.

Пробел исходного PR #182: таблица задачи называла P2-AC04 закрытой, но клиент при
сохранённом `status=unknown` после reload повторял POST с тем же idempotency key.
Серверная идемпотентность не равнозначна read-only восстановлению. Применимая норма
не противоречит архитектуре; новый контракт и решение методолога не нужны.

Стоп-условия рабочего цикла: изменение смысла/PM/API/БД/артефактов/прав/отката — нет;
внешние изменения и выпуск — отдельно, пока не разрешены. Неопределённая общая
политика retry для terminal failed не решается этой правкой.

## Изменённые файлы

- `web/js/screens/onboarding.js`: unknown operation проходит owned GET, как другие
  сохранённые операции.
- `tests/browser/auth-r03.spec.mjs`: регрессия lost POST → reload → GET 503 →
  ручной GET → READY, с проверкой числа POST и точного `operation_id`.
- `web/dist/`: пересобранный frontend, обязательный companion к `web/js`.

## Проверки

- До исправления адресный browser test: **FAIL**, два POST после reload (ожидался один).
- `npm run build:web`: **PASS**.
- `npm run lint:js`: **PASS**.
- `node --test tests/frontend/*.test.mjs`: **PASS**, 150/150.
- `playwright test tests/browser/auth-r03.spec.mjs -g 'AC18-FIX-02' --workers=1`:
  **PASS**, 3/3, синтетические HTTP fixtures, без реального LLM.
- `git diff --check`: **PASS**.
- Backend/DB integration: **NOT_RUN** в этом PR, сервер, схема и admission не менялись;
  результаты #182 не выдаются за проверку этого SHA.
- Полный CI: **NOT_RUN** до PR; обязательный перед merge.
- Реальный provider, физические устройства и test-сессия: **NOT_RUN**, отдельное
  разрешение/приёмка, не часть этого исправления.

## Риски, совместимость и откат

Публичный API, конфигурация, схема, данные и опубликованные snapshots не меняются.
Дополнительный owned GET выполняется только для уже сохранённого `operation_id`.
Секреты и реальные пользовательские данные не используются. Откат — revert этого
клиентского изменения, browser-теста и `web/dist`; серверные операции не удалять.

## Передача и выпуск

`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false` на момент локальной подготовки.
Владелец ранее разрешил merge/deploy #183–#184, но не этого нового PR. Для
`Ready for review` нужен согласованный следующий patch-кандидат и
`npm run ready:prepare -- --candidate <версия>`, затем полный обязательный CI.
Следующий шаг: зафиксировать этот независимый результат и подготовить draft PR;
отдельно получить решение о версии, review и merge/deploy. Не смешивать с
provider verification: по #184 платный вызов требует выбора SHA и лимита затрат.
