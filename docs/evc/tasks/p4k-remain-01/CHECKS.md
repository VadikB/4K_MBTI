# P4K-REMAIN-01 v1.3 — проверки и передача

База: `5a47e105d406add9b9c3b0386311e921015bdb87` (`origin/main` на 14.11.2026). Кандидат: `codex/p4k-remain-01-assignment-lineage`; точный commit SHA фиксируется в `STATE.md` после завершения проверок. Все данные ниже синтетические, внешних LLM-вызовов и реальной отправки писем не было. Главный browser-маршрут использует компонентную подстановку плана `browser-component-plan-boundary/1`; это не опубликованный пилотный admission.

| Критерий | Доказательство и фактическое постусловие | Статус |
| --- | --- | --- |
| F03-AC01 | `test_reassignment_with_same_profile_prepares_own_cycle_without_changing_history`, `test_reassignment_http_start_presents_new_as_once_with_zero_answers`; `path29-participant.spec.mjs` с `P4K_REMAIN01_REASSIGN=1`: B имеет новый assignment/Cycle, первая AS `active`, 0 оценочных ответов, история A и его снимок сохранены. | PASS |
| F03-AC02 | HTTP/PG повтор старта возвращает ту же AS и ровно один collecting interval; browser: повторное нажатие, потерянный ответ подготовки B, reload, две вкладки и новый контекст возвращают B без лишних Cycle/операций. | PASS |
| F03-AC03 | `test_path_start_assignment_lineage_db.py`, `test_reassignment_supersedes_stale_queued_preparation_without_new_index`, `onboarding-late-readback.test.mjs`: выбор exact assignment, старый queued/failed не подменяет B; запоздалый GET старого scope не меняет новый UI. | PASS |
| F03-AC04 | `test_real_sql_revocation_scope_and_publication_fail_closed_before_start`, `test_reassignment_http_start_presents_new_as_once_with_zero_answers`, существующие `test_adm_layout_31_cancellation_db.py` и role-isolation HTTP/PG: отменённый A и чужой Cycle не стартуют, начатый не отменяется. | PASS по адресному набору |
| F12-AC01 | `test_m3_base_roles.py`, exact-role tests и основной browser-маршрут с UI назначения: шесть BaseRoles и пилотный допуск не менялись. | PASS (reused) |
| F12-AC02 | Существующие `test_m3_role_profiles_db.py`, `test_m3_role_profile_selection_http.py`, `test_questionnaire_sources_db.py` и admission tests отвергают неподходящую версию/роль/организацию до привязки. | PASS (reused) |
| F12-AC03 | `test_f01_role_isolation_db.py`, `test_f01_role_isolation_http.py`, `test_managed_assignment_participation_db.py`: admin access и M3 binding различны, участник не получает admin, superadmin не становится участником. | PASS (reused) |
| F16-AC01 | `test_admin_assessment_stage.py`, `test_organization_invitation.py`, `arch30-member-stage.test.mjs`, `test_adm1c_status_history_db.py`, UI карточки участника в главном browser-маршруте: текущий B и точная история A/B; почта/ссылка/регистрация остаются вторичными сигналами, техническая неизвестность отделена от предметного этапа. | PASS |
| F16-AC02 | `e02-completion-waiting.test.mjs` и короткий `F16 processing dialog` в `adm-program-guards.spec.mjs`: read-only диалог, Escape и смена программы не запускают действие. `test_m8_report_access_db.py`/`test_m8_report_access_http.py` проверяют **старый** recipient ACL. Дополнение 14.11 уточняет: любой действующий org-admin должен читать готовые отчёты своей организации, новый admin — и старые, отозванный — теряет доступ; личное право участника отдельно. Текущий `m8_report_access.customer_can_read_report` и `routes.py` stage всё ещё требуют frozen recipient snapshot. Реализация этого ACL принадлежит REMAIN-02 v1.4; в 01 не меняется. | **PARTIAL**: processing/UI PASS, новое org-admin право FAIL по текущему коду; зависимость REMAIN-02 |
| F16-AC03 | `test_admin_dashboard_modern_metrics.py`, `test_adm1c_status_history_db.py`, `test_m8_report_access_db.py`: современные Cycle/Reports и честная пустая сводка без legacy/fake score. | PASS (reused) |

