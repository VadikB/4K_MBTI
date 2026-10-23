# PERS-AUDIT: устранение разрывов функциональной персонализации

## Результат

Обычный продуктовый путь создаёт, проверяет, сохраняет и исполняет новую
профессионально персонализированную AS. Серверный допуск закрывается при неполном
или противоречивом результате tester, runtime исполняет авторские события всех
девяти Case, а M8 не связывает навык с чужим основанием.

## Область

- Включено: технические находки F01–F06 независимого аудита от 23.10.2026;
  регрессии, повторная проверка сохранённых 27 AS, настоящий negative/runtime
  контур и содержательный Cycle; итоговая сверка доказательств.
- Не входит: изменение паспортов и содержательных требований; второй этап
  персонализации; присвоение CURRENT/FROZEN; методологический допуск и пилот.

## Контекст, источники и решения

- Основание: запрос владельца «делаем» и целостный архив
  `P4K_PERS_Audit_Evidence_2026-10-23.zip`; `MANIFEST.sha256` — 28/28 PASS.
- Проверяемая база: `origin/main` / `2b707cae904d9c20b20143602b101a8fcacd9583`,
  product 2.0.15, PR #101.
- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, рабочий цикл, матрица
  проверок, Change 01, source-set manifest, ADR-002, traceability и исходная
  карточка/отчёт PERS. Применимы M1 v1.4 FROZEN/CURRENT=NO, M5 1.1 и draft 0.2.
- Аудит — техническое доказательство, не предметная норма. Воспроизведены F01,
  F02, F03 и F06 штатными диагностическими скриптами без DB/LLM.
- Архитектурный адрес: PM-03 готовит и допускает AS, PM-04 исполняет; PM-06
  описывает только по основаниям PM-05. Публичный API и исторические snapshots
  сохраняются.
- Стоп-условия: изменение смысла, публичного контракта, схемы/данных, нового
  контура артефактов, прав и границ развёртывания — нет на текущем шаге.
  Включение draft в пилот и изменение предметного содержания запрещены.
- Решение владельца: исправить аудит одной веткой без промежуточного merge;
  подтверждение — текущий запрос. Требуется решение владельца: нет.

## План и состояние

- Завершено: проверена целостность аудита; воспроизведены заявленные дефекты;
  создана ветка от точного audit SHA; F03/F06 исправлены: противоречивый/пустой
  tester protocol закрывается, каждый M8 skill требует собственного основания.
  Сохранённые 27 AS повторно агрегированы: 27 PASS; пограничные воспроизведения
  теперь отклонены. Адресные unit 22 PASS, полный non-LLM backend 519 PASS.
- Завершено: F02 получил отдельный draft runtime-артефакт `1.0.0`, привязанный
  к неизменяемым Case по id/version/checksum. Добавлены expand-only таблицы,
  неизменяемые версии/привязки, совместимый legacy fallback и явный выбор версии
  для QA/каталога. PostgreSQL-регрессия фактически провела все 9 Case через
  `submit_turn`: 2 PASS; CASE02/07 без вызовов персонажей. Полный non-LLM backend:
  522 PASS, 217 deselected.
- Активный шаг: F05 реализован и проверяется перед единым итоговым PR/merge.
- F05 начат от `7f96ea6abc04061c2e1c0333473085cc9c9a02c8`. Первичная
  трасса выявила два prerequisite-разрыва A01/A02: runtime сохранял только
  checksum принятой generated AS без её неизменяемого содержания и проверяемой
  связи со входом tester; planner ошибочно ограничивал подбор суммой плановых
  длительностей Case. Исправление хранит полный PM-03→PM-04 hand-off (author
  example, accepted AS, refs и checksums tester/compiled runtime) в закрытом
  execution snapshot и проверяет его перед attach. Профиль повторно не
  копируется, сохраняется ссылка/checksum его неизменяемой версии. Плановые
  длительности теперь информационные; 7200 секунд ограничивают фактическое
  прохождение Cycle. Предметное содержание и артефакты F04 не изменены.
