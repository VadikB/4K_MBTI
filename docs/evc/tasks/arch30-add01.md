# ARCH30-ADD01 — девять кейсов, подключение и адресная приёмка

## Основание и результат

- Запрос владельца: выполнить `P4K_ARCH30_ADD01_START.txt` и пакет
  `P4K_ARCH30_ADD01_2026-10-30.zip` как ограниченное продолжение слитого ARCH30.
- Base: `main@6cde53b238def742114b3eef2958ddb3da52bcc2`.
- Ветка: `codex/arch30-add01`.
- Целевой результат: проследить `CASE.SPEC.01–09`, устранить технический разрыв
  поставки и назначения, проверить delta D03–D05 и предъявить D01–D06 без
  повторного широкого аудита и без удаления рабочих данных.

## Прочитанные источники

- `README.md`, `CONTRIBUTING.md`, `AGENTS.md`.
- `docs/evc/agent-workflow.md`, `verification-matrix.md`,
  `artifact-recipe.md`, `change01-traceability.md`.
- `docs/architecture/product-4k/1.0/context.md`, `registry.md`, Change 01 и
  `docs/methodology/source-sets/2026-10-01/manifest.json`.
- `docs/adr/002-cycle-as-dialogue-contracts.md`,
  `docs/adr/003-arch30-program-and-deletion-lifecycle.md`.
- `docs/evc/tasks/arch30.md`, `docs/evc/reports/pers-functional-personalization.md`,
  `docs/evc/evidence/case-cycle-r1-2026-10-26.md`.
- Все D01–D06, acceptance и source notes из ADD01 package.
- `assessment_definitions/cases/competencies_4k/functional-personalization/0.5`,
  runtime `1.2.0`, catalog integrity contract и затронутый код/тесты.

## Разведка и границы

- Нужный набор — `m5-functional-personalization-cases@0.5`, девять
  `CASE.SPEC.01–09`, BaseRole `specialist_expert`. `CASE-TDISC-*` не является
  этим набором.
- Case package остаётся `draft`, Case — `WORKING`, runtime package — `draft`,
  `runtime_enabled=false`; static verification PASS, но
  `methodology_admission=NOT_RUN`. Первая разорванная связь — содержательный
  admission до публикации assessment catalog.
- ProgramDefinition, UI подключения, точные role/config/catalog refs, transfer и
  purge уже находятся в `main`; они не реализуются повторно.
- Не выполняются production/test destructive операции, реальные письма и LLM.
  Test-публикация возможна только после применимого admission и release gate.

## Стоп-условия

- Смысл сущности/оценки без решения: **нет**; владелец подтвердил существующие
  девять Case и роль «Специалист».
- Публичный контракт/схема без совместимости: **нет** для аддитивной реализации;
  несовместимое изменение запрещено.
- Миграция/удаление данных без допуска: **нет**; рабочие данные не меняются.
- Нет применимого предметного источника: **да только для фактической публикации** —
  package сам фиксирует `methodology_admission=NOT_RUN`. Это блокирует
  `artifact_publish` и live D06, но не технический release-контур и регрессии.
- Новый формат артефакта: **нет**; используются существующие package/catalog/
  ProgramDefinition contracts.
- Права/граница deploy без допуска: **нет** для локальной реализации;
  публикация и deploy остаются отдельными release-действиями.
- Откат: новые immutable версии и подключения не удаляются; до публикации — revert
  кода, после публикации — переключение на прежнюю published configuration/program.

## План

1. D01: сформировать машинно проверяемый реестр девяти Case и release plan,
   который fail-closed отличает static verification от assessment admission.
2. D02: сделать атомарное создание/доведение assignment source bindings с
   идемпотентным readback; добавить точные причины readiness.
3. D03–D05: сопоставить ADD01 с кодом и тестами, исправить только доказанные delta.
4. D06: выполнить first-save/confirm regressions и product-path integration до
   границы, не подменяя live publication fixture.
5. Обновить таблицу D01–D06, выполнить применимый минимум матрицы и review.

## Проверки и передача состояния

