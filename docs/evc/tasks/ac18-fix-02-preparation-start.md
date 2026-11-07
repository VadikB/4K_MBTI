# AC18-FIX-02 — подготовка ситуации и надёжный первый старт

Статус: локально проверенный кандидат; требуется review/разрешение на передачу. Основание: пакет
`P4K_AC18_FIX_02_Preparation_Start_2026-11-07.zip`, редакция 1.0 от 07.11.2026.

## Основание и границы

- Base: `origin/main` = `65c1f4c04466b60d4c6ce4611346fc92c617ed74`, версия 2.0.75.
- Ветка: `codex/ac18-fix02-preparation-start`; отдельный worktree `/tmp/4k-ac18-fix02`.
- Прочитаны: `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`, Product Architecture,
  Registry, Change 01, task SourceSet manifest, `TASK.txt`, `SOURCES.md`,
  `VISUAL_ACCEPTANCE.txt` и адресные runtime/тесты подготовки и старта.
- Не меняются: методология, published snapshots, prompts, admission/repair policy, схема БД.
- Push, PR, merge, deploy и real-provider LLM этим запуском не разрешены.

## Таблица решений

| ID | Принятое поведение | Факт main | Решение |
|---|---|---|---|
| P2-AC01/02 | Неполный protected review не допускает AS | `normalize_results()` требует полный `adversarial_review`; aggregation закрывает admission; тесты различают invalid/incomplete/correct | Уже исправлено; адресная регрессия |
| P2-AC03/04 | queued/running/failed/unknown различаются; readback не создаёт операцию | onboarding использует точную owned operation и server `start_readiness`; transport error не объявляется terminal failure | Уже исправлено; адресная регрессия |
| P2-AC05 | После потери ответа первого start сначала читается runtime; второй Cycle/AS не создаётся | POST был идемпотентен на сервере, но клиент после transport failure readback не выполнял | Исправлено и проверено |
| P2-AC06 | Сервер повторно проверяет scope/admission | `start_prepared()` повторяет assignment/profile/readiness checks под lock | Уже исправлено; integration требуется перед передачей |
| P2-AC07/08 | Отдельная техническая и визуальная приёмка | Шаблон есть, новый кандидат ещё не предъявлен владельцу | Подготовить после полного локального прогона |

## Реализация

Добавлен клиентский start adapter: один POST с idempotency key; только при транспортной
неопределённости выполняется read-only GET того же Cycle. Успех восстанавливается лишь
по persisted runtime с предъявленной первой AS. Состояние `admitted` без participant
projection не выдаётся за успешный старт; пользователю возвращается безопасное unknown.

## Проверки

- `node --test tests/frontend/product-cycle-start.test.mjs tests/frontend/product-cycle-preparation.test.mjs tests/frontend/onboarding-flow.test.mjs` → PASS, 11.
- `.venv/bin/python -m pytest -q tests/unit/test_assessment_start_readiness.py tests/unit/test_m5_functional_generation_service.py` → PASS, 49.
- `npm run lint:js` → PASS.
- `npm run build:web` → PASS.
- `node --test tests/frontend/*.test.mjs` → PASS, 150 (после обновления совместимого W02 contract test).
- Полный backend без integration/e2e/llm → PASS, 956.
- HTTP e2e → PASS, 108.
- PostgreSQL `test_pilot_start_admission_db.py` → PASS, 7; отдельный test-контейнер остановлен.
- Browser lost-start + visual 1440/768/390/320 → PASS, 1; кадры и ограничения:
  `docs/evc/evidence/ac18-fix02-preparation-start/README.md`.
- CI/deploy/real-provider/физические устройства/визуальное решение владельца → NOT_RUN.

## Риски и откат

Схема/данные/config не меняются. Клиент выполняет один дополнительный owned GET только
при потере POST-ответа. Откат — совместимый revert JS adapter, импорта, тестов и сборки;
сохранённые Cycle/AS/ответы не удаляются.

## Следующий шаг

Выполнить финальный diff/review-check, зафиксировать commit и запросить отдельное
разрешение на push/PR. Real-provider verification остаётся отдельным NOT_RUN без
прямого разрешения; владелец отдельно принимает визуальный результат.
