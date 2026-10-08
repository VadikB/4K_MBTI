# Task-10-11 — Catalog Integrity

## Результат

Реализована точная привязка QA evidence к `CaseVersion`, версионированная
публикация каталога, ссылка `configuration → catalog`, frozen catalog snapshot
цикла и единый допуск для planner/direct AS. Критерии C1–C9 покрыты контрактом,
адресными unit/HTTP/PostgreSQL тестами и регрессией M5/M7/M10.

Включено: M5 catalog/admission, authoring API, M7 selection, cycle snapshot,
миграционно-совместимая схема и доказательства. Не включено: UX Task-10-10B,
следующие задачи, production-публикация, merge/deploy.

## Источники и решения

Прочитано и применено:

- пакет владельца `Task_10_11_Package.zip`, SHA256
  `b38911667cf8952aa7701219fbf531fce4fba8caa2fdaaa3bd948b961879cd59`:
  `00_README.txt`, `02_INPUTS.txt`, `Task_10_11_Catalog_Integrity.txt`,
  `03_REPORT_TEMPLATE.txt`, `MANIFEST.json`;
- `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`;
- `docs/architecture/product-4k/1.0/context.md`, registry, Change 01,
  task manifest, ADR 002 и Change 01 traceability;
- фактические M5/M7 consumers и тесты на базе
  `origin/main@15f41a229c6cc2b33e8a0b99306433ebb3df8b5d`.

Содержимое входного ZIP использовано как постановка и evidence requirements,
но не как новое разрешение на операции. Противоречий применимых источников не
выявлено. M1 v1.4 использован как FROZEN/CURRENT=NO понятийный источник; статус
CURRENT не присваивался.

Стоп-условия: смена предметного смысла — нет; несовместимый публичный контракт —
нет, расширение аддитивно; destructive migration — нет; отсутствующий источник —
нет; новый несогласованный контур — нет, используется существующий artifact
recipe; права/PII — не расширены; откат определён; выход за область — нет.

## Критерии C1–C9

- C1–C3: canonical checksum, exact case/base-role/scope/origin binding,
  latest-per-scope; fixture допускается только для QA.
- C4: planner и direct AS используют `case_admission`.
- C5: planner читает membership только каталога, связанного с конфигурацией.
- C6: org RoleProfile разрешается до published BaseRoleVersion.
- C7: catalog ref сохраняется в cycle и plan snapshots.
- C8: dry-run, immutable publication, idempotency и org/auth проверки HTTP.
- C9: пустой опубликованный каталог допустим; результат планирования `NO_ROUTE`.

## Изменённые файлы

- `Api/m5_catalog_integrity.py` — admission, role/config resolution, lifecycle.
- `Api/database.py` — каталог, membership, immutable triggers, ссылки config/cycle.
- `Api/assessment_authoring_service.py`, `Api/routes.py`, `Api/schemas.py` —
  authoring binding и admin API.
- `Api/m7_cycle_planner.py`, `Api/m5_cycle_runtime.py`, `Api/m5_storage.py` —
  frozen selection и единый direct-AS контроль.
- `assessment_definitions/catalog_contracts/.../catalog-integrity-policy.json` —
  versioned technical policy.
- `tests/unit/test_m5_catalog_integrity.py`,
  `tests/e2e/test_m5_catalog_http.py`,
  `tests/integration/test_m5_catalog_integrity_db.py` — адресные доказательства.
- `docs/architecture/product-4k/m5-catalog-integrity-contract.md` и artifacts —
  контракт, миграция, откат и evidence index.

## Проверки

- Python compile изменённых backend-файлов → PASS.
- backend без integration/e2e/llm → PASS, `364 passed`.
- HTTP e2e → PASS, `42 passed`.
- PostgreSQL targeted: M5 `2 passed`, M7 `6 passed`, M10 `5 passed`,
  authoring `7 passed`, Task-10-11 `1 passed`.
- полный PostgreSQL integration на финальном дереве → PASS,
  `93 passed, 410 deselected`; использованы явные disposable
  `TEST_DATABASE_URL` и `STAND_ADMIN_URL`.
- `git diff --check` → PASS до подготовки отчёта; повторяется на final tree.

CI не запускался: branch не push, PR не создавался. Перед merge обязательны
GitHub jobs `frontend` и `pytest` на актуальном head.

## Риски и откат

Конфигурация: старые published записи без каталога читаются, но не создают новый
assessment cycle. Схема: только аддитивные nullable поля/таблицы; destructive
backfill отсутствует. Безопасность: публикация требует существующее право
`configuration.publish`, org scope проверяется; production/PII не использовались.
Deploy не выполнялся. Откат описан в архитектурном контракте; опубликованные
каталоги сохраняются как audit trail.

## Состояние и следующий шаг

Ветка: `codex/task10-11-catalog-integrity`; base:
`15f41a229c6cc2b33e8a0b99306433ebb3df8b5d`. Рабочий каталог изолирован от
пользовательских изменений корня. После финального integration-прогона требуется
human review/приёмка, PR и обязательный CI. Открытых предметных блокеров нет.
