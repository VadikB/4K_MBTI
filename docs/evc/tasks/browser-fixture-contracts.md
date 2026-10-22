# Browser fixture contracts: явная маршрутизация M7

## Результат

Synthetic browser gateway выбирает ожидаемое уточнение M7 по сохранённому
`case_ref`, а не угадывает сценарий по составу `indicator_ids`. Для обычного и
character-сценария зафиксированы отдельные технические fixture-контракты.

## Область

- Включено: isolated browser acceptance gateway, JSON fixtures, unit-регрессия.
- Не входит: production/test runtime, методология, GC, публичный API, схема БД,
  содержательная оценка ответов и опубликованные пакеты.

## Контекст и источники

- Основание: поручение владельца в текущем чате 22.10.2026 после расхождения
  двух CI-запусков одного commit в S10-A.
- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, рабочий цикл, матрица
  проверок, рецепт артефактов, review checklist, Change 01 README и task manifest,
  `tests/browser/README.md`, `Api/m10_test_gateway.py`, M7 clarification runtime и
  browser fixtures/tests.
- Применимый источник: Change 01, M7 v1.3 FROZEN; изменение не вводит предметных
  норм и не меняет runtime publication.
- Связь: synthetic case snapshot `case_ref` → fixture contract → test gateway →
  unit и browser S10-A.
- Стоп-условия: отсутствуют; новый формат ограничен тестовым контуром и не является
  предметным артефактом.

## Критерии приёмки

- [x] Обычный и character-сценарии имеют отдельные fixture-контракты с входом,
  actions, ожидаемым вопросом и статусом M7.
- [x] Выбор контракта выполняется по `case_ref.id`.
- [x] Неизвестный case и отсутствие обязательного indicator завершаются явной
  диагностической ошибкой без текстового fallback.
- [x] Адресные unit-проверки проходят; S10-A подтвердил fixture-ветку, но полный
  browser-набор остаётся нестабилен из-за отдельной orchestration/DB-lock гонки.
- [ ] Обязательный CI актуального head проходит.

## Проверки

- `git diff --check`;
- `python -m py_compile Api/m10_test_gateway.py`;
- `pytest tests/unit/test_m10_test_gateway.py`;
- browser S10-A на owned isolated `product4k_pytest_*`;
- backend-набор и обязательный GitHub CI.

Фактически: unit 4 PASS; backend без integration/e2e/llm 489 PASS; character
S10-A 1 PASS и повторно 3/3 PASS; оба S10-A совместно 2 PASS. Первый полный
browser-прогон: 13 PASS, REV-02 FAIL из-за PostgreSQL deadlock между background
worker и UI heartbeat. Эксперимент с общим `drain` в `report()` подтвердил, что
расширять синхронизацию на все сценарии нельзя: он удалён, поскольку создавал новые
гонки P10.5/G10.7. Финальный адресный прогон после удаления эксперимента: unit
4 PASS; два S10-A FAIL — основной остался на mandatory update до M7, character
дошёл до M7, но Report остался `not_ready` после зафиксированного DB deadlock.
Исправление runtime lock ordering и детерминированного завершения scenario transition
не входит в эту задачу; результат нельзя объявлять полной стабилизацией browser suite.

После первого CI для PR #93 подготовлен PATCH-кандидат `2.0.14`: release check
PASS, `npm run build:web` PASS, `npm run lint:js` PASS, frontend 66 PASS и unit
gateway 4 PASS. Frontend-регрессия cache-busting теперь сверяется с текущим
`APP_RELEASE`, а не с прежним номером версии.

## Риски и откат

Изменение действует только при guarded `AGENT4K_BROWSER_TEST_GATEWAY=1` на owned
isolated stand. Откат — revert PR; миграций и преобразования данных нет.
