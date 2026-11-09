# EXEC-FIX-02 + EXEC-FIX-03 — состояние интеграции

- Сессия: `P4K-PUB-EXEC-02-03-ARCH`; ID `01a1c143-ba8b-7a61-b28e-b70e902169b5`.
- Worktree: `/Users/vadim_bogachev/Developer/4K/ARCH_WORKTREES/release-exec-fix-02-03`.
- Ветка: `codex/release-exec-fix-02-03`; один активный писатель.
- Base / актуальный `origin/main` при импорте: `46a5532336e41c5cdedf9684ba7bd5a9c5c202d1`.
- EXEC-FIX-02: base `023bf85ec796d212d29b33218d906a1ed2023941`, source/tested `ea5f8353447dcd3764fb9f97665ef536e95b6d84`, imported commit `4c608f957b85757b81fc3df2b9dd9c3aed92af20`.
- EXEC-FIX-03: base `46a5532336e41c5cdedf9684ba7bd5a9c5c202d1`, source/tested `b19171997118d490cff334ce44b8f664a5ee6b4e`, imported range `447b7731..fe2c9ede`.
- Integration/tested head до STATE-коммита: `fe2c9edef5d0dd5f1bdd0582541e9502b2cde4ff`; generated `web/dist` пересобран из объединённых source-файлов при разрешении конфликтов.
- EXEC-FIX-01 включён в `origin/main` commit `60234f2a1d8d8389567fbfb012f4b83eb3b4a21f` (#200); integration обновлена merge-коммитом `ee27ae117e6cdf34f2153c9879eae5083608dc82`.
- После создания Draft PR #202 база продвинулась до `3290421966214ffac4d6193975fd5723b7e19b21` (#201); интеграция повторно актуализирована. Конфликты затронули только generated `web/dist`, который очищен и пересобран из автоматически объединённых source-файлов; source-конфликтов не было.
- Текущий шаг: Draft PR на release head после записи финальных результатов.
- Release version: владелец одобрил PATCH `2.0.89 → 2.0.90`; `npm run ready:prepare -- --candidate 2.0.90` — PASS, product paths: 51.
- Следующий шаг: commit/push подготовленного release head, полный обязательный CI и human review до merge.
- Стоп-условия: предметных/схемных/миграционных новых решений не выявлено; merge заблокирован до актуального полного CI и human review.
- Полномочия: import/local checks/branch push/PR разрешены; paid LLM запрещены; version bump не назначен; merge/deploy только после действующего допуска и обязательных gates.
- Откат: revert импортированных commit-цепочек и интеграционных адресных исправлений; сохранённые Turns/receipts/history/snapshots не удалять.

## Прочитанные источники

`AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
`docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`, Product Architecture
1.0/Registry, Change 01 и SourceSet manifest, ADR-002, Change 01 traceability,
карточки EXEC-FIX-02/03 и оба HANDOFF/bundle manifest. Применены M1 v1.4
FROZEN/CURRENT=NO и выбранные M5 v1.1/M6 v1.8/M7 v1.3/M8 v1.2 без изменения CURRENT.

## Проверки integration head `fe2c9edef5d0dd5f1bdd0582541e9502b2cde4ff`

- Переданные source evidence: FIX-02 L1–L8 и FIX-03 scoped C1–C9 приняты с исходными SHA; ограничения HANDOFF-03 не повышены молча.
- Frontend delivery/draft/reload: `46 passed`.
- Unit + HTTP: `86 passed`, одно deprecation warning.
- Owned PostgreSQL integration: `33 passed`, одно deprecation warning, 291.69 s. Первый запуск был `BLOCKED_BY_SANDBOX`; второй использовал неверное не-whitelisted имя maintenance DB (`8 passed`, `25 setup errors`), итоговый прогон на отдельной `agent4k_pytest` — PASS. Wrapper после PASS вернул exit 1 только из-за попытки присвоить readonly zsh-переменной `status`; pytest завершил `33 passed`.
- FIX-02 Chromium first/next × retry allowed/blocked/reload: `4 passed`.
- FIX-03 actual HTTP/PG Chromium ordinary C1–C6: `1 passed`, 48.117 s; точные startup fingerprints и SHA совпали.
- `npm run lint:js`, `npm run build:web`, `git diff --check`: PASS.
- C7–C9 shared M7 и обязательный стык с EXEC-FIX-01: `NOT_RUN` на финальной комбинации, потому что EXEC-FIX-01 ещё не включён в `origin/main`; это блокирует Ready, но не Draft PR.
- Paid/provider LLM, TEST, human review: `NOT_RUN`.
- Ресурсы: marker-owned preview DB удалена; owned PostgreSQL container остановлен; чужие ресурсы не изменялись.

## Проверки после EXEC-FIX-01 на merge head `ee27ae117e6cdf34f2153c9879eae5083608dc82`

- Фактический source-конфликт отсутствовал; конфликты были только в generated `web/dist`, который пересобран из объединённых исходников. `Api/m10_product_flow.py` и `web/js/screens/interview.js` объединились автоматически.
- Первый общий PostgreSQL прогон: `65 passed`, `19 failed`. Все 19 падений локализованы в FIX-02 test fixture: новый FIX-01 admission запрещал synthetic ordinary Finish с `INTERIM_PENDING`; production-дефект не скрывался.
- Адресная совместимость: FIX-02 fixture теперь явно подставляет только synthetic upstream Finish admission, заявленную в исходном HANDOFF; проверяемая очередь/preparation/scope остаётся production. EXEC-01 domain guards проверяются отдельным реальным recorded M6/M7 набором.
- Frontend FIX-01/03/delivery: `55 passed`; ordinary draft после Continue сохраняется в своём AS scope и не переносится в открытый ASK.
- Unit + HTTP FIX-01/02/03: `87 passed`, одно deprecation warning.
- FIX-02/03 owned PostgreSQL: `33 passed`, одно warning, 336.62 s.
- Точный стык FIX-01+03 owned PostgreSQL: `42 passed`, одно warning, 130.43 s. Покрыты accepted replay после final closure, payload conflict, budget/calendar boundaries, запрет нового ответа, single Turn/attempt и отсутствие нового provider/effect.
- FIX-02 Chromium first/next × retry allowed/blocked/reload: `4 passed`.
- FIX-03 actual HTTP/PG Chromium ordinary C1–C6: `1 passed`, 31.6 s; startup fingerprints и merge SHA совпали.
- Paid/provider LLM: `NOT_RUN` по запрету. CI/human review/TEST: `NOT_RUN` до Draft PR.

## Актуализация после PR #202 и PR #201

- GitHub локализовал конфликт Draft PR #202 в generated `web/dist/main.js`; актуальный `origin/main` оказался `3290421966214ffac4d6193975fd5723b7e19b21` (#201).
- Merge с #201 не дал source-конфликтов; все rename/content-конфликты находились в generated `web/dist`. Выполнены `npm run build:web` из объединённых source-файлов и `git diff --check` — PASS.
- Frontend regression стыка FIX-01/FIX-03/delivery после #201: `48 passed`; `npm run lint:js` — PASS.
- Обязательные GitHub checks до разрешения конфликта имели статус expected/waiting; после push должны запускаться на новом release head. Human review, merge и TEST deploy остаются `NOT_RUN`.

## Release candidate 2.0.90

- Read-only preflight на актуальном `origin/main` определил единственного PATCH-преемника: `2.0.89 → 2.0.90`; владелец явно одобрил `version_bump`.
- `npm run ready:prepare -- --candidate 2.0.90`: PASS; обновлены `pyproject.toml`, `uv.lock`, `web/js/config.js`, `web/index.html`, generated `web/dist`; consistency/release gate PASS.
- После bump: frontend regression `48 passed`, `npm run lint:js` и `git diff --check` — PASS.
- До перевода из Draft: commit/push точного release head и обязательный CI. Human review, merge, deploy и TEST scenarios пока `NOT_RUN`.
