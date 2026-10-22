# Отчёт PERS-01–PERS-06

Статус: **не готово к merge**. Технический draft и офлайн/БД-проверки выполнены;
обязательные реальные LLM-прогоны, полный Cycle, CI и review не пройдены.

## Реализовано

- PERS-01: единый schema-v3 package для девяти актуальных Case/AS; полные author
  snapshots, provenance, hashes, поля 16–19/22, события и персонажи.
- PERS-02–04: исходные generation/tester контракты, 27 профилей и 27 отрицательных
  примеров включены как версионные артефакты; статусы остаются `NOT_RUN`.
- PERS-05: новые ключи событий нормализованы в штатные execution rules; доказаны
  идемпотентный импорт и неизменяемость версии.
- PERS-06: сохранены 34 scenario plans, выгрузка методологу с явными пустыми
  полями фактического прогона, демо-инструкция и миграция/откат.

## Фактические проверки

- `shasum -a 256 -c MANIFEST.sha256` внешнего пакета: PASS 4/4.
- `shasum -a 256 -c MANIFEST.sha256` source package: PASS 149/149.
- `scripts/build_m5_functional_package.py ...`: PASS, 9 Case, 55 targets, characters
  `1,0,3,1,1,3,0,2,1`.
- unit functional + Sales regression: PASS, 15 tests.
- integration functional import/readback: PASS, 1 test; Sales regression: PASS, 2 tests.
- full non-LLM unit: PASS, `497 passed`; HTTP e2e: PASS, `66 passed`.
- full integration: PASS после явного `STAND_ADMIN_URL=.../postgres`: `140 passed` в основном
  прогоне и `6 passed` в повторе пяти stand-падений с корректной maintenance DB;
  первичные FAIL были конфигурационными, не дефектом кода.
- frontend lint/build: PASS. Browser: 48 PASS; 14 runtime `NOT_RUN` из-за отсутствия
  внешнего `STAND_ADMIN_URL` в Playwright-контуре.

## Не выполнено

- 27 реальных generation + tester прогонов: `NOT_RUN`; реальный provider-контур для
  полной AS не доведён до продуктового вызова.
- 27 negative и 34 scenario фактических прогона: `NOT_RUN`; пока проверена их
  целостность как inventory.
- Полный Cycle с реальным LLM через M6/M7/M8: `NOT_RUN`; траектории и методологической
  выгрузки из реальных данных нет.
- 14 stand-dependent browser runtime и CI: `NOT_RUN`.

Пока эти пункты не закрыты, версия продукта не повышается, PR/merge в `main` не выполняются.
