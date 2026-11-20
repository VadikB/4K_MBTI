После подтверждения знакомства список и preview анкеты падали с `KeyError: organization_context_version_id`. Сводка использовала последнюю анкету организации и последнее legacy-задание участника, поэтому новая редакция сбрасывала готовность старого назначения, а чужая подготовка влияла на текущую.

Теперь readiness каждого участника проверяется по закреплённой редакции/context version и точному confirmation. Строка участника и сводка используют общий выбор операции по organization/user/assignment/revision/profile. Неоднозначные legacy jobs не присваиваются новому поколению; старое чтение операции по ID сохраняется. Готовность профиля, ход подготовки и допуск к старту остаются отдельными: без допущенной первой AS старт запрещён.

Карточка и полный отчёт: [docs/evc/tasks/adm-fix-01-readiness.md](docs/evc/tasks/adm-fix-01-readiness.md).
Исходная база `origin/main`: `e4bc5c88c45b775a6406f034750e75aa1e4c47be` (2.1.40).
Ветка синхронизирована с `fa55e1eff21864448b0dcb88dd81cdbcbb2d9a56` (2.1.41), кандидат кода и проверок `94b001254cfd3f86f4b8c753763b16489640be8d`.

Проверки на синтетических данных и новом localhost PostgreSQL 15.16:

- backend: 1305 PASS;
- HTTP: 218 PASS;
- адресные questionnaire/assignment lineage SQL/HTTP: 17 PASS;
- полный integration: 484 PASS, 2 explicit real-LLM SKIPPED;
- frontend: 476 PASS; harness: 66 PASS; audit/lint/build и совпадение bundle: PASS;
- `git diff --check`: PASS.

Быстрый CI на 94b00125: frontend PASS, pytest PASS ([run](https://github.com/VadikB/4K_MBTI/actions/runs/44694381565)). Исправлена статическая regression-проверка перенесённого общего SQL; assertions сохранены.

HTTP проверяет list/preview/read/confirm до/после знакомства, реальные права org admin/superadmin и foreign=403, штатные причины несовпадающего профиля/отсутствующего confirmation, readback сохранения и отсутствие новых задач от GET. M4 snapshot/checksum неизменны после новой публикации. Схема, API и опубликованные артефакты сохраняются.

Draft: номер приложения и Ready/release gate ожидают решения владельца. CI точного head и визуальная приёмка учитываются отдельно. Merge/deploy не выполнялись. Откат — revert коммитов этого PR; сохранённые profiles/snapshots и историю не переписывать.

Синхронизация с main fa55e1ef выполнена, полный локальный набор повторён. Ready preflight без изменения версии требует разрешённый PATCH 2.1.42. Full verification в draft ожидаемо SKIPPED; выпуск на TEST и номер ожидают отдельного решения владельца.
