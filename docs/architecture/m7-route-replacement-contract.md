# M7 Route Position Replacement v1

Дата: 15.10.2026. Статус: draft runtime foundation. Основание: UX-P01 rev 2.0,
решение владельца от 15.10.2026, M1 v1.4 §§5–10, M6 v1.8, M7 v1.3,
Change 01 и ADR-002.

## Граница

PM-04 хранит устойчивую позицию маршрута, её текущую AS и полную историю замен.
PM-03 готовит candidate через `ReplacementProvider`; production fallback отсутствует.
P01 не определяет автоматическое условие возврата, предъявление новой AS и
возобновление времени — это область P03.

Операция применима только к текущей предъявленной незавершённой AS в состоянии
`active` или `paused`. Клиент передаёт ожидаемые AS/state и idempotency key.
Cycle, позиция и AS блокируются и повторно проверяются; terminal Cycle, исчерпанный
бюджет и календарный deadline запрещают переключение.

## Данные и атомарность

`m7_route_positions` хранит номер, CaseID/version, цели, состояние и текущую AS.
`m7_route_position_as_history` хранит все AS позиции и явное `current/replaced`.
`m7_as_replacement_operations` хранит запрос, expected AS/state, policy ref,
candidate и сохранённый результат. Ограничения гарантируют одну текущую AS позиции,
одну позицию для AS и один эффект request key.

Candidate обязан сохранить Cycle, Session, CaseID/version, профиль и допуск.
В одной транзакции старая AS переводится в `terminated`, получает явное основание
исключения, а новая `admitted` AS становится текущей на том же месте. Dialogue,
Turns, snapshots и результаты старой AS не изменяются и не копируются.

## C-46, M6 и совместимость

C-46 v1 совместимо расширяется блоком `route`: позиции, current AS и история.
Каждая AS имеет `route_disposition`; legacy AS без позиции читается как
`legacy_current`. Checksum состава включает маршрут и исключения.

Заменённая AS исключается из `_facts`, final outbox и M6 observations до проверки
готовности расчёта. В C-46 она остаётся с причиной и operation ref. Фильтр не
выбирает лучший IA: единственное основание — сохранённая операция замены.

Откат запрещает новые replacement operations, но сохраняет новые таблицы и чтение
истории. Старые Cycles без доказуемой route position продолжают legacy read и не
получают угаданную позицию.
