# SLS02 — Sales-предъявление и путь контекста

## Результат

Schema v3 Case материализует participant payload из выбранной авторской Sales AS,
а не из общей Case-проекции. Runtime сохраняет новый ID экземпляра AS, frozen
profile ref/checksum, точную версию предъявления, применённые подстановки и отдельный
execution payload. Чат показывает вводную, ситуацию, Trigger, роль, позиции сторон,
задачу, ограничения и стартовые материалы без выдачи закрытого author JSON.

## Область

- Включено: девять Sales presentation projection, ограниченный слот
  `organization_name`, latest-confirmation regression, совместимый presenter,
  unit/DB/browser проверки.
- Не входит: сценарные реакции и раскрытие последующих материалов SLS03,
  120-минутный план SLS04, содержательная приёмка SLS06, публикация draft-пакета.

## Контекст и прослеживаемость

- Основание: `P4K_Sales_02_Context_AS.txt`, редакция 2 от 19.10.2026; SLS01
  `m5-sales-pilot-cases/0.1`, author sources WORKING/TEST_DRAFT.
- База реализации: `origin/main@03c39df`; SLS01 уже merged.
- Прочитано: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, EVC workflow/matrix/
  artifact recipe, Change 01 README/manifest/traceability, Registry, ADR-002,
  `docs/architecture/m5-case-execution.md`, SLS01/SLS02 материалы комплекта.
- Источник → правило → контракт → код → проверка:
  author Sales AS + SHA-256 → открытые поля и стартовая видимость →
  `ParticipantPresentationV3` → builder/`build_assessment_situation` →
  `test_m5_sales_package.py` и Playwright E01;
  последнее подтверждение assignment → запрет fallback → `late_readiness` →
  реальный PostgreSQL integration test.
- Архитектурный адрес: PM-03 формирует immutable AS; PM-04 и C-45 читают её
  snapshot; M8 использует frozen profile snapshot. Предметные тексты остаются в
  versioned JSON, Python/JS содержит только проекцию и защитные правила.

## Решения и границы

- Schema v2 и исторические AS не меняются. Schema v3 получает совместимое поле
  `participant_presentation`; пакет 0.1 остаётся draft/runtime disabled.
- `organization_name` применяется только к объявленным source-backed paths и
  только когда profile usage rule не запрещает название. Неизвестный слот,
  пустое значение или запрещённая настройка останавливают подготовку до старта.
- P00 является вводной, остальные стартовые материалы выводятся отдельным списком.
  Для Case03 M04 остаётся закрытым до S3.
- Последняя неподвязанная confirmation даёт `W02_ANSWERS_NOT_BOUND`; более старый
  profile не выбирается.
- Стоп-условия EVC: несовместимой миграции, изменения методологии и допуска людям
  нет. Решение владельца для SLS02 не требуется.

## Критерии приёмки

- [x] Все девять preview имеют разные author AS ID/version/source checksum и
  точные стартовые материалы.
- [x] Разрешённая подстановка меняет только объявленное место; запрещённая
  отклоняется до создания AS.
- [x] Trigger и позиции сторон не теряются presenter-ом; reload не дублирует
  стартовое сообщение; узкий экран не создаёт горизонтальный overflow.
- [x] Более новая неподвязанная confirmation не откатывается к старому profile
  (изолированный PostgreSQL).
- [x] Schema v2 совместимость сохраняется, draft admission не расширен.
- [ ] Содержательный диалог, дальнейшие раскрытия и реальный LLM — SLS03/SLS06.

## Проверки

- `git diff --check` — PASS.
- `pytest tests/unit/test_m5_sales_package.py` — 8 PASS.
- полный backend unit-набор — 465 PASS; полный frontend-набор — 65 PASS.
- `TEST_DATABASE_URL=... pytest --run-integration -m integration tests/integration/test_w02_acquaintance_db.py`
  на временной `agent4k_pytest` — 2 PASS.
- `TEST_DATABASE_URL=... pytest --run-integration -m integration tests/integration/test_review_m4_confirmation_db.py tests/integration/test_m10_product_path_db.py`
  — 9 PASS: три ответа связываются идемпотентно, C-45 и M8 сохраняют тот же
  frozen profile snapshot, изменение последующего профиля не меняет историю.
- `playwright ... --grep "E01 renders accepted active assessment"` — 1 PASS.
- release candidate `2.0.2`, `check_release_version.py` — PASS.
- Полный backend/frontend набор и обязательный GitHub CI — перед merge.
- Опубликованный test и authenticated smoke — после merge/deploy-test.

## Откат и передача

Откатить код и не импортировать новую draft-версию пакета; уже созданные immutable
AS snapshots остаются читаемыми. `runtime_enabled=false` не меняется. SLS03 получает
`participant_presentation`, source refs, стартовую material boundary и execution
payload; сценарные rules остаются единственной следующей зависимостью.
