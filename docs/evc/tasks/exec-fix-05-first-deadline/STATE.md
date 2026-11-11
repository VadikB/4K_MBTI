# P4K-EXEC-05-USER

11.11.2026. Единственный исполнитель изменений — мой Codex.
Ветка `codex/exec-fix-05-first-deadline`, worktree
`/private/tmp/USER_WORKTREES/exec-fix-05-first-deadline`.
Base/fresh remote main `e6b294e43811fb67afb695506f15547e5efc5f9e` / 2.0.94.
Источники/план/полномочия: [карточка](../exec-fix-05-first-deadline.md).

На исходном main независимая собственная PG проба воспроизвела неверный
calendar-first при более раннем бюджете (ошибка effective_at +4 секунды).
Реализация вычисляет обе границы по единому DB clock после lock, сравнивает
точные timestamps и сохраняет календарный приоритет равенства. Только collecting
с точным timedelta; допуск M5/M7, replay, R1 и исторические Cycle не изменены.

Код и локальная приёмка завершены. Source/full-suite tested SHA
`4c96732080b3d45177d8d86a8a905e792e886aac`: backend 1065 PASS; HTTP 144 PASS;
адресные PG 127 PASS, затем FIX02 25 PASS. Первый combined PG-прогон содержал
25 setup errors: существующий stand требует разрешённую служебную БД.
Отдельный повтор FIX02 на новой собственной `agent4k_pytest` через неизменённый
test_stand дал 25 PASS; guard/schema/права не ослаблены. Ошибочный лог сохранён.
Новые 10 unit и 23 PG/HTTP регрессии входят в эти наборы; предварительные
17/26 PASS не прибавляются повторно. Исходная probe after — 3/3 PASS;
фактические HTTP/readback — 6/6 PASS с сохранёнными event/C46 и timestamps.
Независимые read-only code/source/acceptance review: блокирующих замечаний нет.
Этот завершающий коммит меняет только STATE, bytes Api/tests прежние.

Передача: bundle, PR description, before/after, команды/результаты, зависимости,
checksums и независимый импорт. Финальные candidate/tested SHA и область
проверок каждого SHA хранятся в HANDOFF внешнего пакета
`outputs/p4k-exec-fix-05-20261111` рабочего пространства пользователя.
В этой ветке допускаются внутренние шаги; другая ветка для них не создаётся.

`branch_push/pr/merge/deploy/version_bump/artifact_publish=false`.
Paid LLM/shared TEST/Prod не использовались. Временные собственные PG остановлены;
диагностика сохраняется. CI/human review/release preflight — этап архитектора.