## Локальные команды

- `git diff --check`: PASS.
- `npm run lint:js`: PASS.
- `npm run build:web`: PASS; `web/dist` обновлён из изменённого исходника.
- `node --test tests/frontend/*.test.mjs`: 272 PASS.
- `npm run test:backend`: 1089 PASS, 558 deselected, 1 warning.
- `npm run test:backend:http`: 153 PASS, 13 deselected, 1 warning.
- Финальный адресный PostgreSQL/HTTP набор F03/F12/F16 в отдельной `p4k_remain01_pytest`: 54 PASS, 1 warning.
- Финальный главный browser-маршрут A→B: 1 PASS за 38.9 с; машинные [browser-reassignment.json](evidence/browser-reassignment.json) и [browser-cleanup.json](evidence/browser-cleanup.json) подтверждают 0 ответов и удаление owned DB. Короткий F16 processing dialog: 1 PASS за 2.4 с после исправления fixture-навигации.
- Первый полный integration с `TEST_DATABASE_URL=…/p4k_remain01_pytest`: 374 PASS, 2 skipped, 25 setup ERROR, 1 warning за 584 с. Все ошибки — fixture `test_exec_fix02_*` требует имя maintenance/test DB из закрытого списка; это ошибка выбора локального URL, продуктовые assertions там не исполнялись. Контрольный ранее ошибавшийся тест PASS на новой пустой owned DB `agent4k_pytest`.
- Финальный `TEST_DATABASE_URL=…/agent4k_pytest STAND_ADMIN_URL=…/postgres npm run test:backend:integration`: **400 PASS, 2 skipped** (явные real-provider), 1246 deselected, 1 warning, exit 0 за 682.62 с. Кластер и обе собственные БД штатно удалены после тестов.
- Полный CI `frontend`, `pytest`, `full-verification` на PR head: NOT_RUN, PR по условиям задачи создаёт архитектор. Человеческое review/приёмка: NOT_RUN.

## Ограничения и передача

Актуальная ветка — локальный кандидат для импорта архитектором. Push, PR, merge, deploy и публикация не выполнялись. Полный локальный integration и CI не заменяют друг друга. F16-AC02 не является полным PASS до REMAIN-02 v1.4; допустимость выпуска с этой зависимостью определяют действующие review/release gates. Платные прогоны, производственные и пользовательские данные не использовались. Откат — `git revert` узкого commit после его фиксации; исторические Cycle/AS/операции и опубликованные snapshots не переписываются.

## Текст для PR архитектора

**Заголовок:** `F03: привязать подготовку и старт Cycle к точному назначению`

**Описание:** После отмены не начатого назначения A новое B с теми же ref, конфигурацией, редакцией анкеты и профилем выбирает собственный Cycle и первую AS. Сохранённые операции, readback, готовность старта, admin stage и ключ UI различают `assignment_id`; старые завершённые операции доступны только для своего Cycle. Устаревшая queued/running операция A освобождает существующий one-active-user slot без изменения схемы. История A не изменяется. F12 и F16 проверены адресно; новое org-admin право чтения готовых Reports остаётся зависимостью REMAIN-02 v1.4 и отмечено `PARTIAL` по F16-AC02.

**Проверки:** локальные backend/HTTP/frontend/lint/build; адресные PostgreSQL/HTTP 54 PASS; browser A→B и processing dialog PASS; полный integration 400 PASS/2 skipped на разрешённой isolated DB. Перед merge обязательны CI `frontend`, `pytest`, `full-verification` и review на точном PR head. Внешний LLM, реальные письма и Report pipeline не запускались.