- F05 DB runtime выполнен на изолированной PostgreSQL: 34/34 позиций versioned
  `Scenario_regression_plan_v0.2.json` получили отдельные configuration/profile/
  Cycle и прошли штатные `prepare → generator/tester → attach → start →
  submit_turn → events/state/readback`; прямых INSERT Turn нет. Сохранены 34
  первичных JSON и summary; semantic/character adapters контролируемые, поэтому
  результат доказывает runtime-контракт, но не полную предметную приёмку
  CASE.SPEC.01–09. Два functional Cycle дополнительно дошли до M8: раннее
  прекращение сохранило partial/no-result, R09_CHANGED — непустые обоснованные
  partial scores; downstream provider в этих двух трассах контролируемый.
- Устранён проявившийся на первом `start` A01-разрыв композиции: source
  CaseVersion checksum и checksum допущенного compiled generated Case теперь
  различаются и проверяются отдельно. Устранён A02-разрыв C45→M6: стартовые
  материалы присутствовали в событиях, но отсутствовали в закрытом execution
  snapshot; теперь они сохранены как `initial_material` и разрешаются M6.
- Разрыв A02 для multi-case Cycle закрыт: `/next` для второго и последующих
  `CASE.SPEC.*` создаёт ту же durable product-operation, фиксирует профиль и
  CaseVersion, запускает functional generator, полный tester/challenger и только
  после программного допуска прикрепляет и предъявляет AS. PostgreSQL-регрессия
  проходит две позиции без ручной вставки Turn и подтверждает checksum цепочки
  `author source → tester input → accepted AS → compiled runtime` для второй AS.
  A01 (сохранность авторского содержания до M6) подтверждён execution snapshot и
  readback именно принятой AS; уже исправленное содержание F04 не менялось.
- Причина технического M6 `ValueError` установлена и исходная ошибка сохранена
  точным кодом `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`: frozen operation
  собиралась из изменяемых `.env` model/endpoint и расходилась с неизменяемым
  provider contract исполнителя. Пакеты evidence/assessment/admission теперь
  фиксируют version/checksum provider contract. Регрессии проверяют совпадение
  identity и сохранение безопасного предметного error code вместо общего
  `ValueError`.
- Real-provider positive завершён до M8: functional generation сначала получила
  содержательный блокирующий FAIL tester из-за профессиональной несогласованности;
  одна полная repair-генерация сохранила исходный кандидат и findings, затем
  прошла весь tester/challenger, runtime, M6 evidence/assessment/admission и дала
  непустой обоснованный C67. Отдельный controlled-AS real-provider прогон также
  дошёл до M8. Промежуточные `M6_FRAGMENT_SPAN` и
  `M6_ATTRIBUTION_MISMATCH` сохранены как технические отказы строгой валидации,
  устранены повторным полным ответом провайдера с точной обратной связью и не
  классифицируются как недостаточность данных или содержательный FAIL AS.
- A03/A04/A07 не переопределялись и остаются отдельными зависимостями. A03 требует
  методологического подтверждения различения L0/IE/отсутствия IA; A04 — полного
  набора завершений/пауз/уточнений в UI и real-provider; A07 — полного набора
  временных race-сценариев. F05 доказывает только затронутые технические контракты,
  не присваивает CURRENT/FROZEN и не заменяет методологический допуск.
- Выполнена инфраструктурная часть F01: `/assessment/cycles/prepare` теперь
  создаёт отдельную durable product-operation и отвечает `202`; оба UI-пути
  ожидают её завершения и получают Cycle только после committed `admitted` AS.
  Старый assessment queue не переиспользован из-за другого контракта и владения.
  PostgreSQL integration подтверждает отсутствие преждевременного результата,
  успешное завершение, идемпотентный replay и закрытие конфликта ключа. Следующая
  зависимая часть — разнести snapshot/provider/commit и включить общий
  functional generator/tester между claim и сохранением AS.
- Добавлен общий pure-сервис PM-03 для functional AS: версионированные Case и
  author example входят в snapshot с checksum, generator возвращает полную AS,
  tester v2 получает серверный applicability plan, а допуск вычисляется только
  программной агрегацией. Матричный runner переключён на тот же сервис; отдельной
  лабораторной логики допуска больше нет. Два профиля дают разные frozen-входы,
  неполный tester закрывает допуск. После явного разрешения владельца выполнен
  real DeepSeek smoke `PROFILE.01.1`: оба вызова завершились `stop`, tester
  вернул 18 проверок, но AS закономерно не допущена (`generation=FAIL`,
  `tester=FAIL`, `admitted=false`) из-за отсутствующего обязательного поля
  `Предыдущая версия AS`. Секреты не читались и не сохранялись. Следующий шаг —
  исправление/repair этого подтверждённого дефекта без ослабления контракта.
