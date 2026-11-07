# FIX-RETURN-01: поздний heartbeat после Continue

## Результат

После успешного возврата к сохранённой Assessment Situation первый heartbeat не
пытается закрыть новый `collecting` старой границей presence lease и не возвращает
HTTP 500.

## Область

- Включено: M7 return-presence, сброс lease предыдущей эпохи, защита временного
  интервала, интеграционная регрессия воспроизведённой гонки.
- Не входит: изменение UI/API/схемы, исправление данных test, release/deploy.

## Контекст

- Основание: запрос владельца от 07.11.2026 и traceback test Cycle
  `9f9df3e8-06f8-4f27-96df-64a28dbf38e8`.
- Архитектура: PM-04; `docs/architecture/m7-return-time-integration.md`,
  `docs/architecture/m7-completion-contract.md`, ADR-002.
- Правило: успешный Continue закрывает `blocking_system_wait` и возобновляет
  `collecting`; поздний heartbeat не переносит серверную границу назад.
- Реализация: `Api/m7_return_integration.py`.
- Проверка: `tests/integration/test_m7_cycle_planner_db.py`.

## Источники и решения

- Прочитано на base `b04b7f0a`: `README.md`, `CONTRIBUTING.md`, AGENTS.md,
  workflow/matrix/artifact recipe/review checklist, Change 01, SourceSet manifest,
  Registry/context, ADR-002 и M7 return/completion/replacement contracts.
- M7 v1.3 FROZEN выбран SourceSet; runtime-интеграция остаётся draft QA. Новая
  предметная норма и новый артефакт не вводятся.
- Стоп-условий нет: исправляется воспроизведённое нарушение существующего
  временного инварианта, API и данные обратно совместимы.

## План и состояние

- Завершено: диагностика test, изоляция worktree, код, unit-регрессия и полный
  быстрый backend/HTTP-набор.
- Активный шаг: итоговый review и commit.
- Следующий шаг: после завершения параллельного обновления подготовить release/PR,
  затем отдельно восстановить test Cycle на уже исправленной версии.
- Ветка: `codex/fix-return-heartbeat-race`, base `b04b7f0a`.

## Действия выпуска

- `branch_push=false`, `pr=false`, `merge=false`, `deploy=false`.
- `version_bump=false`, `artifact_publish=false`.

## Ограничения и риски

- Совместимость: API/схема не меняются; старые Cycle читаются прежним кодом.
- Данные: удаляются только активные presence lease текущего Cycle внутри успешной
  транзакции Continue; они являются краткоживущим сигналом связи, не Evidence.
- Безопасность: авторизация и owner-check не меняются; PII не добавляется.
- Откат: revert кода и теста; миграция/обратное преобразование данных не нужны.

## Критерии приёмки

- [x] Continue с истёкшим lease возобновляет тот же AS — покрыто существующей
  integration-регрессией, дополненной проверкой сброса lease.
- [x] Немедленный heartbeat после Continue не создаёт новое событие отсутствия —
  адресный integration PASS на изолированной PostgreSQL.
- [x] Старый lease не может записать `ended_at < started_at` — unit PASS.
- [x] Адресная M7 integration-регрессия проходит на изолированной PostgreSQL.
- [x] Backend и HTTP-наборы проходят.

## План проверки

- Адресный integration на отдельной БД с `test`/`pytest` в имени.
- `npm run test:backend`, `git diff --check`.
- Полный CI перед merge; test/deploy и восстановление Cycle — отдельный шаг.

## Проверки

- Python compile изменённых файлов — PASS.
- `pytest -q tests/unit/test_m7_return_integration.py` — 3 PASS.
- backend `not integration and not e2e and not llm` — 937 PASS.
- HTTP/e2e — 108 PASS.
- `git diff --check` — PASS.
- адресный integration — 1 PASS / 30 deselected на одноразовой PostgreSQL 16,
  БД `return_heartbeat_pytest`; контейнер после проверки удалён.
- полный M7 integration-файл запускался дополнительно, но итоговая строка runner
  не была сохранена инструментом; этот прогон не используется как доказательство.
- `origin/main` после повторного fetch остаётся `b04b7f0a`; параллельное изменение
  не появилось в main на момент проверки.
