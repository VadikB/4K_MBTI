# Проверки P4K-REPORT-02

Base `32a13d3d`; product commit `94233541`, draft PR #227. Все данные синтетические. PostgreSQL 15 запускался локально на `127.0.0.1:55432` с базами `agent4k_pytest` и `p4k_report02_pytest` только для этой задачи и остановлен после проверок. Реальные LLM и почта не вызывались.

| Критерий | Статус | Доказательство / предел |
| --- | --- | --- |
| AC01–03 HTTP+PostgreSQL права и история | PASS адресно | `tests/integration/test_m8_report_access_db.py`: владелец без членства, другой участник, действующий/новый/снятый/чужой администратор, анонимный, list/detail/PDF/comparison и подмена чужого report ID. `test_profile_to_m4_owned_stand.py` проверяет перевод владельца в другую организацию, сохранение history/Results/Report/PDF и отказ старта Cycle со старым профилем. Служебный суперадмин использует прежний маршрут; отдельного расширения админского scope нет. |
| AC04 миграция и откат | PASS адресно | `test_archive_migration_empty_filled_and_rollback`: пустая и заполненная схема, архивные строки, повторный up, обратный SQL. Отдельная миграция не запускалась на общей TEST/Prod. |
| AC05 DOM и runtime | PASS адресно | `tests/browser/report02-recipient-form.spec.mjs`: 1440/390/320 px, подставленный legacy payload, отсутствие полей/секции и переполнения; снимки в `evidence/`. Поиск runtime показывает отсутствие `m8_cycle_report_recipients` вне SQL миграции/исторических тестов; приглашения и назначения используют другой смысл `recipient_*`. |
| AC06 публичная проекция | PASS адресно | `test_public_projection_excludes_nested_private_data`: непустые skill/competency/claim, технические trace, provenance, profile, dialogue, checksum. Чистый bootstrap подтверждает HTTP/PDF. |
| Backend | PASS | `npm run test:backend`: 1117 passed, 580 deselected. |
| HTTP | PASS | `npm run test:backend:http`: 153 passed, 15 deselected. |
| Frontend | PASS | `node --test tests/frontend/*.test.mjs`: 334 passed. |
| Интеграция | PASS | Полный повтор `TEST_DATABASE_URL=… .venv/bin/python -m pytest -q --run-integration tests/integration`: 421 passed. Дополнение матрицы сравнения и финальный PDF/projection проверены адресно после запуска полного прогона: 3 passed и 6 passed. Предыдущий проход с 25 падениями был исправлен; журналы в `/private/tmp/p4k-report02-*`. |
| JS lint/build/diff | PASS | `npm run lint:js`, `npm run build:web`, `git diff --check`. |
| CI product commit `94233541` | PASS / SKIPPED | В draft PR #227 jobs `frontend` и `pytest` PASS; `full-verification` ожидаемо SKIPPED до Ready. После release commit проверка повторяется на новом head. |
| Release preflight | PASS | Владелец утвердил PATCH `2.1.13`. `npm run ready:prepare -- --candidate 2.1.13` и точный повтор — PASS, diff между повторами идентичен; `git diff --check` PASS. |
| CI release head | PENDING | После commit/push и перехода PR #227 в Ready необходимы `frontend`, `pytest`, `full-verification` на точном head. |

## Карта удаления и сохранения

- Удалены: строки выбора получателей из формы организации, DTO `QuestionnaireConfirmRequest`, сохранение recipient IDs/карт, recipient-текст из briefing, freeze при Cycle, проверка `m8_cycle_report_recipients` в админском списке, создание четырёх legacy-таблиц в bootstrap.
- Сохранены: адресаты приглашений и назначений (`organization_invitations`, `organization_assessment_assignments`), журнал `m8_report_access_events`, историческая колонка `questionnaire_response_revisions.recipient_mapping_json` в уже существующей БД и архивные таблицы `*_legacy_audit` с исходными строками/триггерами. Их имена остаются в SQL миграции и исторических тестах.
- Старые HTTP payload с `recipients`/`recipient_user_ids` игнорируются Pydantic и не влияют на scope; это проверено stand-сценарием `remarks_questionnaire_actor`.

## Восстановление

Миграция `p4k_report_02_archive_access.sql` выполняется транзакционно вместе с контролем схемы до выпуска приложения. Для отката приложения запустить `p4k_report_02_restore_access.sql` в отдельной транзакции и вернуть предыдущий release. Архивные записи не удаляются, API и таблицы нового журнала доступа остаются совместимыми. На пустой схеме обратный SQL не создаёт фиктивных recipient-записей; предыдущий bootstrap создаст старые таблицы при запуске.