- Исправление подтверждено тем же реальным профилем: точный список обязательных
  полей теперь вычисляется из versioned author example, после чего generation
  прошла `PASS`. Точная выходная схема tester v2 восстановлена в общем сервисе;
  повторный независимый tester: 18 checks, `PASS`, `admitted=true`, 0 incomplete,
  0 blocking/review/warnings, `finish_reason=stop`, 0 parse failures. Это
  технический smoke одного профиля, не методологический допуск всей матрицы.
- Допущенный полный generated AS теперь компилируется тем же JSON-native
  builder’ом, что author package, в `CaseVersionV3` и execution rules; source ref
  привязан к checksum именно generated AS. Недопущенный результат не получает
  compiled runtime payload. Адресная регрессия builder/service: 29 PASS.
- Выявленная зависимость F01→F05: текущий ordinary Cycle выбирает legacy
  `CASE-TDISC-*`, тогда как functional generator работает с `CASE.SPEC.*`.
  Смешивать идентичности запрещено; перед финальным подключением очереди нужен
  отдельный versioned functional catalog/plan и его admission evidence.
- F05 wiring подтверждён PostgreSQL integration: отдельный assessment catalog
  из девяти синтетически допущенных FROZEN-копий `CASE.SPEC.*` привязан к новой
  конфигурации и профилю `specialist_expert`; новый Cycle не содержит
  `CASE-TDISC-*`, выбранная AS использует versioned runtime rules `1.0.0`.
  Полный `test_m10_product_path_db.py`: 10 PASS. Fixture не меняет и не допускает
  репозиторный WORKING/draft пакет. Исправлен обнаруженный trigger: непривязанный
  CaseVersion теперь может перейти в новый статус, но после создания AS изменение
  по-прежнему блокируется как `Referenced M5 CaseVersion content is immutable`.
- Planner и durable product-operation подключены к единой трёхфазной цепочке:
  короткая транзакция фиксирует профиль, Case и route decision; DeepSeek
  generator/tester вызываются без удержания DB-соединения; допущенный результат
  компилируется и атомарно прикрепляется к decision. Runtime snapshot содержит
  полный trace независимого tester и checksum generated AS. Legacy-схема без
  `assessment_configurations.catalog_version_id` продолжает прежний путь.
  Изолированная PostgreSQL-регрессия: целевой functional Cycle — 1 PASS; полный
  `test_m10_product_path_db.py` — 10 PASS; адресные unit — 23 PASS; `py_compile`
  и `git diff --check` — PASS. Провайдер в integration заменён детерминированной
  фикстурой; повторный real-LLM вызов на этом шаге не выполнялся, поскольку
  контракт провайдера уже подтверждён отдельным smoke и стандартная регрессия
  не должна зависеть от внешней модели.
- Следующий шаг: зафиксировать точный head, пройти обязательный CI и review,
  затем выполнить единый squash merge по правилам репозитория.
- F04 negative-контур больше не передаёт tester известный диагноз: отдельный
  mutator создаёт полную AS, исходная AS проходит тем же tester как positive
  control, а независимый verifier подтверждает материальность мутации. Старые
  `27/27` сохранены и не считаются доказательством нового контура. Первый полный
  проход выявил ложные PASS из-за неполных мутаций и подтверждённый пропуск
  готовой классификации. Tester теперь требует adversarial review защищённых
  проверок и запускает отдельный challenger с versioned author baseline; более
  строгий результат нельзя понизить основным tester. Фактически подтверждены и
  отклонены 17 полных мутаций; промежуточные 9 `NOT_APPLIED` и одна отсутствующая
  позиция сохранены как история, но не засчитаны.
