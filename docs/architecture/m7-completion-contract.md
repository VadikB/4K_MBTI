# Технический контракт M7 Completion and Continuation v1

Дата: 02.10.2026. Статус: **draft runtime**. Источники: M1 v1.4 §M1.6,
M7 v1.3 §§5.3–5.6, 7–8, Change 01 И-1/И-4/И-5 и ADR-002.

## Переходы и владельцы

PM-04 управляет сбором в существующих `m5_cycles`, `m5_cycle_sessions` и
`m5_assessment_situations`. Допустимы четыре завершающих команды:

| Команда | AS | Session | Cycle |
| --- | --- | --- | --- |
| `complete` | final close | completed | collection_closed |
| `final_refusal` | final close | completed | collection_closed |
| `time_limit` | final close | completed | collection_closed |
| `interrupt_for_continuation` | final close | interrupted | interrupted |

`scenario_end` оставляет AS открытой для Task 06. Окончательное прекращение active
или paused AS пишет `interaction_terminated`, затем `assessment_situation_closed`,
не создавая фиктивный `scenario_completed`. Только closed AS допускает final C-45.
Подготовленная, но не предъявленная AS закрывается как `not_presented` без C-45/IA.

Пауза и resume используют те же Session/Cycle и, при наличии открытой AS, тот же
Dialogue. Закрытые состояния не открываются повторно. Все команды сериализуются
блокировкой Cycle, имеют scoped idempotency key и неизменяемое событие перехода.

## Время и восстановление

Бюджет считается только по `collecting`-интервалам. `authorized_pause` и явно
открытый `blocking_system_wait` исключаются, но не продлевают календарный deadline.
Operation ref делает блокирующее ожидание идемпотентным. Worker каждые 30 секунд и
при старте приложения закрывает Cycles, достигшие бюджета или срока; все входы также
проверяют время синхронно. `effective_at` границы и `processed_at` события различны.

## Additional Session

Команда прерывания сохраняет continuation intent: исходный профиль, target-set,
Session, остаток и Cycle. Новая Session разрешена только для pending intent,
открытого interrupted Cycle, прежних profile/target checksums и действующих двух
лимитов. Intent потребляется один раз. Старые AS/Dialogue и IA не перепривязываются.

## Final C-45, outbox и C-46

Для каждой предъявленной закрытой AS создаётся неизменяемый final C-45 и запись
`m7_finalization_outbox`. Она отделяет commit закрытия от обработки PM-05. На текущем
SHA M6 product-dispatch отсутствует: QA M6 не используется как скрытый fallback,
поэтому product outbox остаётся `pending` до отдельного допуска M6.

C-46 revision 1 фиксирует Cycle, цель/план, полный target-set, Sessions/AS, Case и
final C-45 refs, интервалы, оба лимита и источники, причину закрытия, точный состав и
`calculation=pending`. Reconciliation создаёт новую revision только при совпадении
Cycle и composition checksum; coverage и четыре Skill outcome поступают от PM-05,
M7 их не пересчитывает. Несовпадение возвращает `COMPOSITION_MISMATCH`.

## API, совместимость и откат

Product-owned API предоставляет status, pause/resume, completion и Additional
Session, проверяя owner и assessment scope. Служебный C-46 и blocking waits доступны
только существующему superadmin. Legacy `user_sessions` не переименован в M7 Session.

Откат останавливает worker и новые команды, сохраняя события, C-45, outbox и C-46.
Закрытые Cycle не открываются; незавершённую PM-05 обработку можно продолжить по
сохранённому outbox после восстановления совместимого consumer.
