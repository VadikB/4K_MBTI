# PILOT31-02 — каталог программ и пустое состояние

Дата проверки: 2026-10-31. Контур: TEST. Deployed commit:
`fa38c46c1034ad2452bc47be065a40d42c3fd0a6`, ветка `main`.

## Результат диагностики

Причина пустого списка подтверждена чтением БД в транзакции `READ ONLY`:
`assessment_program_definitions` не содержит строк. При этом в БД существуют
три опубликованные конфигурации и два опубликованных каталога. Поэтому
`list_published` возвращает пустой список: наличие каталога само по себе не
создаёт `ProgramDefinition`.

| Уровень | Фактическая запись | Классификация | Доступность нового назначения |
| --- | --- | --- | --- |
| Catalog | `specialist-pilot@1.0`, published, assessment, 9 cases | admitted current catalog | нет: отсутствуют связанная configuration и ProgramDefinition |
| Catalog | `e102-controlled@1.0`, published, assessment, organization `1`, 2 cases | QA/controlled | нет вне указанной организации; не Specialist pilot |
| Configuration | `4k_standard_v1`, published/default, methodology `1.0`, без catalog | legacy | нет как новая программа: отсутствует ProgramDefinition |
| Configuration | `4k_m5_qa_v1_1`, published, methodology `1.1`, без catalog | QA | нет: отсутствуют catalog и ProgramDefinition |
| Configuration | `e102_controlled_catalog`, published, catalog `e102-controlled@1.0` | QA/controlled | нет: отсутствует ProgramDefinition |
| ProgramDefinition | строк нет | отсутствует | нет |
| Organization connection | строк нет | отсутствует | нет |
| Pilot binding | строк нет | отсутствует | нет |

Опубликованная роль `specialist_expert@1` для methodology `1.1` существует.
Draft и retired ProgramDefinition отсутствуют; это не означает, что исторические
оценки или их snapshots отсутствуют — персональные данные не читались.

## Цепочка DB → API → UI

- DB: 0 строк ProgramDefinition — PASS, подтверждено SELECT.
- API: код `Api/assessment_programs.py:list_published` выбирает только
  `status='published'` из `assessment_program_definitions`; при текущей БД
  корректный результат равен `[]`. Живая проверка авторизованного SUPERADMIN GET
  не выполнялась: доступная SSH-сессия не предоставляет и не должна извлекать
  пользовательские credentials (`API_CHECK=NOT_RUN`).
- DTO: `_build_admin_organizations` передаёт список только суперадминистратору;
  для администратора организации управление не выводится.
- UI: `assessment_programs=[]` ранее оставлял активную кнопку рядом с пустым
  select. Теперь empty явно объяснён, select и действие disabled; loading,
  loaded-empty и failed-to-load различаются, failure предлагает повтор загрузки.

## Release readiness

Публикацию выполнять рано. Из обязательных параметров подтверждены catalog
`specialist-pilot@1.0` и role-code `specialist_expert`. Для него отсутствует
опубликованная `assessment_configuration`, связанная именно с этим catalog.
`scripts/publish_assessment_program.py` принимает `configuration-code`, а не
catalog напрямую, и обоснованно остановит validation. Code, version, name,
assignment-ref, mode и publisher-user-id для новой ProgramDefinition также не
зафиксированы принятым release-решением. Синтетические значения не подставлялись.

Следующий отдельный шаг владельца: утвердить/указать существующую configuration
для `specialist-pilot@1.0` и идентичность ProgramDefinition. Затем штатная команда
сначала запускается без `--publish`; публикация и подключение организации — два
разных разрешённых действия.

## Проверки и границы

- Приложенный `READONLY_INVENTORY.sql` — PASS с `ROLLBACK` в test/pytest БД.
- Инвентаризация published role versions — PASS, `READ ONLY` + `ROLLBACK`.
- `node --test tests/frontend/*.test.mjs` — PASS, 113/113.
- `npm run lint:js` — PASS.
- `npm run build:web` — PASS.
- `git diff --check` — PASS.

Live-данные, схемы, статусы, связи, права, опубликованные артефакты и snapshots не
изменялись. Публикации, миграции, писем и LLM-вызовов не было. Откат кода — revert
коммита этой задачи; для данных откат не требуется.
