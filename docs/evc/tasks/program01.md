# PROGRAM01: программа оценки, назначения и достоверные статусы

## Основание и результат

- Пакет владельца: `P4K_PROGRAM01_2026-11-01.zip`, редакция 1.2.
- Проверенная база: `main` / `1abb9cf71212ed2be214bd74267daebd070f942b`, приложение 2.0.46.
- Результат: опубликованная программа однозначно подключается организации, администратор назначает точную оценку с ролью и source binding, участник получает эту роль и продолжает сохранённый путь; остаток ADM-STATUS закрывается по `STATUS_FIXES.txt`.

## Прочитанные источники

- `README.md`, `CONTRIBUTING.md`, `AGENTS.md`.
- `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`.
- `docs/architecture/product-4k/1.0/context.md`, `docs/architecture/product-4k/registry.md`.
- `docs/architecture/product-4k/1.0/updates/2026-10-01/README.md`.
- `docs/methodology/source-sets/2026-10-01/manifest.json`.
- `docs/adr/003-arch30-program-and-deletion-lifecycle.md`.
- Пакет: `START_ARCHITECT.txt`, `TASKS.txt`, `ACCEPTANCE.txt`, `FINDINGS.txt`, `SOURCE_MAP.txt`, `STATUS_FIXES.txt`, `status_review/RECHECK.txt`, `CHANGELOG.txt`, `PACKAGE_CHECKS.json`.
- Предметные источники: M3.RoleProfile v1.0, M3.BaseRoles v1.0, M4.Context v1.0, M5 v1.1; M6 v1.8, M7 v1.3 и M8 v1.2 только в относящихся к статусам границах.

## Принятые решения владельца

1. В форме назначения видны все шесть BaseRoles; в пилоте доступен только `specialist_expert`, остальные имеют пояснение «Недоступно в пилоте».
2. Интерфейсное имя новой версии программы: «Пилот 4К · 9 кейсов»; версия и доступная роль показываются отдельно.
3. Текущая работа включает PROGRAM01-01..04 и STATUS-R01..06; прочие замечания исходных DOCX не входят.
4. Published-определения и исторические bindings не изменяются; при необходимости имени выпускается новая совместимая ProgramDefinition.

## Границы

- Не менять M6/M7, таймеры, допуск кейсов, обязательный контекст или методологию ради разблокировки.
- Не создавать вторую систему программ, ролей, назначения или отмены.
- Не открывать пилоту другие роли и не публиковать RoleProfile только ради справочного списка.
- Не перепривязывать начатые Cycle и старые snapshots; legacy `assignment_id=NULL` не восстанавливать догадкой.
- Не выполнять `artifact_publish`, `version_bump`, merge или deploy без отдельного решения владельца.

## План

1. Зафиксировать сквозные идентичности и первый неуспешный переход: ProgramDefinition → connection → questionnaire assignment_ref/revision → assignment → binding → participant readiness.
2. Исправить подтверждение подключения, readback, идемпотентный исход и защиту от поздних ответов.
3. Добавить серверную проекцию BaseRoles/capabilities и явный выбор допустимой роли; сохранить совместимость единственной роли.
4. Исправить batch-назначение, системный assignment_ref, атомарный binding, повторное чтение и восстановленный bulk selection.
5. Исправить проекции/действия STATUS-R01..06, включая приглашения, revoke guards, свежесть, определённый исход отмены и доступные подтверждения.
6. Выполнить unit/frontend/HTTP/integration/browser проверки и заполнить AC01..16 плюс исходные 26 критериев статусов на окончательном SHA.
7. После отдельного допуска подготовить immutable ProgramDefinition, release/version, PR, CI и живую приёмку test.

## Стоп-условия

- Изменение смысла предметной сущности без решения: нет; решения даны пакетом и сообщением владельца.
- Несовместимое изменение API/БД без плана: нет; изменения должны быть добавочными и совместимыми.
- Миграция/удаление сохранённых данных: нет; запрещены границами.
- Нет источника предметного значения: нет для текущих BaseRoles/ProgramDefinition; конкретный конфликт фиксируется адресно.
- Новый контур артефакта: нет; используется существующий ProgramDefinition release-process.
- Новые права/чувствительные данные/граница deploy: нет.
- Откат: revert приложения; новая published ProgramDefinition при выпуске остаётся историей и может быть retired, старые связи не переписываются.

