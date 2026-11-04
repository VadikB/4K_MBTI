# PATH-START-01 — зависимость PM-03, не разрешение нового задания

Владелец 04.11.2026 выбрал передачу независимых PATH fixes с точным блокером;
доработку генерации согласовать отдельно. Новый prompt/repair/admission, публикация
артефактов, очередной платный run, merge и deploy этим документом не разрешаются.

## Факт

Real-provider run `aa2cbb221fdd458a8bb75e9a0faeb8b2` на clean
`a8d8fcff36eb81ff118c82676af6f9885bbbd4b7`, operation
`687295f9-7635-4fa6-b083-4db724749e92`. Exact release `specialist_pilot@1.1` /
config 11 / `specialist-pilot@1.0`, CASE.SPEC.02 v0.6. Source identity и 27 исходных
QA перепроверены, не заменены synthetic human_review диагностического каталога.

Автоматическая штатная PM-03 подготовка исполнила generation, tester, challenger,
единственный разрешённый repair и проверки конечного кандидата. 20 уникальных
provider operations, DeepSeek `deepseek-flash`; HTTP completions 20, JSON retry 0.
Финальный generation operation:
`687295f9-7635-4fa6-b083-4db724749e92:generation:repair:c7f75705b545`.
Candidate checksum/recomputed:
`56c303d1ed93170082eacabe3e75a84c5ea662d6499e749276e729488549543d`.

Admission **FAIL**, `admitted_for_participant=false`. Пять blocking checks:

- `indicator:K4.I13` — нарушено I05, B удовлетворяет всем существенным требованиям.
- `indicator:K4.I14` — отсутствует требуемая остаточная неопределённость рекомендации.
- `indicator:K4.I16` — сравнение альтернатив вырождается при доминировании B.
- `indicator:K4.I17` — не сохраняется неопределённость оценки рисков альтернатив.
- `critical_prohibition:02` — вариант с меньшим охватом стал гарантированно пригодным.

Конкретное основание checks: B — день 19 при дедлайне 20, проверенная совместимость,
охват 30 при минимуме 30, сопровождение; A — день 30 и неподтверждённая совместимость.
Это содержательное отклонение кандидата, не технический INCOMPLETE. В выгрузке
`deterministic_failures`, `deterministic_protocol_errors`, `incomplete_checks` пусты.
Почему разрешённый repair не сохранил инвариант — пока не установлено; дефект
исходного Case, prompt или алгоритма без отдельной диагностики не утверждается.

AS отсутствует. Cycle `f80c40bc-d45e-4e39-8b31-17019f27b023` и Session
`fe4425cf-51a2-4017-9f30-4009c56ce635` prepared, started_at=null, оценочных ответов 0.
Явный start и предъявление не выполнялись. Terminal export сохранён до штатного
cleanup owned-БД; секретов/state/raw provider messages в пакете нет.

## Первичные доказательства и неизвестное

[Receipt](../evidence/path-start-01/preparation-a8d8fcf/source-to-runtime-receipt.json),
[run](../evidence/path-start-01/preparation-a8d8fcf/run.json),
[runner result](../evidence/path-start-01/preparation-a8d8fcf/runner-result.json),
[cleanup](../evidence/path-start-01/preparation-a8d8fcf/cleanup.json).
Безопасные причины/paths/operation links сохранены; полный кандидат/raw prompts
не передавались. Старые assignment/time refs не были выгружены и после cleanup
не реконструируются. Расширение collector проверено отдельной бесплатной регрессией.

Исторический PREP-DIAG-01 (`c570a030-a47a-4eed-81f9-37c92e1441d8`, 4bab723,
INCOMPLETE) остаётся с первопричиной UNKNOWN. Новый FAIL и ошибки harness не
объявляются причиной старого INCOMPLETE. Восстановление БД — вне этой задачи.

## Предлагаемый предмет отдельного согласования

База: head `codex/path-start-01` из MANIFEST передачи (implementation 136b858),
не текущий main 7221671, в котором нет PATH target inputs и этих исправлений.
Владелец определяет scope и разрешённые изменения генерации/версий prompts, бюджет
и основание следующего real run. Методология/исходный допуск/repair сохраняются,
пока на их изменение нет самостоятельного нормативного решения.

После доказанного исправления — новый полный owned PATH на точном SHA: от
суперадмина до admission и явного первого start/AS при 0 ответов, с полным
profile/assignment/plan/time readback. Затем отдельные Ready/CI/release/deploy
решения. До этого полный PATH и приёмка развёрнутого пути BLOCKED.
