# Задача 8.1 — содержательный допуск

## Результат и границы
Разделить допуск конкретной итоговой IA к интерпретации, совместный числовой вклад и достаточность по сохранённому плану. Вход — неизменяемые revisions и материал C-45; выход — расширение решения C-56, сохраняемое существующим lifecycle расчёта. История не переписывается, новые нормы M2, GC, legacy cleanup, merge/deploy не входят.

## Контекст и разведка
Основание: [задание](artifacts/task8-1/request.txt). Main после fetch: `8654b97ed6605d560111c37cd291f98f82c41457`. Ветка `codex/task8-1-substantive-admission` от `d5752740770e7241756a3bb42fa94e743da89605` (зависимости 10.4/10.5/11.2/10.6, PR36). Дефект сохраняется: m6_admission v1 сравнивает base_role, запрещает любое contradiction, interpretation_admissible=bool(numeric); calculate заменяет interpretable_revision_ids всеми числовыми IA.

Прочитаны README, CONTRIBUTING, AGENTS, EVC workflow/matrix/artifact-recipe/task-template, архитектурные context/Registry/Change01, ADR002, M6 v1.8 §§6.5–6.8, контракты/загрузчики M6 и потребитель recommendation_basis. Реквизиты оригиналов проверены в [sources.json](artifacts/task8-1/sources.json). M1 v1.4 FROZEN/CURRENT=NO. Технический пакет не означает нормативный допуск.

## Решение и совместимость
PM-05 использует существующий `_gateway_for`/`_call_with_trace`, отдельный внешний draft prompt, строгий JSON-контракт и проверку source/checksum. Семантика: сначала отдельные IA, затем совместный вклад; guards проверяют сохранённые ссылки/авторство/время/принадлежность. Непредъявленные материалы не передаются как доступные. Недоступный механизм даёт processing failure, без разрешающего fallback. Нет новых весов, универсального числа AS или порога расхождения L.

Стоп-условия: новая норма — нет (задание и M6); расширение контракта — разрешено §4.6; изменение владения — нет; миграция истории — нет; новый контур артефактов — нет; права/внешняя граница — прежний gateway; откат — описан; расширение задачи — нет. Предметная приёмка методолога и approved GC остаются отдельно, разработку не блокируют.

## План и состояние
1. Разведка и независимые ожидаемые сценарии — завершено.
2. Версионированный механизм, сохранённые входы и решения, consumer-specific revisions — завершено.
3. Регрессии, owned DB/HTTP → C56/Results/C67/PDF, локальный минимум — завершено.
4. Review — завершено; активный шаг: отдельный Draft PR и CI точного финального commit.

## Проверки
План: unit/backend, HTTP, integration только owned DB по 10.2; contract gateway без реального LLM; diff/checksum. Фактические статусы A8.1-01–12 приведены ниже. Реальный LLM и нормативная приёмка не подменяются scripted fixtures.

## Риски и откат
Внешний вызов увеличивает время расчёта; запрос ограничен размером/timeout. Не читаются .env/рабочая БД/PII. Новые расчёты сохраняют версии входа/механизма/решения. Откат прекращает новые прогоны версии, сохраняет созданные расчёты и поддержку их чтения; не включает v1 автоматически и не переписывает историю.

## Реализация и границы доказательств

Реализованы новый внешний prompt `m6_substantive_admission/2.0.0`, проверенный
resolver сохранённой IA → assessment → evidence → C-45, отдельные individual/joint
решения, проверка требований исходного плана и запрет незаметного уменьшения
состава при неразрешённой ошибке. Сохранённые AS/Case refs, normative criteria,
авторство, полные Turns/events и реально предъявленные материалы доступны механизму.
Ни роль, ни равенство JSON условий не являются семантическим решением.

Агрегатор больше не заменяет точный интерпретационный состав всеми числовыми IA.
Допускается обоснованное исключение конкретной IA, сохраняются причины и исходный
знаменатель покрытия. Последние final revisions с одинаковым временем считаются
неоднозначными, а не выбираются случайно. Новая команда explicit retry идемпотентна;
изменение истории не выполняется. Manual endpoint ограничен QA и не принимает
решения допуска для product Cycle.

