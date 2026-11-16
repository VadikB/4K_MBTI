# Отчёт POSTW02-03

## Результат

Новые публичные pause и interrupt_for_continuation запрещены до записи в БД.
Старые команды читаются по ключу до запрета; несовпадающее содержание даёт
IDEMPOTENCY_CONFLICT. В Cycle-командах сохраняется существующий checksum;
AS event не имел отдельного request_checksum, поэтому сравниваются неизменяемые
сохранённые event_type/action и cause.reason. Нового поля/миграции нет.

| Публичный путь (префикс /users) | Поведение |
| --- | --- |
| /assessment/m7/cycles/{id}/control | новый pause →409 M7_PARTICIPANT_MANUAL_CONTROL_NOT_ALLOWED; resume только по подтверждённому состоянию |
| /assessment/m7/cycles/{id}/completion | новый interrupt_for_continuation → тот же409; complete/final_refusal сохраняются |
| /assessment/m5/situations/{id}/transitions | новый pause → тот же409; resume проходит проверку восстановления; scenario_end/terminate/close сохраняются |
| /assessment/m7/cycles/{id}/additional-sessions | прежний pending intent, однократное потребление, повтор результата по ключу |
| /assessment/m7/cycles/{id}/return-continue | прежний явный Continue по сохранённой policy, без изменений runtime |
| /assessment/pause | legacy user_sessions/session_cases; Cycle UUID не адресует legacy Session |

`participant_command=True` задаётся только тремя owned HTTP-маршрутами, не телом
запроса. Существующая strict Pydantic-схема не принимает произвольные поля.
Внутренние вызовы completion/runtime и admin/m5-runtime/transitions используют
прежнюю семантику. Reason=between_situations не обходит публичный запрет.
У новых отклонённых pause/interrupt нет presence reconciliation, commit, событий,
intent, Evidence, смены AS/Session/Cycle, материалов или временных интервалов.

## Старые состояния и пути восстановления

| Сохранённое состояние | Допустимый путь / ограничения |
| --- | --- |
| Cycle/Session=paused, текущая AS=paused | Cycle/control resume: in_progress той же AS, один authorized_pause, сохранённый pause receipt с checksum/reason/Session/AS, последний interaction_paused; оба лимита и отсутствие признанного/истёкшего lease проверены |
| Cycle/Session=paused, текущая AS=scenario_ended | Тот же Cycle/control resume по saved pause receipt с AS=null, authorized_pause и текущей позиции; scenario_end не переписывается, существующий sync_interim_wait сохраняет открытое уточнение/блокирующий анализ |
| Cycle/Session=active, текущая AS=paused от старого AS/transitions | AS/transitions resume: тот же in_progress, сохранённый interaction_paused с from/to/reason, один collecting; без изменения интервалов/бюджета |
| AS=paused при Session=paused, попытка AS-only resume |409 RESUME_NOT_ALLOWED; использовать согласованный Cycle/control для обоих состояний |
| Между AS, текущая AS закрыта/позиция завершена | resume запрещён; существующий явный старт следующей AS сохраняется |
| blocking_system_wait | resume не закрывает ожидание; применяется существующий системный путь |
| Обязательный возврат |409 EXPLICIT_CONTINUE_REQUIRED; сначала return-continue, затем при оставшейся старой ручной паузе допустимый resume |
| Истёкший бюджет/deadline |409 TIME_LIMIT_REACHED, время не запускается; штатное закрытие выполняется существующим runtime/worker |
| interrupted + pending intent | Additional Session один раз; закрытая AS остаётся закрытой, новый intent не создаётся |
| intent уже consumed | тот же ключ возвращает сохранённую Session; другой ключ не создаёт вторую |
| Нет current route, pause event/receipt, несогласованная причина/AS/Session, повреждённый checksum | безопасного публичного resume нет;409 RESUME_NOT_ALLOWED. Массового исправления/миграции нет; требуется адресная диагностика сохранённого состояния |

Все пути сохраняют бюджет/deadline/snapshots. Таблица описывает реализацию и
синтетические проверки, не наличие таких состояний в Prod.

## Изменённые файлы и трасса

- Api/routes.py — явный признак публичной команды на границе; для pause/resume
  readback выполняется до reconciliation. Остальные HTTP ownership/scope сохранены.
- Api/m7_completion.py — отказ новой публичной команды после replay, проверка
  восстановления по серверной истории/состоянию; внутренний контракт не меняется.
- Api/m5_scenario_runtime.py — запрет публичного pause, сверка AS receipt и
  проверка безопасного AS-only resume. Нет скрытого открытия окончательно закрытой AS.
- docs/architecture/m7-completion-contract.md — уточнение текущей поверхности.
- tests/unit/test_postw02_* — безопасный resume и existing pending intent.
- tests/e2e/test_postw02_participant_commands_http.py — реальные guard-функции
  через FastAPI при подменённом хранилище; readonly fake отклоняет любой SQL write.
