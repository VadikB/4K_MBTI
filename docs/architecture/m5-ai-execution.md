# M5 AI execution trace

Статус: implemented contract for T08.3; методологическое оценивание M6 отсутствует.

## Карта операций

| Операция | Вход | Исполнитель | Проверка | Результат |
| --- | --- | --- | --- | --- |
| `semantic_decision` | правило M5, пользовательский Turn, revision состояния | `DeepSeekSemanticAdapter` | JSON, enum, model identity, актуальность revision | `m5_rule_decisions`; техническая попытка в `m5_ai_attempts` |
| `character_response` | разрешённый материал, публичная позиция персонажа, пользовательский Turn | `DeepSeekCharacterAdapter` | JSON, непустая реплика, model identity | Turn с `speaker_type=character`; попытка в `m5_ai_attempts` |
| `technical_c45` | сохранённый C-45 целиком и точный IndicatorID | QA-only adapter | C-54 echo contract, AS/handoff/mode/Indicator/M2/boundary | `m5_c54_receipts`; IA/Evidence не создаются |

## Идентичность исполнения

`m5_assessment_situations.execution_payload_json.ai_operations` содержит зафиксированные
provider, endpoint, model, параметры, `prompt_ref`, формат ответа и политику идентичности.
Checksum `execution_payload_ref` входит в неизменяемый AS snapshot. Runtime создаёт gateway
из этой конфигурации. Текущие глобальные model/endpoint после подготовки AS её не заменяют.

`m5_ai_attempts` различает предусмотренную конфигурацию, фактически отправленные аргументы
и метаданные ответа провайдера. `revision=null` означает, что провайдер её не сообщил.
Секреты и ключи не сохраняются. Известное несовпадение model отклоняет результат.

## C-45/C-54

`final` C-45 допустим только для закрытой AS; `interim` — после конца сценария, пока AS
открыта. C-45 содержит исходные Turns с авторством и временем, события, фактически
предъявленные материалы, snapshot refs и inclusive boundary. Позднее изменение Dialogue
не меняет уже сохранённый handoff.

Текущий M5 QA runtime создаёт AS без Cycle/Session, поэтому `cycle_ref` и `session_ref` в
его C-45 равны `null`. Продуктовый путь обязан передать эти ссылки после реализации
владельца сборки сессии M7; T08.3 не создаёт фиктивные Cycle/Session.

Технический C-54 используется только для проверки транспорта в серверно авторизованном
QA-контуре. Он не является M6, не создаёт IA, Evidence, L0 или `INSUFFICIENT_EVIDENCE`.

## Ошибки и повторы

HTTP action, AI request и attempt имеют отдельные ID. Уникальные `action_key` и handoff ×
Indicator обеспечивают идемпотентность. Невалидный JSON, неизвестный Indicator,
несовпадение M2/AS/handoff/boundary и provider identity сохраняются как отклонённые либо
технические исходы. Техническая ошибка не создаёт предметный результат и не завершает AS.

Provider revision наблюдаема только если она присутствует в ответе API. Одинаковый вход
не обещает побайтно одинаковый ответ.
