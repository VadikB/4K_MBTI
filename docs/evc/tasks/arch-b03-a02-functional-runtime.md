# ARCH-B03/A02 — штатные planner-исходы и единый functional runtime

## Основание и результат

- Base: `main@31779afc5ea53c0b62e63aa62f8640aec81b5fd1`, приложение `2.0.19`;
  release candidate: `2.0.20`.
- Внешний пакет: `P4K_Case_AS_Cycle_Plan_2026-10-23`, редакция 2.0;
  карточки `04_A02_Accepted_AS_Runtime.txt` и `05_B01_B03_Error_Fixes.txt`.
- B01/B02 и A01 уже интегрированы PR #103/#106 и не повторяются.
- Результат: functional CASE.SPEC проходит через generator/tester только для нового
  решения `SELECTED`; штатные невыбранные решения завершают операцию без внешнего
  вызова и без вставки AS. Автоматический профиль и последующие Case используют
  тот же механизм по замороженному маршруту Cycle.

## Границы

Включено: `prepare`, compatibility `start`, `next`, polling/replay, состояния
`WAITING_CURRENT_AS`, `OUT_OF_TIME`, `COLLECTION_CLOSED`, `NO_ADMISSIBLE_CASE`,
идемпотентный возврат уже назначенной AS, participant-safe projection.

Не включено: real-provider матрица A06, общие fencing/lease изменения A03,
полное pinning зависимостей A04, методологическая приёмка и Reliability.
Публичная схема и БД не мигрируют. Исторические snapshots/evidence не меняются.

## Источники и контракты

- `README.md`, `CONTRIBUTING.md`, `AGENTS.md`;
- `docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`;
- `docs/adr/002-cycle-as-dialogue-contracts.md`;
- `docs/architecture/m7-cycle-planning-contract.md`;
- `docs/evc/change01-traceability.md`;
- `Api/product_cycle_preparation_queue.py`, `Api/m10_product_flow.py`,
  `Api/m7_cycle_planner.py`, `Api/routes.py` и их unit/HTTP/PostgreSQL тесты.

Предметных пробелов для зависимой реализации не выявлено. Статусы planner уже
определены контрактом; изменение их смысла или правил достаточности не требуется.

## План и критерии

1. Разрешить принадлежащий пользователю профиль до выбора functional/legacy пути.
2. Для начатого Cycle классифицировать путь по замороженному маршруту, не по
   текущему `assessment_configurations.catalog_version_id`.
3. До generator/tester проверить решение: не-`SELECTED` вернуть как штатный
   completed outcome; назначенную AS переиспользовать без новой генерации.
4. Запретить synchronous compatibility-подготовку functional AS; клиент получает
   стабильный конфликт с указанием штатного `/prepare` пути.
5. Проверить четыре planner-исхода, replay, auto/explicit profile, pointer change,
   multi-case accepted traces, безопасные HTTP ответы и отсутствие внешних вызовов.

## Проверки до PR

- адресные unit/HTTP/PostgreSQL regression;
- `npm run test:backend`, `npm run test:backend:http`;
- полный integration на изолированной PostgreSQL БД с `test`/`pytest` в имени;
- frontend regression/build, если меняется клиент;
- `git diff --check`, release check; обязательный GitHub CI exact head.

## Откат

Revert одного squash commit возвращает прежнюю orchestration-ветку. Схема БД и
сохранённые AS/snapshots не меняются. При откате нельзя раскрывать закрытые поля,
ослаблять owner checks или переписывать исторические результаты.

## Состояние

- Реализовано: разрешение auto/explicit profile до классификации; frozen route для
  последующих Case; generator только для нового неназначенного `SELECTED`;
  compatibility start не обходит functional tester; UI различает четыре исхода.
- Адресные unit/HTTP: 18 passed; PostgreSQL functional path: 2 passed.
- Backend: 551 passed, 223 deselected; HTTP: 68 passed, 11 deselected.
- Frontend: 74 passed; `lint:js`/build PASS. `lint:dead` фиксирует 11
  существующих unused exports и одну подсказку конфигурации вне diff задачи.
- Полный integration: 150 passed, 1 skipped (явный real-provider acceptance),
  623 deselected; 491.21 s. CI exact head: NOT_RUN.
- Активный шаг: финальная версия/отчёт и передача PR.
- Открытые вопросы: нет.