- F04 завершён: repair-runner использует последний отзыв независимого verifier,
  не передаёт mutator/tester нарушенный инвариант или ожидаемый вердикт, проверяет
  мутацию до tester и не заменяет основной артефакт неподтверждённой попыткой.
  Verifier различает наличие предмета и фактическое оценочное требование,
  денежную цену и неденежное число, а также ложное переименование одинаковых
  ресурсов; уточнения следуют формулировкам versioned negative-матрицы.
  Applicability plan теперь программно включает все критические запреты поля 18
  конкретного Case как обязательные защищённые проверки наряду с инвариантами
  поля 16 и условиями наблюдаемости поля 22. Итоговый независимый прогон:
  27/27 `APPLIED`, 27/27 `PASS`, пропущенных позиций и ошибок нет. Все PASS
  означают, что положительный контроль допущен, а подтверждённая дефектная AS
  отклонена; это не методологический допуск Case. Real DeepSeek операции и все
  промежуточные repair-attempts сохранены. Адресные unit: 23 PASS; targeted
  PostgreSQL product integration: 1 PASS (9 deselected); `py_compile` и
  `git diff --check`: PASS. Следующий шаг — 34 DB runtime-сценария F05.
- Ветка: `codex/pers-audit-remediation`.
- Изменённые файлы первого шага: `Api/m5_functional_tester.py`,
  `Api/m8_descriptive_report.py`, соответствующие unit-тесты и эта карточка.
- Изменённые файлы второго шага: `Api/m5_runtime_rules.py`, `Api/database.py`,
  `Api/m5_storage.py`, `Api/m5_catalog_integrity.py`, builder execution rules,
  runtime package `functional-personalization-runtime/1.0.0` и unit/integration tests.
- Откат: revert единого исправляющего PR; draft остаётся runtime-disabled,
  исторические AS и tester traces не переписываются.

## Критерии приёмки

- [x] Blocking finding под любым declared status запрещает допуск; пустой или
  некорректный обязательный протокол не допускается и не выдаётся за дефект AS.
- [x] Каждый заявленный M8 skill имеет собственное основание; лишний skill закрыт.
- [x] Все девять Case проходят runtime-проверку; CASE02/07 остаются actorless.
- [x] Продуктовый путь использует единый сервис profile→applicability→generation→
  tester→immutable AS, а матрицы вызывают тот же сервис.
- [x] Negative-тесты проверяют мутированную AS без подсказанного диагноза;
  34 runtime-сценария проверяют события, видимость, состояние и idempotency.
- [x] Новый Cycle проходит штатный API/runtime до M8 с цепочкой идентификаторов;
  недостаточные данные остаются отдельным отрицательным сценарием.
- [x] Новое предметное содержание не встроено в код; исторические артефакты неизменны.

## План проверки

- Адресные unit для tester, M8, builder/runtime и product orchestration.
- Backend non-LLM; HTTP и PostgreSQL integration на изолированной test-БД.
- Frontend/lint/build при затронутом пользовательском пути; browser на локальном
  изолированном stand. Real-provider помечается `llm` и запускается отдельно.
- `git diff --check`; package checksum/verify; полный GitHub CI перед merge.

## Фактическая проверка remediation

- Адресная PostgreSQL-регрессия multi-case и controlled F05: `11 PASS`, включая
  все 34 позиции матрицы и второй Case через durable generator/tester/admission.
- Полный backend non-LLM: `535 PASS`, `220 deselected`; HTTP/e2e: `66 PASS`,
  `11 deselected`; полный integration: `149 PASS`, `1 SKIP`, `605 deselected`.
  Единственный SKIP — explicit real-provider тест, запущенный отдельно.
- Real-provider F05 на текущем head: `1 PASS` за 209.87 s; pipeline
  `report_ready`, непустой C67.
  Первичные JSON и SHA-256 перечислены в
  `docs/evc/evidence/pers-functional-personalization/f05-remediation-2026-10-23/README.md`.
- Frontend unit: `74 PASS`; ESLint и `py_compile`: PASS; web build и release
  consistency для `2.0.16`: PASS.
- Первый полный Playwright: 61 product assertions PASS и один teardown timeout;
  упавший P10.5 отдельно повторён: `1 PASS` за 35.1 s. Причина — fixture ожидала
  SIGTERM без границы; shutdown ограничен 5 секундами с SIGKILL fallback.
  Финальный полный повтор после исправления: `62 PASS` за 12.4 min.
- Не выполнено и не заявляется: человеческая методологическая приёмка Case,
  присвоение CURRENT/FROZEN и расширенная приёмка A03/A04/A07.
