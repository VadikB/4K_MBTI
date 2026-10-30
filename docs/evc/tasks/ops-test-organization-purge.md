# OPS: полное удаление тестовой организации

## Результат

Суперадминистратор может сначала получить безопасный план, а затем одной
транзакцией физически удалить тестовую организацию и все связанные с ней данные.

## Область

- Включено: отдельный CLI; test/pytest guard; dry-run; точное подтверждение кода;
  удаление прямых и FK-зависимых данных; legacy assessment-сессии участников;
  удаление аккаунтов, identities, credentials и сессий пользователей, которые после
  purge не состоят ни в одной организации; проверка результата; rollback при ошибке.
- Не входит: UI/API-кнопка, production/pilot, удаление аккаунтов участников других
  организаций, изменение штатной деактивации организации.

## Контекст

- Основание: решение владельца в чате 2026-10-29 — тестовые организации можно
  физически удалять вместе со всей assessment-историей и snapshots.
- Значимые точки входа: `Api/routes.py` (штатная деактивация/удаление),
  `Api/database.py` (FK и immutable triggers), `scripts/purge_test_organization.py`.
- Архитектурный адрес: эксплуатационная операция над данными PM-02–PM-07; не
  меняет предметные контракты и runtime-поведение.
- Открытое решение закрыто владельцем: уничтожение связанных неизменяемых данных
  допустимо только для явно выбранной тестовой организации.
- Расширение решения владельцем 2026-10-30: вместе с тестовой организацией требуется
  уничтожать все следы аккаунтов, не состоящих больше ни в одной организации;
  shared-аккаунты и их глобальные данные сохраняются.

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
  backup/snapshot. Orphan-аккаунты удаляются; аккаунты с membership в другой
  организации сохраняются.
- Безопасность: допускаются только БД с `test`/`pytest` в имени; выводятся только
  идентификатор организации и агрегированные количества строк.
- Эксплуатация: на время транзакции берётся advisory lock; новые таблицы с
  `organization_id` и FK-зависимости обнаруживаются через PostgreSQL catalog.

## Критерии приёмки

- [x] Без `--execute` данные не изменяются и выводится план по таблицам.
- [x] Execute невозможен вне test/pytest, без backup reference или без точного кода.
- [x] Связанные строки, включая защищённые immutable trigger, удаляются в одной
  транзакции; при сбое сохраняется исходное состояние.
- [x] Несвязанная организация и shared-аккаунты сохраняются.
- [x] Orphan-users удаляются вместе с identities, credentials, profiles и sessions.
- [x] Штатное удаление membership сохраняет аккаунт и допускает повторное добавление.
- [x] После commit отсутствуют организация и строки с её `organization_id`.

## План проверки

- `git diff --check`.
- Unit: guard/аргументы и чистые функции.
- Integration: отдельная pytest-БД, изолированная schema, прямые/косвенные FK,
  immutable user trigger, legacy session, rollback/dry-run.
- Полный backend-набор и обязательный CI перед слиянием.

Фактические проверки 2026-10-29:

> Результаты ниже фиксируют предыдущую редакцию контракта, в которой аккаунты
> сохранялись. Регрессия расширенного orphan-purge фиксируется отдельными результатами
> проверки текущего изменения.

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

Фактические проверки расширения 2026-10-30, кандидат `2.0.38`:

- Python compile: PASS; unit purge/API: `8 passed`.
- адресная PostgreSQL integration: `2 passed`; orphan-user, identity, credential,
  profile и session удалены, shared-user и его глобальная session сохранены;
  membership shared-user удалён и повторно создан без новой регистрации.
- frontend regression: `91 passed`; ESLint и `npm run build:web`: PASS.
- backend без integration/e2e/llm: `655 passed`, `260 deselected`.
- HTTP/e2e contract: `82 passed`, `12 deselected`; release check `2.0.38`: PASS.
- полный integration: `172 passed`, `2 skipped`; первый запуск дал 6 ошибок из-за
  неверного `STAND_ADMIN_URL`, все затронутые stand-тесты повторены с разрешённой
  локальной maintenance DB: `7 passed`. Обязательный CI ожидает точного SHA кандидата.

## Откат

До commit — автоматический rollback. После commit — восстановление выбранной
организации из указанного backup/snapshot; удаление кода CLI обычным revert не
восстанавливает данные.