- Реализовано:
  - D01: `scripts/plan_specialist_program_release.py` проверяет package/runtime,
    формирует реестр `CASE.SPEC.01–09` с версиями и checksum и готовит
    идемпотентный DB import/readback; assessment publication остаётся fail-closed.
  - D02: существующая транзакция назначения повторно вызывает immutable `bind()`
    и штатно доводит пригодное незапущенное назначение без source binding;
    регрессия фиксирует этот readback.
  - D03: повторно использованы реализованные в ARCH30 capability/navigation,
    scoped draft и logout regressions; новых расхождений ADD01 не найдено.
  - D04: снятие member relationship возвращает `removed`/`already_absent` и
    сохраняет отдельную audit-запись с actor/target/org/result/affected rows.
  - D05: административные email/ФИО/должность обязательны в UI/API/import;
    desktop geometry формы приведена к измерениям ADD01 без изменения mobile.
  - D06: first save/confirm и product path повторно проверены до честного отказа
    подготовки на недопущенном каталоге.
- Обязательный минимум: `git diff --check`, package verify/checksum, затронутые
  unit/frontend/HTTP, backend, isolated PostgreSQL integration, `npm run lint:js`,
  `npm run build:web`; browser — для изменённого UI.
- Реальные LLM, рабочая БД и удаление рабочих организаций/аккаунтов запрещены.
- Результаты:
  - PASS — release trace: девять точных Case, BaseRole `specialist_expert`, Sales
    только профессиональный пример; package checksum
    `4c127cbb8ed3573885cccdadfc9ae8199b6f266bd3f8077644b45a3d7c8e486c`.
  - BLOCKED — D01 publication/D06 live first Case: package `draft`, Case
    `WORKING`, `runtime_enabled=false`, `methodology_admission=NOT_RUN`.
  - PASS — `11` ARCH30/ADD01 frontend tests.
  - PASS — `13` затронутых HTTP tests; отдельный ранний набор — `11` PASS.
  - PASS — backend, кроме integration/e2e/llm: `672 passed, 275 deselected`.
  - PASS — isolated PostgreSQL: path29, membership race, transfer: `5 passed`.
  - PASS — JS lint для изменённого `organizations.js`.
  - FAIL (baseline, вне diff) — полный JS lint: `32` уже существующих
    `no-unused-vars` в methodology/prompt-lab/report-detail/reports.
  - PASS — эквивалентный production esbuild bundle в `/tmp`; запись в
    `web/dist` managed worktree заблокирована `EPERM`, CI build остаётся
    обязательным перед слиянием.
  - PASS — `git diff --check`.

## Матрица ADD01

| Проверка | Результат | Доказательство / граница |
|---|---|---|
| Q01 | PASS | Машинный реестр package/runtime/Case/source hashes. |
| Q02 | BLOCKED | Import plan готов; предметный admission отсутствует, публикации нет. |
| Q03 | BLOCKED | UI подключения опубликованной ProgramDefinition есть; реального допустимого каталога D01 нет. |
| Q04 | PASS | Повтор/operation fingerprint/полный `bind()` проверены HTTP. |
| Q05 | PASS | Пригодный active incomplete assignment доводится через immutable `bind()`; frozen отклоняется контрактом. Рабочие №6–8 не изменялись. |
| Q06 | PASS | Ограничение ролей принадлежит ProgramDefinition; глобального specialist-only валидатора нет. |
| Q07–Q09 | PASS | Переиспользованы ARCH30 navigation/draft/logout regressions. |
| Q10 | PASS | 409, tenant hiding, retry/race покрыты HTTP и PostgreSQL. |
| Q11 | PASS | HTTP `removed`/`already_absent` и durable audit с affected rows. |
| Q12–Q14 | PASS | Переиспользован реализованный ARCH30 purge/entitlement набор; новых изменений кроме Q11 нет. |
| Q15 | PASS / NOT_RUN | CSS/автотест PASS; визуальная приёмка владельцем NOT_RUN. |
| Q16 | PASS | UI/API/CSV required и read-only member stage regressions. |
| Q17 | PASS | Save/confirm/readback и confirmed-vs-preview HTTP/product-path regressions. |
| Q18 | BLOCKED | Product path до подготовки PASS; первый Case блокируется `ASSESSMENT_CATALOG_NO_ADMISSIBLE_SPECIALIST_CASE`. |

Итоговый SHA появится после commit. Публикация, test deploy и приёмка владельцем
не подменяются локальными проверками.
