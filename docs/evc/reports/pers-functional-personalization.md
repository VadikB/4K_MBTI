# Отчёт PERS-01–PERS-06

Статус: **не готово к merge**. Tester orchestration исправлен: 25 сохранённых AS
повторно проверены без регенерации и после технической нормализации/одного локального
исправления получили PASS. Две позиции из 27 остаются технически незавершёнными;
сценарная матрица, полный Cycle, CI и review ещё не пройдены.

## Реализовано

- PERS-01: единый schema-v3 package для девяти актуальных Case/AS; полные author
  snapshots, provenance, hashes, поля 16–19/22, события и персонажи.
- PERS-02–04: добавлен возобновляемый real-provider runner для 27 синтетических
  M4-профилей, полной AS, независимого tester и не более двух repair-итераций;
  добавлен отдельный real-provider runner 27 отрицательных примеров.
- PERS-05: новые ключи событий нормализованы в штатные execution rules; доказаны
  идемпотентный импорт и неизменяемость версии.
- PERS-06: сохранены 34 scenario plans, фактические обезличенные provider-операции,
  AS/tester/repair артефакты, заполненная выгрузка методологу, демо-инструкция и
  миграция/откат. Методологический допуск не заявлен.

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
- новый matrix runner: unit PASS, `3 passed`; совместно с package — `9 passed`.
- реальные generation/tester: 27 запущено; 25 полных цепочек, 2 технических FAIL
  (`PROFILE.06.1` truncated, `PROFILE.09.1` timeout); детерминированно 11 PASS / 14 FAIL;
  независимый tester 0 PASS / 25 FAIL; выполнено 50 ограниченных repair-итераций;
  допущено к предъявлению 0.
- tester protocol v2: применимость строится из версии Case, общие проверки обязательны,
  отдельные результаты имеют `PASS|FAIL|NOT_APPLICABLE|NOT_RUN|INDETERMINATE|TECHNICAL_ERROR`,
  итог вычисляется программно; 12 unit-тестов агрегации PASS.
- повторная проверка тех же 25 AS без регенерации: после исправления ложной агрегации
  `NOT_APPLICABLE` — 10 PASS / 15 FAIL; после снятия строго распознанного response
  envelope — ещё 14 PASS; `PROFILE.02.2` имел подтверждённую неполную профессиональную
  замену в материалах/словаре/наблюдаемости, исправлен локально и повторно получил PASS.
  Итог сохранённых AS: 25 PASS / 0 FAIL. Старые результаты сохранены отдельно.
- судьба остальных позиций: `PROFILE.06.1` — generation оборвалась как `truncated`
  на лимите 32768; `PROFILE.09.1` — provider timeout; обе имеют `TECHNICAL_ERROR`,
  не интерпретируются как содержательный FAIL и не допущены.
- реальные negative: PASS, `27/27`; каждый дефект отклонён отдельной DeepSeek-операцией
  с локализованным инвариантом.
- изолированный PostgreSQL после LLM-матрицы: PASS, `5 passed` для functional import,
  runtime/idempotency/pause-resume и cycle runtime.
- полный unit при локальном `.env`: FAIL, `3 failed / 256 passed`, потому что
  `DEEPSEEK_MODEL=deepseek-chat` не совпадает с provider contract `deepseek-flash`;
  контрольный прогон с `DEEPSEEK_MODEL=deepseek-flash`: PASS, `259 passed`.

## Не выполнено

- 34 scenario на новой AS: `NOT_RUN`; после допуска 25 AS это следующий этап.
- Полный Cycle с реальным LLM через M6/M7/M8: `NOT_RUN`; фактической траектории
  участника пока нет, и выгрузка сообщает об этом явно.
- 14 stand-dependent browser runtime и CI: `NOT_RUN`.
- локальная конфигурация модели требует привести `DEEPSEEK_MODEL` к
  `deepseek-flash`; фактический provider в LLM-артефактах уже возвращал эту модель.

Пока две позиции матрицы, scenario/full-cycle, CI и review не закрыты, версия продукта
не повышается, PR/merge в `main` не выполняются.
