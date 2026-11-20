После подтверждения знакомства список и preview анкеты падали с `KeyError: organization_context_version_id`. Сводка использовала последнюю анкету организации и последнее legacy-задание участника, поэтому новая редакция сбрасывала готовность старого назначения, а чужая подготовка влияла на текущую.

Теперь readiness каждого участника проверяется по закреплённой редакции/context version и точному confirmation. Строка участника и сводка используют общий выбор операции по organization/user/assignment/revision/profile. Неоднозначные legacy jobs не присваиваются новому поколению; старое чтение операции по ID сохраняется. Готовность профиля, ход подготовки и допуск к старту остаются отдельными: без допущенной первой AS старт запрещён.

Карточка и полный отчёт: [docs/evc/tasks/adm-fix-01-readiness.md](docs/evc/tasks/adm-fix-01-readiness.md).
База `origin/main`: `e4bc5c88c45b775a6406f034750e75aa1e4c47be` (2.1.40).

Проверки на синтетических данных и новом localhost PostgreSQL 15.16:

- backend: 1301 PASS;
- HTTP: 218 PASS;
- адресные questionnaire/assignment lineage SQL/HTTP: 17 PASS;
- полный integration: 484 PASS, 2 explicit real-LLM SKIPPED;
- `git diff --check`: PASS.

HTTP проверяет list/preview/read/confirm до/после знакомства, реальные права org admin/superadmin и foreign=403, штатные причины несовпадающего профиля/отсутствующего confirmation, readback сохранения и отсутствие новых задач от GET. M4 snapshot/checksum неизменны после новой публикации. Схема, API и опубликованные артефакты сохраняются.

Draft: номер приложения и Ready/release gate ожидают решения владельца. CI точного head и визуальная приёмка учитываются отдельно. Merge/deploy не выполнялись. Откат — revert коммитов этого PR; сохранённые profiles/snapshots и историю не переписывать.

Во время работы main продвинулся до `fa55e1ef` (#257). Файлы ADM-FIX-01 в этом изменении не затронуты. Рабочая ветка сохраняет проверенную исходную базу; перед Ready требуется синхронизация и проверки нового head/base.
