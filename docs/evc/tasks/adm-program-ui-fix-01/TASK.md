# P4K-ADM-PROGRAM-UI-FIX-01 — локальный кандидат

Основание: прямое поручение пользователя 09.11.2026 выполнить START_CODEX.txt
из одноимённого пакета, без общего checkpoint. Последующее прямое уточнение
включает карточку «Готовность назначения». Пакет задаёт требования; полномочие
локальной работы исходит от пользователя, допуски чужих задач не наследуются.

Base: `46a5532336e41c5cdedf9684ba7bd5a9c5c202d1` /2.0.87, повторный fetch совпал.
Отдельная рабочая копия/ветка и последующее состояние описаны в STATE.md.

## Требования → реализация → проверка

| Источник | Требование | Реализация | Проверка |
| --- | --- | --- | --- |
| TASK.txt §3А/Б, AC01/02 | Нет ручного технического ключа; отсутствие и неизвестность различаются | organizationProgramState, assessmentFieldMarkup; pre-POST scope guard | adm-program-guards: две роли/формы, forced submit, unknown cached A и delayed CSV |
| TASK.txt §3В, ADR-003 | Точный подтверждённый scope и прежний revision-процесс | existing preview/confirm API, hidden ref | adm-program-positive: реальный HTTP/owned PG manual и CSV, exact revision/confirm/reload/readback |
| TASK.txt AC04 | Не переносить draft/confirmation между программами, сохранить последние поля | data-assessment-ref, draft capture/restore, generation fences | A→B→A, absent→first connection, old collection/import/program readbacks |
| Прямое уточнение владельца | Основной blocker программы и честные зависимые состояния readiness | assignmentReadinessMarkup, отдельные role/anketa labels | absent/unknown/confirmed; role unknown/none/unavailable/available, exact/cached questionnaire |
| TASK.txt AC05/06 | Права/API и независимые данные сохранены; готовый просмотр | existing independent profile save; admin-only responsive CSS | existing frontend/HTTP/browser regressions, 1440/390/320 и synthetic text200 |

Понятийный слой PM-02/PM-03 и ADR-003 сохраняются; изменён только frontend UI
и технический тестовый контур. ProgramDefinition, published sources, БД/миграции,
методология и публичный API не меняются. M1 CURRENT не присваивается.

Локальный минимум: diff check, lint, build (байты dist соответствуют исходнику),
frontend tests, адресный browser и actual HTTP/owned PG. API regressions включают
existing confirmation/assignment/readiness HTTP checks. Источники и решения — STATE.

Для visual: обе роли, absent/unknown/confirmed, обе формы и readiness; 1440/390/320,
computed text200. Физические устройства/native textzoom и приёмка владельцем отдельно.
Галерея synthetic HTTP не заменяет реальный positive HTTP/PG и опубликованный TEST.

Проверки с данными используют существующий marker-owned test_stand/ADM28 fixture.
Fixture готовит upstream программу/организацию/аккаунты; tested questionnaire
preview/confirm выполняются реальными действиями UI, не вставкой revision в БД.
Provider disabled, gateway0; все counts оценки неизменны. Evidence сохраняется до
проверенного cleanup. Новая временная локальная PG16 не использует рабочую .env/БД.

Local commit/bundle разрешены; branch_push/pr/merge/deploy/version_bump/artifact_publish=false.
Релизную версию готовит архитектор отдельно. Откат — revert собственных изменений;
организации, анкеты, назначения и оценки не удаляются. Открытых предметных решений нет.
