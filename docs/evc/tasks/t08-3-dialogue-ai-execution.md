# T08.3 — Dialogue AI execution

## Основание и границы

- Запрос владельца от 2026-10-01: реализовать
  `Product_4K_Task_7_T08_3_Dialogue_AI_Execution_2026-10-01.txt`.
- Ветка: `codex/t08-3-dialogue-ai-execution`; база: `0096597` (`main`, версия `2.1.29`).
- Прочитаны: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, обязательные документы
  `docs/evc/*`, Product Architecture 1.0 + Change 01, M1 v1.4 и действующие M5 runtime,
  snapshot, gateway, HTTP и DB-тесты.
- Не входит: реализация методологии M6, принятие методологического IA, M7-формулирование
  уточнений, M8 и универсальный multi-provider engine.

## Обнаруженный пробел

M5 сохранял Dialogue/C-45 и имел версионированные prompts, но gateway выбирал model и
endpoint из текущих settings. Фактический запрос, provider metadata и попытки не входили
в AS trace. `final` C-45 допускался до закрытия AS. C-54 отсутствовал. M6 в репозитории
не реализован, поэтому для транспорта нужен явно технический QA-результат.
Связь M5 AS с Cycle/Session также отсутствует: QA C-45 явно передаёт `null`, а не
синтетические идентификаторы. Подключение реальных ссылок остаётся зависимостью M7.

## Реализация

- [x] AI-конфигурация входит в checksum-защищённый execution payload AS.
- [x] Gateway возвращает sent/provider trace без ключей и иных секретов.
- [x] M5 semantic/character adapters используют замороженные model/endpoint/parameters.
- [x] Попытки и решения сохраняются и читаются через основной trace.
- [x] C-45 содержит происхождение, фактическую доступность материалов и точную границу.
- [x] Разделены `interim` и `final` предусловия.
- [x] QA-only технический C-45/C-54 проходит основной adapter и не создаёт оценку.
- [x] Повтор действия идемпотентен; несовпадение identity и невалидный ответ отклоняются.

## Проверки

- `pytest -m 'not llm and not integration'` — 255 passed.
- `TEST_DATABASE_URL=postgresql://pytest:***@127.0.0.1:55433/agent4k_pytest npm run test:backend:integration`
  во временном `postgres:16-alpine` — 32 passed; контейнер удалён.
- `npm run lint:js` и `git diff --check` — PASS.
- Frozen config на границе gateway, provider trace, неизвестная revision, несовпадение
  model, prompt checksums, M5 runtime и HTTP покрыты тестами.
- Реальный локальный provider smoke: 3 passed; сетевой вызов выполнен через штатный
  `DeepSeekGateway`, методологическая корректность M6 не проверялась.
- Управляемый test transport через продуктовый QA HTTP и чтение DB/trace: выполнить после deploy.
- Реальный provider smoke на test: выполнить после deploy при доступной конфигурации.

## Риски и откат

Риск — рост объёма trace из-за сохранения request/response metadata. Секреты не входят в
trace. Миграция добавляет таблицы без удаления существующих данных. Откат — revert PR;
новые таблицы можно оставить неиспользуемыми до отдельного согласованного удаления.

## Change & Impact

Техническая версия C-54 подтверждает только транспорт и контракт. Для продуктового C-54
нужен M6: EB/IA, Fragment validation и содержательные правила. Продуктологу требуется
сохранить формулировку: «успешный технический C-54 не означает корректность оценивания».
