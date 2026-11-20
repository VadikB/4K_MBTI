# Контракт состояния обработки результата

Версия: `m10-processing-recovery/1.0.0`. Область: техническое состояние
обработки закрытого Cycle после M5/M7, без изменения предметных правил M6.

## Разделение состояний

- `collection_status` описывает сбор и закрытие Cycle;
- четыре `outcome` M6 (`full_score`, `partial_score`, `result_without_score`,
  `no_result`) остаются предметными исходами;
- `processing.status` описывает техническое исполнение механизма;
- `report_status` описывает доступность представления.

Наличие `report_id` не переводит `processing.status=failed` в успех. Ограниченный
Report сохраняет подтверждённые IA и материал, но явно показывает техническое
ограничение. `PROCESSING_FAILED` не преобразуется в L0, IE или
`NOT_COMPARABLE`.

## JSON-проекция для UX

```json
{
  "processing": {
    "contract_version": "m10-processing-recovery/1.0.0",
    "status": "completed | processing | failed | recovered",
    "message": "локализованное server-approved сообщение",
    "allowed_actions": []
  },
  "pipeline_stage": "admission_processing_failed",
  "processing_error": "M6_ADMISSION_PROCESSING_FAILED",
  "report_status": "limited",
  "report_id": "uuid-or-null"
}
```

Адресный статус участника возвращает `route_progress` того же Cycle. `total`
берётся из сохранённого маршрута, `completed` — из числа завершённых позиций.
Если сохранённый план нельзя подтвердить, оба поля имеют значение `null`.
Ноль при подтверждённом плане обозначает отсутствие завершённых позиций.

`processing_error` предназначен для диагностики; UI показывает `message`.
Участнику не предлагается retry: `allowed_actions=[]`. Авторизованный повтор
доступен ответственному через
`POST /users/admin/assessment/m8/cycles/{cycle_id}/processing-recovery` с
`idempotency_key`, действующим правом `configuration.publish` и статусом
суперадминистратора. Администратор организации не запускает восстановление.

## История и восстановление

Каждый переход записывается новой строкой `m10_pipeline_revisions`. Recovery
запоминает frozen `catalog_ref`, `profile_ref`, `target_set_checksum`, время
закрытия и исходную pipeline revision. После ошибки подготовки Report при
корректных C-56/Results повтор использует сохранённые calculation ID, Results
revision ID и checksum; создаётся только ещё не сохранённый Report. Если сбой
затронул расчёт, исправленная попытка создаёт новые неизменяемые Calculation,
Results revision и Report; старые записи не обновляются.

REPORT_01: финализация подбирает также закрытый Cycle в состоянии `calculated`.
Если Results сохранён, а Report отсутствует, она продолжает создание Report;
если допустимый Report уже сохранён, восстанавливает только состояние pipeline.
`m10_report_claims` содержит
один claim на Cycle с токеном и сроком 10 минут; конкурентный worker не
генерирует второй Report. Работающий worker обновляет срок каждые 30 секунд;
перед сохранением C-67 токен и срок проверяются повторно. После аварийного завершения просроченный claim может
быть захвачен повторно. Сохранённый допустимый Report и `ready` pipeline
исключают повторную финализацию. Ошибка генерации или валидации описания не
публикует пустой `assessee` Report и переводит pipeline в `report_failed`.
Служебный recovery доступен для зафиксированных `report_failed`,
`processing_failed`, `admission_processing_failed` и `recovery_failed`.
Повторное чтение не создаёт задач и не сбрасывает попытки.

GET status/history/report/PDF — только чтение. Они не ставят recovery в очередь,
не вызывают AI и не открывают сбор. Production worker обрабатывает очередь
recovery через обычный orchestration loop. Повтор не меняет Cycle, Session,
Dialogue, AS, catalog snapshot или временной бюджет.

Обычный `POST /users/assessment/m8/cycles/{cycle_id}/reports/regenerate`
удалён. Прямая публикация второго `assessee` Report через admin endpoint
отклоняется; служебный recovery проходит через очередь M10. Если ранее
опубликован корректный Report, поздняя техническая ошибка не скрывает его
от владельца.

## Совместимость и откат

Изменение схемы аддитивно: `m10_report_claims` не меняет прежние строки.
Старые Results без `processing` проецируются как
`completed`. Откат к предыдущему runtime оставляет новые таблицы невостребованными;
immutable Results/Reports и recovery history не удаляются. До удаления схемы
нужен отдельный согласованный migration plan.
