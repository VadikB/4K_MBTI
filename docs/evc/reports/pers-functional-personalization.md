# Отчёт PERS-01–PERS-06

Статус: **F05 технически выполнен, итоговая интеграция не разрешена**. Все 27
результатов F04 сохранены. Новые 34/34 F05-трассы исполнены через PostgreSQL
runtime, но controlled semantic adapters не дают права объявлять полную предметную
приёмку CASE.SPEC.01–09. Утверждение ниже о прежних успешных real-provider Cycle
относится к историческому legacy-пути; новый functional path до M8 реальным
provider пока не завершён и учитывается как `NOT_RUN/TECHNICAL_ERROR`.

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

## Дополнение F05 от 23.10.2026

- База: ветка `codex/pers-audit-remediation`, исходный commit
  `7f96ea6abc04061c2e1c0333473085cc9c9a02c8`; source plan v0.2, checksum
  `bee5ca5a001a47f9651239589ab2f90a0058a4186e85ce573f19bb3d7c474f29`.
- 34/34 отдельных Cycle прошли штатные API без прямого INSERT Turn; сохранены
  requests, responses, events, states, readback и AS/tester checksums в
  `docs/evc/evidence/pers-functional-personalization/f05-runtime-db/`.
- A01/A02: сохранён полный immutable hand-off author source → tester input →
  accepted generated AS → compiled runtime; profile и source CaseVersion
  проверяются собственными version checksums. Стартовые материалы восстановлены
  в execution snapshot, поэтому C45→M6 больше не теряет provenance.
- Пилотное решение 120 минут реализовано: это фактический elapsed budget Cycle;
  сумма плановых длительностей не блокирует план и выбор следующего Case.
- Два controlled downstream functional Cycle дошли до `report_ready`: раннее
  прекращение сохранило ограничения/no-result, содержательный R09_CHANGED дал
  непустые partial scores. Это техническая проверка M8, не real-provider допуск.
- Real-provider: зафиксирован timeout tester; отдельные повторы успешно прошли
  generation/tester/admission/runtime/C45, но M6 processing завершился
  `ValueError` без assessment-request. Поэтому real-provider positive M8 —
  `NOT_RUN`; ошибка сохранена как `TECHNICAL_ERROR`, не как дефект AS и не как
  «недостаточные данные».
- Проверки: non-LLM unit/backend `595 passed`; полный PostgreSQL integration
  `144 passed, 5 failed` при ошибочном `STAND_ADMIN_URL`, затем все пять stand
  проверок повторены с maintenance DB — `6 passed`; адресная F05 PostgreSQL —
  PASS, 34/34 и два M8-пути. A03/A04/A07 остаются отдельными зависимостями.
- Review-blocker: multi-case `next_situation` после первой позиции пока обходит
  functional generator/tester и использует legacy synchronous prepare. Поэтому
  единый новый functional Cycle целиком не доказан; merge в `main` не выполнен.

Пока evidence-архив, CI и review не закрыты, версия продукта не повышается, PR/merge в
`main` не выполняются. Draft-пакет остаётся `runtime_enabled=false`; технический
допуск AS не является методологической публикацией или разрешением пилота на людях.
