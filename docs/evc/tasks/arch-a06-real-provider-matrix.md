# ARCH-A06 — расширенная real-provider матрица Case/function

## Результат

Получить воспроизводимые технические evidence реального DeepSeek для синтетической
матрицы 9 `CASE.SPEC` × 3 функции, не смешивая generation/tester/admission с
HTTP runtime, M6, M8, методологической приёмкой и Reliability.

## Область

- Включено: отдельный возобновляемый runner PM-03; package 0.3; синтетические
  профили Sales/HR/IT; безопасные provider trace; пилот одной строки перед серией.
- Не входит: production/персональные данные; общий test DB; изменение методологии,
  IndicatorIDs или исторических evidence; автоматическое повышение статуса M6/M8.

## Контекст

- Основание: пакет `P4K_Case_AS_Cycle_Plan_2026-10-23`, A06; явный допуск владельца
  на платные LLM-вызовы 25.10.2026 в текущем чате.
- База: `034280f947434117bd4a72fb1940e55a5fdacf0d`, приложение `2.0.25`.
- Контракт матрицы: `tests/fixtures/arch_a06/acceptance-matrix-v1.json`.
- PM/LU: PM-03 формирует и проверяет AS; PM-04 и последующие этапы считаются
  отдельными evidence.
- Предметный пакет: `m5-functional-personalization-cases` 0.3, draft; runner не
  публикует пакет и не изменяет его.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, обязательные EVC документы, Change 01,
  ADR-002, A06 fixture/manifest/tests, `task10-13-provider-contract.md`, PM-03
  generation service и существующий PERS runner.
- Provider identity: опубликованный контракт требует `deepseek-flash`; прежний
  `deepseek-chat` в test `.env` давал `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`.
- После исправления identity одиночный M6-вызов дошёл до ответа провайдера, но
  завершился `M6_CONTEXT_REFERENCE`. Поэтому M6/M8 не считаются проверенными.
- Стоп-условие: любой technical/provider failure, невалидная identity, несинтетический
  вход или попытка записи в репозиторий останавливают строку; независимые строки
  можно продолжать только отдельным явным запуском.
- Требуется решение владельца: нет для пилота и разрешённой матрицы; исправление M6
  является отдельной задачей и не выполняется автоматически.

## План и состояние

- Завершено: provider identity test-контура приведена к контракту с резервной
  копией; readiness PASS; ключ/сеть подтверждены ответом provider.
- Завершено: controlled tests PASS; real-provider пилот `A06.C01.SALES` технически
  завершился, но admission FAIL из-за `indicator_author_content_preserved`.
- Завершено: safe evidence и хэши сохранены в
  `docs/evc/evidence/arch-a06/real-provider-pilot-2026-10-25.json`; исходный raw
  evidence остаётся вне Git на test.
- Активный шаг: подготовить отдельный принимаемый PR runner/evidence.
- Следующий шаг: остальные 26 строк не запускать до отдельного исправления или
  принятого решения по воспроизведённой потере авторского содержания; HTTP/DB/M6/M8 только
  после отдельной локализации `M6_CONTEXT_REFERENCE` и в изолированной БД.
- Ветка: `codex/arch-a06-real-provider-matrix`.

## Ограничения и риски

- Совместимость: runtime/API не меняются.
- Данные: только синтетика; общий test DB не используется.
- Секреты: ключ читается только штатной конфигурацией и не попадает в output/log.
- LLM: один prepare может вызвать generation, tester, challenger и при дефекте один
  repair с повторным tester/challenger; стоимость и недетерминизм фиксируются trace.
- Статус: technical PASS не равен AI tester PASS, methodology PASS или Reliability.

## Критерии приёмки

- [ ] Runner принимает только 27 зарегистрированных синтетических строк и package 0.3.
- [ ] По умолчанию запускается не более одной строки; полный запуск требует `--all`.
- [ ] Результат пишется только во внешний каталог и возобновляется без перезаписи PASS.
- [ ] Controlled тест доказывает все 27 комбинаций без сети.
- [ ] Real-provider пилот сохраняет safe trace и честный раздельный статус.
- [ ] Исторические evidence и предметные пакеты не изменены.

## План проверки

- Unit: CLI/матрица/output guard; controlled generation/tester/admission 27 строк.
- Real provider: одна строка, затем серия только при успешном пилоте.
- HTTP/DB/M6/M8: NOT_RUN в этой фазе; M6 имеет воспроизводимый FAIL.
- CI: обязателен перед merge.

## Откат

Удалить runner/tests/task отдельным revert. На test вернуть сохранённый `.env` backup
и перезапустить сервис. Внешние evidence не удалять, а пометить superseded/failed.
