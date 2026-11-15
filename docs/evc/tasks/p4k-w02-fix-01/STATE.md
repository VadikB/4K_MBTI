# STATE — P4K-W02-FIX-01

Base e8773ca80b9e3089a0faec16e9722680d126d8bb, codex/p4k-w02-fix-01.
Активно: UI/регрессии; candidate/tested SHA ещё не назначены, PR не создан.
Флаги и прямое полномочие — TASK.md. Merge/deploy запрещены этим этапом.
node_modules/.venv — ссылки на уже настроенные зависимости W02-02.
Своих временных серверов/БД/контейнеров пока нет. LLM/письма=0.
Следующее: штатный bounded browser, восемь снимков и сравнение HTML.

Перед browser01: run ID `w02-fix-browser01`; штатный runner
`python3 /private/tmp/p4k-w02-fix-browser.py browser01 ...`.
Owned process registry/evidence фиксируются до исполнения; статус/stop — plan.json.
Порты: ephemeral W02, 18764 auth; БД/контейнеры отсутствуют; restart=no.
Runner SYN-LIMITS run_bounded 600s/90s, reporter прогрессирует только по тестам.
Критерий cleanup: owner registry absent + записанные server stop + закрытые порты.

Локальный этап завершён, candidate2.1.10, fresh basee8773ca.
Runtime SHA256 — evidence/checked-content.json. Lint/build/diff-check PASS,
frontend333/333 PASS. Browser06:43PASS/1FAIL (RAF focus race в тесте);
browser07 после точного исправления ожидания:3width PASS; все44 выбранных
сценария подтверждены на том же runtime. Подробная AC/visual матрица — CHECKS.
Шесть own групп absent, recorded ports closed; noDB/noLLM/noletters.
Активно: commit/push/Ready PR и CI точного head. Human TEST PENDING.
