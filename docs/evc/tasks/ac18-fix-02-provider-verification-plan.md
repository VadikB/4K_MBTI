# AC18-FIX-02 — план real-provider проверки на итоговом SHA

Статус: **PLAN_READY / LLM NOT_RUN**. Это самостоятельный документационный
результат после продуктового PR #182 и отдельного визуального PR #183. Пакет
`P4K_AC18_FIX_02_Preparation_Start_2026-11-07.zip` — источник требований, но
сам по себе не разрешает платный вызов. Ранее выданные допуски относились к
другим SHA; новый прогон требует отдельного прямого решения владельца.

## Основание, границы и точные идентичности

- База подготовки плана: `main@58bcfa291d8f49a08f18ecd8cc62113a1f544da4`,
  версия `2.0.76`. Это не допуск к запуску на указанном SHA. Исполняемый
  кандидат — чистый неизменяемый commit/tag после принятия всех связанных PR;
  владелец выбирает его отдельно вместе с лимитом затрат. Перед запуском
  повторить code identity и сверить актуальный deployed test SHA. Любое
  дальнейшее продвижение `main` требует повторного выбора кандидата и
  бесплатного preflight; SHA ветки или один лишь номер версии недостаточны.
- Программа: опубликованная `specialist_pilot@1.2`, id `2`, exact receipt
  SHA-256 `09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b`.
  Она уже прошла разрешённый limited-pilot PATH на `e63eba67…`/2.0.66,
  но тот PASS не переносится на 2.0.76. Default `published-pilot` без
  явного selector использует историческую 1.1, поэтому для этой проверки
  требуются `--program-receipt`, `--program-receipt-sha256` и
  `--program-version 1.2` вместе. Точный путь к receipt установить
  read-only на execution host и сверить его bytes до обращения к env/БД.
- Проверяемый участок AC18-FIX-02: подтверждённые сведения участника →
  единственная M5 preparation operation → обязательные generation,
  tester/challenger и только штатный repair → terminal admission. При
  `can_start=true` — один явный start и readback той же первой AS с нулём
  оценочных ответов. При terminal отказе — сохранить причины/check IDs и
  остановиться без повторов ради PASS.
- Вход: профиль `assessment-first-case/1.1`, existing
  `scripts/assessment_first_case.py --program-source published-pilot` на
  отдельной owned-БД `product4k_pytest_<run_id>`. Рабочая БД, постоянные
  test/pilot БД и реальные данные участников не являются целью теста или cleanup.

Цепочка источника: Change 01 и task manifest → frozen программа/QA и
`m7_start_readiness/1` → PM-03 preparation/admission → PM-04 explicit start →
participant projection/readback → receipt и проверка zero answers. M1 v1.4
остаётся FROZEN/CURRENT=NO. Методология, prompts, admission/repair policy,
published definitions, схема и runtime не меняются этим планом.

## Бесплатный preflight и один разрешаемый запуск

1. На чистом execution checkout сверить `git status`, SHA/версию, exact
   published receipt1.2, source refs/checksums, provider contract/model и
   isolated PostgreSQL/Chromium/порт. Запустить `--preflight-only`, затем
   `--check-bootstrap` с exact selector; оба шага без LLM. Не печатать env,
   secrets, raw prompts или production/test PII.
2. До paid launch зафиксировать разрешённые provider/model, один сценарий,
   максимальные время и денежные затраты, а также способ их enforce. В
   существующем runner нет подтверждённого hard cap на суммарные provider
   tokens. Исторический PATH1.2 занял 376.5 s, 20 уникальных операций и
   сохранил usage 1 523 716 tokens; malformed JSON retry не включён в полный
   биллинговый итог. Эти числа — ориентир, **не гарантированный потолок**.
   Внешний `timeout` не заменяет лимит: он может оставить неизвестный исход
   уже отправленного запроса. До решения владельца paid launch не выполнять.
3. Если отдельный допуск получен, сделать ровно один runner invocation с
   `retries=0` на уровне browser/test. Внутренние transport retry и repair
   допускаются только по существующему frozen контракту; новых серий
   генерации или ручного повтора после отрицательного исхода нет.
4. До cleanup выгрузить safe primary receipts с fsync/readback: code/source/
   provider identities, operation IDs, check IDs, candidate/AS bindings,
   статусы, доступный usage и длительность, admission/start/zero answers
   либо точный отказ. При невозможности terminal export — сохранить owned
   состояние, не удалять БД. Иначе только штатный marker-guarded cleanup
   собственной БД и offline verification пакета.

Стоп-условия: drift SHA/receipt/program version; нездоровый isolated stand;
отсутствующий provider contract; mismatch scope/binding; превышение принятого
лимита; неизвестный transport outcome; terminal INCOMPLETE/FAIL/TECHNICAL_ERROR;
неподтверждённый export. Не ослаблять admission, не публиковать новую программу
и не показывать недопущенную AS. Отдельно сообщить (1) найден ли дефект
кода/контракта и (2) что реально подтвердил provider на выбранном SHA.

## Проверки, передача и откат

Для настоящего docs-only результата: `git diff --check`, ссылки и
согласованность с profile/receipt и пакетным запретом на неразрешённый LLM.
Исполнение LLM и HTTP/PG PATH здесь **NOT_RUN**. Визуальное решение принято
владельцем для PR #183 отдельно; этот план не воспроизводит его проверку.
CI PR обязателен перед merge документационного результата. После разрешённого
прогона отчёт и safe evidence — отдельный PR, не скрытый commit этого плана.
Откат плана — revert этого документа; runtime и опубликованные данные не
затронуты. Для будущего запуска откат — остановка только собственного
процесса и guarded cleanup только после доказанного export.

Флаги на момент подготовки плана: `branch_push=true`, `pr=true` (draft),
`merge=false`, `deploy=false`, `version_bump=false`,
`artifact_publish=false`, `llm=false`.
