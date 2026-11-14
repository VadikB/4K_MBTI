# REMAIN_05 — первая ситуация и явный старт

Основание: команда владельца «Делаем REMAIN_05», 14.11.2026; карточка1.6 и общий порядок1.0 прочитаны как требования. Результат F04: безопасные ошибки GET/PUT/POST и recovery возможного старта. F27: адресно проверить существующую queue/admission/persistence, не менять policy. PM-03 LU03.2–4 → PM-04 explicit start; вход PM-02 LU02.6/8, C-23/24/34. Оценивание M6/M8 не затрагивается.

## Источники и границы

Прочитаны README, CONTRIBUTING, AGENTS, EVC agent-workflow/verification-matrix/artifact-recipe/task-template/review-checklist; context1.0/registry; Change01 README/адресные И-1/2/3/6/7; task manifest2026-10-01; ADR002 C23/24/34 и повторы; change01-traceability T01–04; decision-register (новых полномочий не выводим); M4.Context1.0 §§4/6, M5.Methodology1.1 AS/QA/admission из originals, M7v1.3 derived первый старт/время; REMAIN01/04 STATE/CHECKS; исторический ac18-fix02-start-unknown-readback. Источники FROZEN/CURRENT=NO, архитектура WORKING; runtime и технический PASS не повышают статус методологии. Profile/candidate/checksum/required IDs/admission сохранены. Исторический fd… UNKNOWN; иных предметных пробелов для транспортной правки нет.

Читаемые код/тесты: api.js fetchWithDeadline/readApiResponse; product-cycle-start/preparation; screens/onboarding/interview; actual m10 start_prepared, pilot start/readback SQL/HTTP tests; queue/protocol tests по CHECKS. Рецепт: новый предметный артефакт не нужен, prompts и defaults не вводятся, legacy долг не расширяется.

Стоп-условия workflow: 1 нет (смысл не меняется); 2 нет (публичный API/PM/схема не меняются); 3 нет (миграции/удаления нет); 4 нет (технический транспорт по действующим контрактам); 5 нет (новый контур не нужен); 6 нет (ACL/privacy/deploy не меняются); 7 нет (revert кода, данные сохранены); 8 нет (локальная реализация/controlled проверки в scope). Значимые новые решения владельца не нужны. Открытый вопрос fd… не блокирует подтверждённые ветки.

План: разведка → адресное исправление и регрессии → controlled HTTP/PG/browser до первой AS и локальный минимум → review/commit/bundle архитектору. Критерии все7: F04-AC01–04, F27-AC01–03. Команды, факты и ограничения — CHECKS; текущий шаг/ресурсы — STATE. Откат revert только собственных изменений, без переписывания immutable истории. CI/frontend/pytest/full-verification на будущем PR, человеческое review/выпуск отдельно.

## Выбранные байты источников

- ProductArchitecture.Change01 1.0/01 WORKING: `docs/architecture/product-4k/1.0/updates/2026-10-01/source.pdf` SHA-256 `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081` — MATCH.
- M1 1.4 FROZEN: `docs/architecture/product-4k/m1/v1.4/source.docx` SHA-256 `5fa5ab5735dfe57fac6ef3c93aca50d149fbd7abd365edf80d362c10e2d7a975` — MATCH.
- M4.Context 1.0 FROZEN: `docs/methodology/source-sets/2026-10-01/originals/M4.Context-v1.0.docx` SHA-256 `07875e93ae422668b1b30cd60bc1c6140cae91db12b0b80ba4abca441cfe9291` — MATCH.
- M5.Methodology 1.1 FROZEN: `docs/methodology/source-sets/2026-10-01/originals/M5.Methodology-v1.1.docx` SHA-256 `dc96f9b48e0711326c0c4239d63f50a2fa1e63176a728f3e9eb4420f9efb77c1` — MATCH.
- M7 1.3 FROZEN: `docs/methodology/source-sets/2026-10-01/originals/M7_Assessment_Cycle_v1.3_FROZEN_2026-09-30.docx` SHA-256 `50a0d53a3aaf6258957ecc6d9e89f27d922bfbe4cd55668185d475c87f4e2f10` — MATCH.
- Постановка `/Users/vadim_bogachev/Downloads/P4K_REMAIN_05_v1_6.txt` SHA-256 `055e7dfc0fc14ef520a5ead0881eaf3763a4a5a4503625dd44adb535ea86c399`.
- Постановка `/Users/vadim_bogachev/Downloads/P4K_REMAIN_Execution_Rules_v1_0.txt` SHA-256 `ece5f67dde34f7771e0084789f40617131e99d767ad5d8a57cac320320796c31`.


## Продолжение архитектора

Прямое уточнение владельца14.11.2026: «я архитектор и это машина архитектора. продолжаем». Продолжение описанного этапа подготовки кандидата/PR: branch_push/pr/version_bump=true, PATCH2.1.5 от fresh main2.1.4; merge/deploy/artifact_publish=false до отдельного допуска готового результата. Тот же worktree/ветка, повторная разработка не выполняется. Новые факты — STATE/CHECKS.
