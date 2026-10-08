# M8 Partial Result Contract

Версия `m8-partial-result/1.0.0`, WORKING. Контракт не меняет M6 outcomes и не
присваивает методологии CURRENT.

`partial_result.progress.completed/planned` — число AS с final C-45 handoff / число
элементов frozen route принятой plan revision. `presented`, `interrupted` и
`not_presented` выводятся из lifecycle AS; число Turns в формуле не участвует.
Уменьшение текущего route не меняет сохранённый знаменатель старого Cycle.

Причины независимы: `plan_scope`, `collection_incomplete`, `observation_missing`,
`context_limited`, `technical_failure`. Отсутствие наблюдения не равно L0. Частный
Score, качественный IA без Score и `no_result` сохраняют исходные M6 значения.

Новая оценка создаётся только явным `POST /assessment/cycles/start`. GET/status
возвращает описание действия, но ничего не создаёт. POST повторно проверяет active
organization membership, выбранный profile/BaseRole, configuration и catalog; новый
Cycle не меняет snapshot, Results или Report прежнего Cycle.
