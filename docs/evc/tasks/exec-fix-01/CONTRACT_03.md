# Стык EXEC-FIX-01 / EXEC-FIX-03

EXEC01 root — единственный писатель `m7_clarification.answer/record_outcome`, `m7_completion.finish_current_situation`, return guards/DTO. Base 46a5532336e41c5cdedf9684ba7bd5a9c5c202d1.

`answer` перечитывает response под Cycle→AS lock. Identical `decision_id/request_id/turn_id/content` replay возвращает прежний response до проверки нового допуска, в том числе после budget/deadline/closed; изменение любого поля даёт IDEMPOTENCY_CONFLICT. Новые записи используют существующий assert_collecting + recognized/expired presence explicit Continue. Старые snapshots/схема не меняются.

Runtime получает additive `finish_availability: {allowed: boolean, reason: string}|null`. Только серверная current material→interim C45→C54→M7 цепочка разрешает обычный Finish. Клиенту достаточно allowed===true; причины INTERNAL ожидания: INTERIM_PENDING, DECISION_STALE, WAIT_TECHNICAL, OPEN_ASK, ANALYSIS_FAILED, DECISION_STOP. Для active AS обычный сценарный Finish сохраняет прежний смысл scenario_end, затем ожидание.

01 не добавляет owner answer readback endpoint; узкий endpoint EXEC03 `/assessment/m5/situations/{AS}/answer-status` с исходными request_id/turn_id/optional clarification_id принадлежит03. Он должен проверять owner/cycle/AS identity, читать исходный сохранённый результат после закрытия/смены текущей AS, без новой записи и обхода write guards. 01 не меняет draft/delivery/send/readback helpers или wiring.

Обязательная объединённая проверка: accepted before boundary → потеря HTTP response → close/time expiry → owner readback + identical replay дают один сохранённый Turn/response/interim/job; changed payload conflict; новая запись blocked. Совместную проверку делать в отдельном compose checkout, исходные ветки/кандидаты не смешивать. Candidate SHA/evidence будут в outputs/p4k-exec-fix-01-20261109/HANDOFF.json после финального прогона.

Дополнение стыка: новая запись в исходный ASK допускается только если его C54 остаётся последним interim C54 этой AS; superseded ASK1 при current ASK2 отклоняется M7_CLARIFICATION_STATE_CHANGED. Accepted replay всё равно выполняется раньше этого guard. Handler также сверяет current route AS, если route существует. HTTP replay не создаёт новую pipeline revision и не перезаписывает ready/failed projection. Каждый успешный Finish receipt (включая вторую вкладку уже closed AS) закреплён за исходной AS.
