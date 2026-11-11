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

## Продолжение: PR и подготовка Ready

11.11.2026. Владелец прямым запросом разрешил `branch_push/pr`, затем отдельно
утвердил `version_bump` PATCH `2.0.95` и перевод PR в Ready. Прежние флаги выше
фиксируют границы этапа исполнителя. `merge/deploy/artifact_publish=false`.

PR [#208](https://github.com/VadikB/4K_MBTI/pull/208) создан как draft на
`c06ee5228ada2af15e3420b0fa45f1b938979e77`, base
`e6b294e43811fb67afb695506f15547e5efc5f9e`. Удалённый `main` повторно
сверен, быстрые CI `frontend` и `pytest` для этого SHA прошли.
`npm run ready:prepare -- --candidate 2.0.95` прошёл; изменены только файлы
версии `pyproject.toml`, `uv.lock`, `web/js/config.js`, `web/index.html` и
результат штатной сборки `web/dist`. Локально прошли `npm run lint:js`, 226
frontend-тестов, `scripts/check_release_version.py --base-ref origin/main` и
`git diff --check`. Исходные Api/tests не менялись после приёмки на SHA выше.

Подготовка версии закоммичена как `d3f2d81475757d8034aecd1c35fb887f566022b7`,
ветка отправлена, PR переведён в Ready. На этом SHA CI `frontend`, `pytest`,
integration и четыре из пяти browser shards прошли. Browser runtime shard 2/4
дважды остановился на существующем сценарии завершения AS из другой вкладки:
исходная вкладка уже показывала следующую ситуацию, тогда как общий helper
ожидал ответ `/finish-situation`. Артефакт CI показывает успешный переход из
другой вкладки и отсутствие POST `/finish-situation` из исходной.

В тесте после подтверждения перехода из другой вкладки добавлена перезагрузка
исходной вкладки перед продолжением общего helper. Предметный код и версия не
изменены. Адресный браузерный сценарий прошёл дважды на двух новых собственных
PostgreSQL (`exec05_pytest`), 1/1 PASS в каждом прогоне; обе БД остановлены.
Повторный `npm run ready:prepare -- --candidate 2.0.95` после правки теста —
PASS, версия и сборка не изменились; `check_release_version.py`,
`node --check tests/browser/runtime.spec.mjs` и `git diff --check` — PASS.

Следующий шаг: commit/push тестовой синхронизации и полный CI на новом SHA.
Human review и отдельное решение о merge остаются за владельцем.
