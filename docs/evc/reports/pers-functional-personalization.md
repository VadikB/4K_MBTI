# Отчёт PERS-01–PERS-06

Статус: **не готово к merge**. Все 27 конечных AS получили детерминированный и
смысловой PASS на одной и той же версии; 34/34 сценарных регрессии исполнены.
Обязательный полный Cycle с реальным провайдером имеет сохранённые успешные
трассы до M8. Локальная матрица, включая полный browser runtime, закрыта; до merge
остаются evidence-архив, полный CI и итоговый review.

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
- full non-LLM unit: PASS, `580 passed, 150 deselected`; HTTP e2e: PASS,
  `66 passed, 11 deselected`.
- full integration на изолированной БД: PASS, `145 passed, 1 skipped,
  584 deselected`; skip — отдельно запускаемый real-provider тест. После исправления
  конкурентного пути M7 узкая DB-регрессия повторена: `2 passed`.
- frontend JS lint/build: PASS. Полный browser с явным
  `STAND_ADMIN_URL=.../postgres`: PASS, `62 passed`. В `S10-B` был воспроизведён
  deadlock между runtime poll и записью clarification из-за обратного порядка
  блокировок; порядок унифицирован как `Cycle → Assessment Situation`, после чего
  отдельно `S10-B` и затем весь browser-набор прошли.
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
- ранние real-provider Cycle получили строгие технические FAIL:
  лишнее поле Evidence, неверный fragment span и `NO_ASSESSMENT` без обязательной
  причины. Ошибки сохранены и не интерпретированы как содержательный результат.
- созданы новые неизменяемые draft-механизмы `m6_evidence/1.0.1` и
  `m6_indicator_assessment/1.0.1`: они уточняют существующие структурные инварианты,
  не меняя методологических норм. Ограниченный validation retry делает не более двух
  реальных вызовов, хранит отклонённую трассу и никогда не исправляет JSON локально.
- два последующих real-provider Cycle прошли до `report_ready`; финальная трасса
  содержит профиль, Case/AS checksums, фактический Turn, M6 Evidence/IA, M7 и M8.
  M8 корректно показывает `partial_result.is_incomplete=true`, не присваивает низкий
  уровень при отсутствии достаточного наблюдения и формирует пустое ready-описание
  без вымышленных утверждений.
- `npm run lint:dead`: FAIL на существующем общем наборе неиспользуемых
  devDependencies/unlisted binaries/exports; изменённые M6/M7/M8 модули не названы
  причиной. Этот анализатор не входит в обязательную локальную матрицу текущего
  изменения; результат сохранён как неблокирующее наблюдение для отдельной очистки.

## Не выполнено

- CI: `NOT_RUN` до публикации коммита/PR.
- итоговый review и evidence-архив: `NOT_RUN`.

Пока evidence-архив, CI и review не закрыты, версия продукта не повышается, PR/merge в
`main` не выполняются. Draft-пакет остаётся `runtime_enabled=false`; технический
допуск AS не является методологической публикацией или разрешением пилота на людях.