C-56/Results сохраняют полный audit; C-67 получает ограниченную проекцию без
полных AI messages/prompts. Recommendations разрешают только конкретные
interpretation-admitted revisions; исключённые повреждённые основания не читаются
вместо разрешённых. Пакеты v1 и исторические записи сохранены.

Новый смысловой разбор реализован через действующий gateway; это не доказательство
точности модели. [Содержательные ожидания](artifacts/task8-1/substantive-expectations.md)
отделены от scripted transport fixtures. Provider-eval и приёмка методолога E01–E05
не проводились, approved GC не получены, Reliability остаётся `not_verified`.
Особенно требуется содержательный review влияния ограниченного сообщения в E02;
универсальное правило несовместимости разных материалов не введено.

## Прослеживаемость

| M6 | Входы | Проверка/решение | Потребитель | Доказательство |
| --- | --- | --- | --- | --- |
| 6.2/6.5/6.6 | Сохранённые IA/assessment/evidence, EB, C-45 | Checksum, scope, final, real refs, авторство/время; individual | admission v2 | material resolver DB test; прежние M6 evidence regressions |
| 6.6.4/6.6.8 | Точные Turns и условия предъявления | independence/clarification Finding; сохранение допустимого основания | individual → M8 | prompt/source review; E03/E04 — semantic NOT_RUN |
| 6.7.1/6.8.2 | Все допущенные individual contexts одного Indicator/Cycle | joint normative_meaning/conditions/contradictions; без порога L | числовой вклад | v2 gateway contracts; E01/E02/E05 — semantic NOT_RUN |
| 6.7.2 | Точные рассмотренные/исключённые revisions и исходный plan | admissible subset, distinct AS после исключений; неизвестное условие блокирует вклад | calculate | unit mean/zero/exclusion/sufficiency/duplicate tests |
| 6.7.3–6.7.4 | Иерархия M2, первоначальный состав, принятые IA | Равные веса, четыре исхода, пять покрытий | C56/Results/C67/PDF | прежние aggregation tests + новый saved-chain test |
| 6.8.1–6.8.3 | Findings, limits, exact source/mechanism/hash, AI trace | Раздельные ошибки и недостаток материала; explicit retry | M8/recommendations/history | failure/foreign-ref tests; DB immutable readback и HTTP/PDF |