## Проверки

- `git diff --check`.
- `npm run lint:js`, `node --test tests/frontend/*.test.mjs`, `npm run build:web`.
- Backend unit/e2e без LLM.
- HTTP-контракты изменённых endpoints.
- Integration на изолированной БД с `test`/`pytest` в имени: атомарность, idempotency, race, lineage.
- Playwright: superadmin → org admin → participant; затронутые desktop/mobile состояния.
- Обязательный GitHub CI; после выпуска — deployed SHA/version и повтор live-сценария.

## Текущее состояние

- Ветка: `codex/program01`.
- База после rebase: `main@8fa2df75e2414066d9dac27fdb47e4a696f84bf1`.
- Кандидат приложения: `2.0.47`; подготовлен штатным `scripts/prepare_release.py`, release check PASS.
- Реализация: исправлены точный command/readback подключения программы, сохранение idempotency key при неопределённом исходе, защита от позднего ответа списка, строгий batch-контракт назначения, role-scoped fingerprint клиента, восстановление bulk selection, определённый исход отмены при сбое refresh, серверная capability-проекция шести BaseRoles, раздельные статусы письма/ссылки/регистрации и запрет отзыва использованного приглашения.
- Совместимость: `assessment_program.roles` сохранён как список допущенных runtime-ролей; добавлен `role_capabilities`. Published ProgramDefinition и исторические bindings не изменялись.
- Проверки: ESLint PASS; frontend `124/124 PASS`; backend unit/e2e `779 PASS`; целевые invitation/assignment HTTP `19 PASS`; integration PostgreSQL `36/36 PASS` (ProgramDefinition, cancellation/races, invitations, acquaintance); browser admin flow `3/3 PASS`; `npm run build:web` PASS; `git diff --check` PASS.
- Evidence: обновлены desktop/mobile snapshots `docs/evc/evidence/adm-status-01/`; визуально проверен desktop snapshot.
- После rebase повторены: ESLint PASS; адресная frontend-регрессия `3/3 PASS`; HTTP-регрессия `3/3 PASS`; release unit `5/5 PASS`; `npm run build:web` и `git diff --check` PASS. Ранее выполненный полный набор относится к неизменённому содержимому реализации на базе `1abb9cf`; обязательный CI проверит окончательный release SHA.
- Draft PR `#147`, head `fc8aa5b`: frontend и pytest PASS; full-verification — integration PASS, browser `88 PASS / 2 FAIL`. PATH29 ожидал прежний общий текст вместо нового точного batch-итога PROGRAM01. S10-C1 остался `active` за 120 секунд из-за фазовой гонки синтетического 30-секундного бюджета и 30-секундного polling completion worker.
- Регрессия CI исправлена без изменения production cadence: изолированный owned browser stand явно использует sweep 2 секунды, production и неявные окружения сохраняют 30 секунд; небезопасные значения отвергаются. PATH29 проверяет фактический batch-итог. Unit настройки worker `3 PASS`; совместный PATH29 + S10-C1 `2 PASS`; S10-C1 дополнительно `3/3 PASS` за 57.0–59.4 секунды.
- NOT_RUN: повтор полного browser suite и повторный обязательный CI нового head; live — до развёртывания кандидата.
- Владелец подтвердил выпускной пакет: новая immutable ProgramDefinition «Пилот 4К · 9 кейсов», patch `2.0.47`, branch push и Draft PR. Фактическая публикация ProgramDefinition выполняется штатной командой на `test` только после развёртывания поддерживающего SHA и readback точных опубликованных configuration/catalog/role; merge и deploy требуют отдельного подтверждения.
- Откат: revert будущего commit приложения; добавочная API-проекция совместима. Опубликованные определения не затронуты.
