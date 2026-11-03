# PROGRAM01 R04 — достоверная проекция состояния оценки

## Контекст и границы

- База: `origin/main@fb80f214e40019d04aa17031ec05a13a5aa7095e`.
- Ветка: `codex/program01-r04`.
- Источник задачи: `P4K_PROGRAM01_AUDIT_2.0.47_2026-11-02`, R04 / D04.
- Изменяется только read-only проекция состояния назначения в списке участников и её UI-представление.
- Не изменяются методология, жизненный цикл Cycle, планирование M7, расчёт M8, публикация артефактов и правила CI.

## Прочитанные источники

- `README.md`, `CONTRIBUTING.md` — границы продукта и Git-процесс.
- `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md` — рабочий цикл и проверки.
- `docs/architecture/product-4k/1.0/updates/2026-10-01/README.md` — маршрут Change 01, И-5/И-6.
- `docs/methodology/source-sets/2026-10-01/manifest.json` — M8 v1.2: FROZEN, CURRENT=NO.
- `docs/adr/002-cycle-as-dialogue-contracts.md` — C-46, C-56, C-67.
- `docs/architecture/product-4k/m6-cycle-aggregation-contract.md` — результаты и покрытие Cycle.
- `docs/methodology/source-sets/2026-10-01/derived/M8-v1.2.md` — различие результата, отсутствия результата и технического ограничения.
- `Api/m7_planning_repository.py`, `Api/m7_route_replacement.py` — принятый план и позиции маршрута.
- `Api/m8_results.py` — четыре фактических outcome, `partial_result` и `processing`.

## Решение

1. Не объединять `active`, `paused`, `interrupted` в один административный статус.
2. Разрешать старт только для точного назначения с Cycle `prepared` и принятым планом `READY`.
3. Показывать безопасную причину блокировки и ответственного за следующий шаг без внутренних ошибок и персональных данных.
4. Считать прогресс как закрытые позиции / все позиции текущего принятого плана.
5. Проецировать полноту только из сохранённого результата M8; `no_result` не превращать в ноль, технический сбой показывать отдельно.
6. Сохранить отдельные состояния `processing`, `failed`, `report_ready`, `assignment_id` и `cycle_id`.

## Проверки и откат

- Unit: матрица статусов, готовность старта, X/N, M8 outcomes и технический сбой.
- Frontend: отображение новых статусов и описаний в списке/карточке участника.
- Integration/HTTP: запрос организаций на изолированной test/pytest БД, если затронут SQL-контракт.
- Build frontend и `git diff --check`.
- Откат: revert единственного коммита R04; миграций и записей данных нет.

## Фактическая проверка

- `pytest -m "not integration and not e2e and not llm" -q`: **692 passed**, 314 deselected.
- `tests/unit/test_admin_assessment_stage.py`: **4 passed**.
- `tests/e2e/test_ux_fix20_04_admin_readiness_http.py`: вместе с unit-набором **9 passed**.
- `tests/integration/test_path29_participant_owned_stand.py`: **1 passed** на disposable БД через разрешённую maintenance DB.
- Playwright `ADM-STATUS-01 shows`: **1 passed**.
- `node --test tests/frontend/*.test.mjs`: **125 passed** после синхронизации статического контракта ADM-STATUS-01 с новыми раздельными статусами.
- `npm run build:web`: **PASS**.
- ESLint изменённого JS и `git diff --check`: **PASS**.

Первый integration-запуск не был продуктовым FAIL: сначала был передан URL БД вне allowlist maintenance,
затем sandbox запретил localhost socket. Повтор с `STAND_ADMIN_URL=.../postgres` и разрешённым локальным
подключением завершён PASS; данные разработчика и общая БД не использовались.

## Флаги передачи

- `branch_push=true`, `pr=true` после локального PASS.
- `version_bump=false`, `merge=false`, `deploy=false`, `artifact_publish=false` до отдельного решения владельца.
