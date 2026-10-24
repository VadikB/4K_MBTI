# ARCH-A05 — честное покрытие и PILOT-120

## Основание и результат

- Пакет `P4K_Case_AS_Cycle_Plan_2026-10-23`, редакция 2.0, карточка ARCH-A05.
- Base: `main@d722181c361e97003b75f96cb7a2d9bcf5de5bb3`, приложение 2.0.22.
- Источники: Product Architecture v1.0 + Change 01 WORKING; M1 v1.4,
  M2 K1/K3 v1.1 и K2/K4 v1.0, M7 v1.3, M8 v1.2 FROZEN.
- Решение владельца PILOT-120: 7200 секунд фактического учитываемого прохождения
  на весь Cycle и 259200 секунд календарного окна; плановая сумма не ограничивает
  подбор и не сокращает Case/AS.

Результат этого PR: участник и проверяющий видят раздельно полный нормативный
состав, план конкретного Cycle, фактические возможности и допущенные вклады;
runtime и проверки фиксируют PILOT-120 без подмены фактического бюджета плановой
длительностью.

## Границы

- Не расширять каталог из 39 уникальных IndicatorID и не менять 61 IndicatorID M2.
- Не менять оценки, агрегацию, достаточность и `partial_score`.
- Не публиковать program revision без точного test organization/configuration.
- Не выдавать controlled/integration/browser проверку за методологическую приёмку.
- A06, real-provider и полный сквозной matrix-run остаются отдельным результатом.

## Стоп-условия

- Смысл/кардинальность предметных сущностей: нет, используется принятое разделение A05.
- Публичный контракт/схема БД: совместимое добавление/представление; миграция не нужна.
- Удаление данных: нет.
- Источник предметного значения: есть, PILOT-120 в карточке ARCH-A05.
- Новый контур артефакта: нет.
- Чувствительные данные/права: нет.
- Откат: вернуть код и frontend текущего PR; опубликованные revisions не изменять.
- Выход за область: нет.

## План

1. Зафиксировать воспроизводимую coverage matrix каталога и уровни покрытия.
2. Уточнить совместимый C-67/API/UI контракт без смешения plan/catalog/facts.
3. Добавить проверки `7200/259200`, произвольной planned sum и неизменности Cycle snapshot.
4. Выполнить targeted, backend, integration, frontend/browser и release checks.
5. После CI и merge отдельно опубликовать/прочитать program revision в test-контуре.

## Проверки и состояние

- `tests/unit/test_m8_results.py`: 8 PASS.
- Backend без integration/e2e/llm: 563 PASS, 224 deselected.
- HTTP/e2e: 68 PASS, 11 deselected.
- Frontend Node: 75 PASS совокупно; адресный A05: 5 PASS.
- PostgreSQL PILOT-120: 6 PASS.
- Полный PostgreSQL integration: 145 PASS на первом проходе; 6 локализованных
  ошибок (maintenance DSN и ожидаемая версия snapshot) повторены после исправления —
  7 PASS. Совокупно 151 PASS, real-provider 1 SKIP по явному маркеру.
- `npm run lint:js`, `npm run build:web`, `scripts/check_release_version.py`,
  `git diff --check`: PASS.

Живая test program revision и readback пока NOT_RUN: выполняются после merge на
точной test organization/configuration. Real-provider и методологическая приёмка
NOT_RUN и относятся к A06/владельцу методологии.
