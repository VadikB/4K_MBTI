# OPS: полное удаление тестовой организации

## Результат

Суперадминистратор может сначала получить безопасный план, а затем одной
транзакцией физически удалить тестовую организацию и все связанные с ней данные.

## Область

- Включено: отдельный CLI; test/pytest guard; dry-run; точное подтверждение кода;
  удаление прямых и FK-зависимых данных; legacy assessment-сессии участников;
  проверка результата; rollback при ошибке.
- Не входит: UI/API-кнопка, production/pilot, автоматическое удаление пользователей,
  изменение штатной деактивации организации.

## Контекст

- Основание: решение владельца в чате 2026-10-29 — тестовые организации можно
  физически удалять вместе со всей assessment-историей и snapshots.
- Значимые точки входа: `Api/routes.py` (штатная деактивация/удаление),
  `Api/database.py` (FK и immutable triggers), `scripts/purge_test_organization.py`.
- Архитектурный адрес: эксплуатационная операция над данными PM-02–PM-07; не
  меняет предметные контракты и runtime-поведение.
- Открытое решение закрыто владельцем: уничтожение связанных неизменяемых данных
  допустимо только для явно выбранной тестовой организации.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  `docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`,
  `task-template.md`, `review-checklist.md`, архитектурный context/Registry,
  Change 01 README и task manifest, относящиеся схемы/маршруты/тесты.
- Применимый комплект: Product 4K 1.0 + Change 01 WORKING; M1 v1.4 FROZEN,
  CURRENT=NO. Предметные нормы не изменяются.
- Пробел: отдельного migration/playbook полного удаления организации нет.
- Стоп-условия: несовместимое уничтожение истории явно разрешено владельцем для
  test; production/pilot запрещены guard-условием; секреты и реальные данные не
  читаются и не выводятся.
- Требуется решение владельца: нет.

## План и состояние

- Завершено: разведка; решение владельца; CLI; unit и адресная integration
  на одноразовой PostgreSQL 16 pytest-БД.
- Активный шаг: передача результата владельцу.
- Следующий шаг: review/PR, CI и dry-run на test для выбранной организации.
- Ветка / base commit: `codex/superadmin-organization-purge` /
  `2f930bb9ee10c6acde7ebf50dc8d36462f642c90`; PR ещё не создан.

## Ограничения и риски

- Совместимость: штатный API не меняется.
- Данные: операция необратима после commit; перед execute обязателен идентификатор
  backup/snapshot. Пользовательские аккаунты сохраняются.
- Безопасность: допускаются только БД с `test`/`pytest` в имени; выводятся только
  идентификатор организации и агрегированные количества строк.
- Эксплуатация: на время транзакции берётся advisory lock; новые таблицы с
  `organization_id` и FK-зависимости обнаруживаются через PostgreSQL catalog.

## Критерии приёмки

- [x] Без `--execute` данные не изменяются и выводится план по таблицам.
- [x] Execute невозможен вне test/pytest, без backup reference или без точного кода.
- [x] Связанные строки, включая защищённые immutable trigger, удаляются в одной
  транзакции; при сбое сохраняется исходное состояние.
- [x] Несвязанная организация и пользовательские аккаунты сохраняются.
- [x] После commit отсутствуют организация и строки с её `organization_id`.

## План проверки

- `git diff --check`.
- Unit: guard/аргументы и чистые функции.
- Integration: отдельная pytest-БД, изолированная schema, прямые/косвенные FK,
  immutable user trigger, legacy session, rollback/dry-run.
- Полный backend-набор и обязательный CI перед слиянием.

Фактические проверки 2026-10-29:

- `tests/unit/test_purge_test_organization.py`: `3 passed`.
- адресная integration на PostgreSQL 16: `2 passed`.
- end-to-end на полной актуальной схеме и синтетическом seed:
  dry-run нашёл 19 связанных строк в 11 таблицах; execute удалил их одной
  транзакцией; организация отсутствует, все 3 пользовательских аккаунта сохранены.
- test 2026-10-29, commit стенда `2f930bb9ee10c6acde7ebf50dc8d36462f642c90`:
  для `organization_id=2`, `code=lidum_pro` dry-run и execute удалили 45 строк
  в 15 таблицах; после commit `organization_rows=0`, `direct_references=0`,
  `membership_rows=0`, `users_total=11`; `agent4k-test.service=active`,
  `GET /users/version=200`. Проверенный backup:
  `/home/vadim_bogachev/projects/Agent4K-Test/.test-stand/backups/before-org-purge-lidum-pro-20261029-actual-db.dump`
  (`pg_restore --list` PASS, mode `600`).
- `npm run test:backend`: `442 passed`, `13 failed`; падения находятся в ранее
  существующих M6 admission/evidence/indicator tests и не затрагивают purge-код.
  До PR/слияния требуется исправный полный набор и обязательный CI.

## Откат

До commit — автоматический rollback. После commit — восстановление выбранной
организации из указанного backup/snapshot; удаление кода CLI обычным revert не
восстанавливает данные.
