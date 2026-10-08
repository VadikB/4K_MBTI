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

`processing_error` предназначен для диагностики; UI показывает `message`.
Участнику не предлагается retry: `allowed_actions=[]`. Авторизованный повтор
доступен ответственному через
`POST /users/admin/assessment/m8/cycles/{cycle_id}/processing-recovery` с
`idempotency_key` и правом `configuration.publish` в области организации.

## История и восстановление

Каждый переход записывается новой строкой `m10_pipeline_revisions`. Recovery
запоминает frozen `catalog_ref`, `profile_ref`, `target_set_checksum`, время
закрытия и исходную pipeline revision. Повтор создаёт новые неизменяемые
Calculation, Results revision и Report; старые записи не обновляются.

GET status/history/report/PDF — только чтение. Они не ставят recovery в очередь,
не вызывают AI и не открывают сбор. Production worker обрабатывает очередь
recovery через обычный orchestration loop. Повтор не меняет Cycle, Session,
Dialogue, AS, catalog snapshot или временной бюджет.

## Совместимость и откат

Изменение схемы аддитивно. Старые Results без `processing` проецируются как
`completed`. Откат к предыдущему runtime оставляет новые таблицы невостребованными;
immutable Results/Reports и recovery history не удаляются. До удаления схемы
нужен отдельный согласованный migration plan.