Карта новых полей/API/версий — в [контракте](../../architecture/product-4k/m6-cycle-aggregation-contract.md#дополнение-81--содержательный-допуск-v2-05102026).
Формулы aggregation v1 не менялись; новая версия admission учитывается отдельно.

## Критерии приёмки и проверки

| Критерий | Фактический статус |
| --- | --- |
| A8.1-01/02 | PASS технически: один IA, требования плана, L0, L1/L3, n и spread; семантическая обоснованность ответов модели NOT_RUN |
| A8.1-03/04/05 | PASS передача полного материала и контракты Findings; NOT_RUN содержательный provider-eval и методологическая приёмка E01–E05 |
| A8.1-06 | PASS guards scope/checksum/refs/M2/duplicate и существующие time/author guards; неизвестный mapping не допускается |
| A8.1-07/08 | PASS точный interpretation subset, qualitative/no_result, исключения/знаменатели и старые четыре исхода |
| A8.1-09/10 | PASS новая calculation revision, идемпотентность ключа, immutable Results/Report, разные failure/material states, сохранение индивидуального основания |
| A8.1-11 | PASS реальные DB/HTTP/C67/PDF на owned БД; стандартный набор без реального LLM |
| A8.1-12 | PASS независимые описанные ожидания/источники/ограничения; нормативная приёмка NOT_RUN |

Команды и логи:

- `PYTHONPATH=. .venv/bin/python -m pytest docs/evc/tasks/artifacts/task8-1/reproduce-baseline.py -q -s` — 1 PASS; [исходное поведение](artifacts/task8-1/baseline-repro.log) проверено на неизменяемом parent. Вывод: условия отсутствовали во входе, не «любые различия запрещают среднее».
- `npm run test:backend` — 362 PASS, exit 0; [unit-final.log](artifacts/task8-1/unit-final.log).
- `npm run test:backend:http` — 40 PASS, exit 0; [http-final.log](artifacts/task8-1/http-final.log).
- `STAND_ADMIN_URL=<localhost maintenance> TEST_DATABASE_URL=<owned product4k_pytest_…> npm run test:backend:integration` — 87 PASS, exit 0; [integration-final.log](artifacts/task8-1/integration-final.log). После финальной проекции C-67 повторены затронутые пять DB/HTTP/PDF тестов; точный финальный commit дополнительно проверяется CI.
- `M81_ARTIFACT_DIR=… TEST_DATABASE_URL=<owned DB> .venv/bin/python -m pytest --run-integration tests/integration/test_m6_substantive_admission_db.py -q` — 5 PASS, exit 0; [target-integration-final.log](artifacts/task8-1/target-integration-final.log).
- Чистый bootstrap 10.2 — PASS. Общий suite использовал другую пустую owned БД: старые queue-тесты создают собственные таблицы в public. Рабочая/shared БД не использовалась.
- PDF: текстовые ограничения C-67 совпали с PDF для четырёх исходов (2–3 страницы); визуально проверены три страницы `joint_failure`. Использован навык pdf, pypdf + pypdfium2. Макет не изменялся.
- `git diff --check` — PASS на рабочем diff; контроль перед commit обязателен.

Сбои первых прогонов: 3 unit из-за отсутствующего необязательного admissions в старом
fixture — исправлена совместимая проекция; 1 HTTP из-за нового QA guard — fixture
явно задаёт scope и проверяет запрет product manual. Первый общий integration:
6 FAIL/13 ERROR на предварительно bootstrapped БД, включая конфликт legacy queue
DDL; повтор на пустой owned БД локализовал 3 FAIL (maintenance URL и импорт тестового
gateway из subprocess). Исправлены harness и явная fixture нового этапа; проверки
не отключались. Итоговый общий набор — 87 PASS.

## Review / непроверенное / передача

Review выполнен по EVC checklist: границы PM сохранены; управляющие документы не
менялись; новые публичные поля additive; миграций и новых прав нет; ложного
разрешающего fallback нет; исторические пакеты не редактировались. Внешний вызов
ограничен существующим timeout/input limit, но реальная latency/стоимость не измерялась.

Не проверены реальный provider, содержательная точность, экспертные GC и deployment.
Отсутствие GC не блокирует техническую разработку, но не закрывает предметную приёмку.
Открытых вопросов, без ответа на которые нельзя продолжать техническую реализацию,
нет. Следующий предметный шаг: методолог проверяет E01–E05 и оценивает реальные ответы
закреплённой версии механизма. Технический следующий шаг: отдельный Draft PR,
CI точного head; merge/deploy в рамках этой передачи не выполняются.

## Передача в Git

Создан [Draft PR #37](https://github.com/VadikB/4K_MBTI/pull/37) поверх
[PR #36](https://github.com/VadikB/4K_MBTI/pull/36). Код и локальные доказательства:
`1fa5ff4d70467877b6569fa30bfdb0782d8e66be`; последующий handoff-коммит изменяет только
эту запись. Diff результата: 51 файл, включая синтетические JSON/PDF/PNG и логи.
Реализация, локальный минимум, review и публикация Draft PR завершены. Статус CI
точного финального head и ссылки на запуски фиксируются в описании/Checks PR;
ранний зелёный запуск не переносится на последующий commit. Рабочая ветка
`codex/task8-1-substantive-admission`. Никакого merge/deploy не выполнялось.

Следующий независимый шаг: предметный review E01–E05 методологом и реальный
provider-eval закреплённого механизма. До него не заявляется полная содержательная
приёмка A8.1-03/04/05 и нормативная Reliability.
