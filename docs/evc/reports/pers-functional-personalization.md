# Отчёт PERS-01–PERS-06

Статус: **не готово к merge**. Все 27 конечных AS получили детерминированный и
смысловой PASS на одной и той же версии; 34/34 сценарных регрессии исполнены.
Обязательный полный Cycle с реальным провайдером пока не имеет воспроизводимо
успешной сохранённой трассы до M8, поэтому CI/review и итоговое слияние не начинаются.

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
- исходные реальные generation/tester: 27 запущено; 25 полных цепочек, 2 технических FAIL
  (`PROFILE.06.1` truncated, `PROFILE.09.1` timeout); исторически детерминированно 11 PASS / 14 FAIL;
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
- первичные артефакты подтвердили, что у `PROFILE.06.1` и `PROFILE.09.1` полные AS
  были сохранены, а сбои произошли на стадии tester. Tester v2 повторён по тем же
  AS/hash: обе позиции PASS, без регенерации. Итог: 27 deterministic PASS,
  27 semantic PASS, 27 технических допусков; старые ошибки сохранены как история.
- реальные negative: PASS, `27/27`; каждый дефект отклонён отдельной DeepSeek-операцией
  с локализованным инвариантом.
- изолированный PostgreSQL после LLM-матрицы: PASS, `5 passed` для functional import,
  runtime/idempotency/pause-resume и cycle runtime.
- повторная DB-регрессия штатного пути M5/M7/M10: PASS, `11 passed`.
- 34 фактических сценарных запуска: PASS, `34/34`; две отрицательные scope-позиции
  считаются PASS только при обнаруженном дефекте и явном запрете предъявления.
- текущая конфигурация `deepseek-flash` подтверждена двумя новыми tester-операциями:
  requested model совпал с actual provider model; исторический identity FAIL сохранён.
- полный real-provider Cycle запускался неоднократно. Один прогон фактически создал
  M8 report, но тест упал при последующем readback из-за неверного имени колонки и не
  сохранил полный evidence-файл. Повторные прогоны получили строгие технические FAIL:
  лишнее поле Evidence, неверный fragment span и `NO_ASSESSMENT` без обязательной
  причины. Это не содержательный FAIL AS, но обязательная воспроизводимая трасса
  `profile → Case → AS → M6 → M7 → M8` пока не доказана.
- полный unit при локальном `.env`: FAIL, `3 failed / 256 passed`, потому что
  `DEEPSEEK_MODEL=deepseek-chat` не совпадает с provider contract `deepseek-flash`;
  контрольный прогон с `DEEPSEEK_MODEL=deepseek-flash`: PASS, `259 passed`.

## Не выполнено

- Полный Cycle с реальным LLM через M6/M7/M8: `TECHNICAL_ERROR`; сохранены реальные
  provider traces и причины строгой валидации, но нет одного воспроизводимо успешного
  и полностью архивированного прогона.
- 14 stand-dependent browser runtime и CI: `NOT_RUN`.
- итоговый review и evidence-архив: `NOT_RUN`, так как обязательный full Cycle остаётся
  техническим блокером.

Пока full Cycle, CI и review не закрыты, версия продукта не повышается, PR/merge в
`main` не выполняются. Draft-пакет остаётся `runtime_enabled=false`; технический
допуск AS не является методологической публикацией или разрешением пилота на людях.
