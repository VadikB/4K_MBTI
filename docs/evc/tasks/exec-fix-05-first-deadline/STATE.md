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

Промежуточно: 17 unit FIX04/FIX05 PASS; 26 actual PG/HTTP FIX04/FIX05 PASS.
Новые дополнительные регрессии открытого интервала и двойного отказа добавлены.
Независимое read-only review: блокирующих замечаний нет.

Активно: проверка точного candidate SHA полным backend/HTTP и адресными M5/M7
integration; затем bundle/независимый импорт и завершённая передача архитектору.
Финальные SHA/результаты/хеши хранятся в HANDOFF внешнего пакета
`outputs/p4k-exec-fix-05-20261111` рабочего пространства пользователя.
В этой ветке допускаются внутренние шаги; другая ветка для них не создаётся.

`branch_push/pr/merge/deploy/version_bump/artifact_publish=false`.
Paid LLM/shared TEST/Prod не использовались. Временные собственные PG остановлены;
диагностика сохраняется. CI/human review/release preflight — этап архитектора.
