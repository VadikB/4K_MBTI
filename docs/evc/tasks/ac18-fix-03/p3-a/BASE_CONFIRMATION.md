# Общая база и существующий стык 3А

09.11.2026 владелец ответил на вопрос о checkpoint общей базы:

> Base: 023bf85ec796d212d29b33218d906a1ed2023941

Это прямое подтверждение общей базы; отдельная квитанция архитектора, её номер
и checksum не предоставлены и не приписываются владельцу.
Свежий origin/main при старте совпал с этой базой, source APP_RELEASE 2.0.86.

Существующее распределение участков и контракт взяты из входного пакета,
`CONTRACT_AND_OWNERSHIP.md`, SHA256
`53a6ea7ffd394657d7f1c522d4ce6b6f0ad83373bd07ec95407adfb7556840a0`.
Функции draft/delivery/submit UI принадлежат 3А; time/progress/return/presence
и backend остаются 3Б. Новых endpoint/schema/migration задача 3А не вводит.

Проверка фактического стыка базы:

- `Api/m5_scenario_runtime.py:submit_turn_detached` сохраняет/commit Turn до внешней
  обработки. Ошибка HTTP/provider после этого не доказывает отсутствие Turn.
  Существующая пара request_id/turn_id сохраняется для повтора той же операции.
- M5 POST возвращает `{turn, events, idempotent}`. `turn.turn_id` и content_text
  позволяют подтвердить сохранение; participant runtime trace содержит turn_id,
  speaker_type/content_text, но не request_id.
- M7 clarification POST возвращает decision с answer_turn_id,
  response_request_id/response_outcome. При повторе используется исходный endpoint
  и decision ID, а не новый latest clarification.
- Readback ограничен исходными Cycle/AS и turn_id; ответ другого scope не меняет
  экран/черновик. Перед повтором неизвестной операции сначала читается факт.
- Guards активной фазы могут отклонить повтор уже сохранённого Turn после смены
  состояния. Поэтому один только HTTP409 не является доказательством отказа записи.

Эти выводы проверены чтением routes, m5_scenario_runtime, m7_clarification,
m7_clarification_repository и m10_product_flow participant projection на данной
базе; последующие изменения 3Б требуют обновить базу и затронутые checks.
