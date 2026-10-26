# ARCH-A01/A06 — двухслойный IndicatorTarget

## Основание и результат

- Решение владельца от 26.10.2026: авторский источник неизменяем, а условия
  конкретной AS разрешено адаптировать к профессиональному контексту при
  сохранении смысла, наблюдаемости и ограничений.
- Base: test `2.0.27`, commit
  `97400d2ee17fb2f8f66205561846075e7a2c046a`.
- Воспроизведение: `A06.C01.SALES`; generation и сохранность источника PASS,
  AI tester/admission FAIL из-за смешения авторского и исполняемого слоёв.
- Независимый результат: контракт, compiler и PM-03 hand-off. Исправление
  `M6_CONTEXT_REFERENCE` выполняется другой задачей и не смешивается с этим PR.

## Прочитанные источники и границы

Прочитаны `README.md`, `CONTRIBUTING.md`, EVC workflow/matrix/artifact recipe,
архитектурные context/Registry, Change 01, SourceSet `2026-10-01`, ADR-002,
карточки ARCH-A01/A06, package `0.3`, PM-03 generation/tester, PM-04 compiler,
persistence trace и M6 input resolver.

Не меняются IndicatorID, M2, дескрипторы, достаточность, агрегация,
исторические AS/FROZEN/evidence и пакеты `0.2`/`0.3`. Остальные 26 строк A06 и
четыре RECHECK не запускаются до успешного повторного пилота.

## Контракт

Новый draft package `m5-functional-personalization-cases/0.4`, compiler
`m5-functional-json-compiler/0.4.0` и контракт
`m5-functional-indicator-two-layer/1.0.0` задают:

1. `author` — точная копия `IndicatorObservability` frozen source, source ref,
   версия и canonical SHA-256;
2. `adapted` — проекция той же совокупности IndicatorID для одной AS, версия,
   checksum, условия и явные ссылки на материалы, события, персонажей,
   полномочия и конкретный авторский target;
3. deterministic fail-closed validation целостности, множества целей, хэшей и
   ссылок; independent tester/challenger проверяют сохранение смысла,
   наблюдаемости, ограничений и согласованность с профессиональной AS;
4. принятая AS и persistence trace фиксируют оба слоя; compiler берёт
   исполняемые условия из adapted, добавляя `author_basis`; M6 получает тот же
   target без повторного преобразования;
5. participant projection не содержит execution payload, trace или закрытые
   IndicatorTarget layers.

## Стоп-условия и откат

- Любая потеря условия, неизвестная ссылка/полномочие, несовпавший checksum или
  смысловая подмена блокируют admission; сервер не синтезирует отсутствующее
  соответствие.
- Методологическая неоднозначность адресуется методологу; код не вводит новую
  предметную норму.
- Откат: не выбирать package `0.4` для новых Cycle и revert изменения default
  dependency. Исторические snapshot продолжают ссылаться на свои версии.

## Проверки и статусы

- Package build `0.4`: PASS, 9 Case / 9 AS / 55 targets; package checksum
  `dcb71bf9b2a772c33d3446ef5a0cadcf567497afd966f833926d20e59384a61b`.
- CI push для первого commit `6b8e05e`: integration FAIL из-за изменения
  checksum девяти прежних CaseVersion при добавлении новых полей в статический
  package `0.4`. Исправлено: статические Case побайтно-канонически совпадают с
  package `0.3`, новый авторский basis и адаптированные условия добавляются
  только при компиляции конкретной AS; runtime bindings `1.1.0` вновь проходят
  строгую проверку. Регрессия проверяет все девять Case checksum и bindings.
- CI push/pull_request для `7573376`: integration FAIL при импорте Case в БД:
  `model_dump()` добавлял отсутствующие optional поля как `null`, вследствие
  чего `M5_RUNTIME_RULE_CASE_NOT_IMPORTED` срабатывал на старом CaseVersion.
  Импорт сохраняет только поля, присутствовавшие в валидированном Case;
  регрессия проверяет checksum после сериализации.
- CI push/pull_request для `567ef8a`: integration FAIL в `_as_row` с
  `SNAPSHOT_COMPOSITION_MISMATCH`: runtime признавал функциональную трассу
  только schema 2. Исправлено признание schema 3 при строгой проверке
  `IndicatorTargetLayers` в trace и accepted AS, checksum слоёв,
  compiled Case и frozen source CaseVersion. Адресная регрессия: 4 passed,
  включая отклонение подмены слоёв, checksum и исходной Case-ссылки.
- CI push/pull_request для `57ac148`: integration FAIL в той же композиции.
  Точная причина: `IndicatorTargetLayers` хэшируется генератором canonical JSON
  без завершающего LF, а новая проверка `_as_row` использовала runtime canonical
  JSON с LF. Исправлена только проверка checksum слоёв: она теперь использует
  алгоритм функционального контракта; checksum полного AS и CaseVersion остаются
  на прежнем runtime-алгоритме. Регрессия явно фиксирует различие алгоритмов.
- CI pull_request для `beb0063`: M10 и остальные generated-AS integration
  проходят; остаются F05 и два static-Case runtime теста. В статическом пути
  `build_assessment_situation` хэшировал `CaseVersionV3.model_dump()` с
  добавленными optional/default полями, тогда как импортированный immutable
  CaseVersion сохраняет исходный JSON. `case_ref.checksum` теперь вычисляется
  по исходному валидированному `case_value`; regression подтверждает точное
  совпадение со stored content checksum, сохраняя строгую runtime-проверку.
- Положительная корректная адаптация и hand-off `0.4`: PASS; frozen package
  `0.3` сохраняет legacy trace schema 2: PASS.
- Отрицательные потеря условия, подмена смысла, неверный material ref,
  authority ref и source mapping: PASS (отклоняются).
- Backend без integration/e2e/llm после исправления CI: 584 passed,
  230 deselected.
- HTTP/e2e, включая B01/B02 safe projection и owner/reused-key: 69 passed,
  11 deselected.
- Unit после изменений: 570 passed; адресный двухслойный набор: 31 passed.
- Frontend build, ESLint, npm audit: PASS; `0 vulnerabilities`.
- Browser без изолированного stand: 48 passed; 14 runtime tests NOT_RUN из-за
  обязательного отсутствующего `STAND_ADMIN_URL`, а не дефекта продукта.
- DB integration локально NOT_RUN: Docker daemon недоступен; обязателен CI.
- Release candidate: `2.0.28`; `git diff --check` и Python compile: PASS.
- Real-provider: сначала только `A06.C01.SALES`; матрица — лишь после admission.
- Technical PASS, AI tester, methodology acceptance, publication и Reliability
  фиксируются раздельно.