- tests/integration/test_postw02_participant_commands_db.py — fingerprint12 таблиц
  при отказе/replay, реальные переходы и границы восстановления на existing fixture.
- Существующий HTTP happy path использует оставшийся допустимым terminate;
  существующий integration Additional Session расширен повтором и конфликтом ключа.

Источник POSTW02-03 rev1.0 → публичная граница PM-04 → admission checks после
existing receipt → HTTP/unit и PostgreSQL-регрессии. M7v1.3 §§5.3–5.5,6.3 →
исходные времена и различение приостановки/завершения → recovery helper и прежний
Additional Session. Источники/статусы/область чтения зафиксированы в [TASK](TASK.md).

## Проверки

- PASS: адресный первоначальный набор48 (resume/R1 policy unit + public HTTP +
  существующие M5 HTTP).
- PASS с оговоркой среды: npm run test:backend —1142 passed,9 FAIL в
  test_synthetic_limits.py из-за sandbox PermissionError на ps; повтор только
  этого файла с разрешённым доступом к собственным синтетическим процессам —19/19 PASS.
  После добавления pending-intent тестов они проверены отдельно; полного набора
  повторно не запускали. Общая локальная совокупность покрывает1159 unit cases.
- PASS: npm run test:backend:http —186 passed; добавленная после этого legacy
  регрессия проверена адресно (итоговый набор содержит187 HTTP cases).
- PASS: последняя адресная перепроверка42 (resume, pending intent, public HTTP)
  после уточнения порядка проверок возврата; дополнительный scenario_ended case
  проверен отдельным финальным файлом resume26/26.
- PASS: node --test tests/frontend/postw02-assessment-ui.test.mjs
  tests/frontend/p03-return-presence.test.mjs —12/12 (подменённый HTTP, без браузерной БД).
- PASS: py_compile изменённых Python-модулей/нового integration; git diff --check.
- NOT_RUN:19 выбранных PostgreSQL cases (15 новых +4 существующих R1/lease/
  deadline/Additional Session); runner подтвердил SKIP, не PASS. Нет настроенной
  TEST_DATABASE_URL; новую инфраструктуру по заданию не создавали.
- NOT_RUN: реальные устройства/визуальная приёмка, browser R1 lost-response с БД,
  реальные LLM/письма, полный PATH, Prod и проверка snapshot конкретного Prod Cycle.

Изолированная PostgreSQL-проверка перед Ready/merge обязательна; существующий
full-verification запускается на Ready, не на draft. Статус CI точного commit и
финальные base/head/PR сохраняются в outputs/p4k-postw02-03-20261116 вне Git,
чтобы запись статуса не меняла проверенный head. Версия унаследована2.1.16;
новый кандидат/Ready не назначались.

## Review, риски и откат

Самопроверка по review-checklist: три публичные точки найдены поиском всех вызовов
control/complete/transition в routes; admin и internal не получили флаг. Сохранённый
readback предшествует запрету и текущим лимитам. Resume сериализуется существующим
Cycle lock; AS lock order сохранён. Закрытые AS/межкейсовое состояние не открываются.
В двух клиентах атомарность зависит от существующего PostgreSQL lock/idempotency;
новые DB-регрессии ещё не выполнены, это ограничение приёмки.

Навигация проверена кодом: кабинет вызывает cleanup/stopProductPresence, обычные
активные кнопки не создают pause/interrupt (frontend regression PASS). Начало product
Cycle очищает assessmentSessionCode/Id; legacy endpoint читает только user_sessions,
его сервис изменяет session_cases. HTTP с Cycle UUID отклонён404 без вызова сервиса.
UI-файлы и dist не менялись; фактическая визуальная/устройственная приёмка NOT_RUN.

Конфиг/схема/definitions: без изменений. Риск совместимости: неподтверждённые старые
paused combinations отклоняются, а не восстанавливаются предположением.
Безопасность: только синтетические fixtures, без реальных данных/секретов.
Откат: revert собственного коммита; snapshots/intent/история остаются. Откат вернёт
доступность ручных команд, поэтому выполняется отдельным решением владельца.

Следующий шаг: review draft PR, PostgreSQL cases в существующем изолированном CI,
затем отдельное решение владельца о кандидате/Ready/слиянии. Пользовательская
приёмка и Prod deploy этим отчётом не заявлены.

## Передача: остановлена auto-review

Автоматическая проверка отклонила попытку `git push -u origin
codex/p4k-postw02-03`: внешний destination VadikB/4K_MBTI не признан доверенным,
и reviewer требует прямое одобрение передачи конкретного payload туда. Команда
не выполнена; remote branch и PR этим запуском не созданы. Повтор/обход отказа
не выполнялись. Изменения, патч и подготовленное описание PR сохранены локально.
Нужно прямое разрешение владельца на push этой ветки и создание одного draft PR
в указанном репозитории; merge/deploy/bump по-прежнему не входят в этап.
