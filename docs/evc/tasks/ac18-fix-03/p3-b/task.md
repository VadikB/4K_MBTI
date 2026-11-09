# AC18 FIX-03 / P3-B: прогресс, время и возврат

Дата: 09.11.2026. Исполнитель: Codex архитектора.

## Результат и границы

Привести проекции сохранённого плана, серверного остатка времени и явного Continue
к существующему M7-контракту. Сохранить FIX-RETURN-01 и пилотный R1 v2: та же AS,
явный Continue, без replacement. P3-A, итоговая P3-I, новая методология, схема БД,
CI/gates и рабочие данные не входят.

## Источники

- base `023bf85ec796d212d29b33218d906a1ed2023941`,
  исходный APP_RELEASE `2.0.86`, локальный PATCH-кандидат `2.0.87`;
- пакет `P4K_P3B_Architect_2026-11-09`, SHA256 всех файлов — PASS;
- `README.md`, `CONTRIBUTING.md`, `AGENTS.md`;
- `docs/evc/{agent-workflow,verification-matrix,artifact-recipe,review-checklist}.md`;
- Product 4K context/Registry, Change 01, manifest, ADR-002 и traceability;
- `docs/architecture/m7-return-time-integration.md`, M7 v1.3 адресные разделы;
- `docs/evc/tasks/fix-return-heartbeat-race.md`;
- `assessment_definitions/planning/m7_return_integration/v2/policy.json`.

Пробел: доступный согласованный канал передачи checkpoint исполнителю P3-A в этой
сессии не определён. Checkpoint сохранён в `STATE.md`; внешняя отправка остаётся
отдельным действием. Противоречий, требующих новой предметной нормы, не выявлено.

## Решение и стоп-условия

Публичная схема, API-поля и БД не меняются. Исправляются проекции существующих
saved plan/route/timing и повтор команды с тем же idempotency key. Все стоп-условия
рабочего цикла — нет. Откат: revert продуктового diff и пересборка `web/dist` на
этапе кандидата; миграция и восстановление данных не требуются.

## Проверки

Адресные frontend/unit, M7 owned PostgreSQL integration, HTTP/browser P03,
frontend build, backend minimum и `git diff --check`. Полный CI — только точного
release-кандидата перед merge. Реальные LLM/письма и рабочая БД не используются.

## Полномочия

Ответ владельца «следующий patch» разрешил локальный `version_bump` до `2.0.87`.
`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`artifact_publish=false` до отдельного прямого допуска.
