# AC18-FINAL-REL-01 — подготовка единого выпуска

07.11.2026. Владелец отдельно утвердил2.0.75(PATCH). Локальный release-кандидат
готов; PR/head и mandatory CI фиксируются после push. Человеческое review ещё не пройдено.

| Контур | Результат |
| --- | --- |
| Полный PATH ветки38bf8244 | PASS: generation/tester/challenger, AS admission PASS, start201, первая AS, ответов0 |
| Primary evidence |64 original files/hashes,27 visual reviews, independent cleanup readback PASS |
| Адресные runner/release regressions до bump |24 PASS на runtime38bf8244; новый primary JUnit |
| Документальные проверки |10 local links, diff-check и повтор offline verifier PASS |
| Свежий main/test |339aff9034ff005bc20d072876b3fbef4f834c5e /2.0.74, новый fix не deployed |
| Release preflight |2.0.75 PASS дважды,45 build hashes byte-idempotent; исходный exit2 сохранён как история |
| После bump |frontend146/receipt66/runner-release24/browser9 PASS, lint/release/diff PASS |
| Применимость branch-PASS |18 runtime hashes неизменны,4 metadata version-only;45 modules/import graph эквивалентны |
| Новый CI/review/merge/deploy |NOT_RUN; человеческий code review не подменяется branch acceptance |

Границы/прочитанные источники/проверки/stop conditions/откат —
[карточка](../tasks/ac18-final-release.md). Уже реализованный code c4a6a0c не менялся.
В этом шаге добавлены сохраняемые в Git оригинальные64 JSON/PNG и offline verifier,
release metadata pyproject/uv.lock/APP_RELEASE/entry и generated dist;
исходный sidecar package, негативный run и прежние документы не переписаны.
[Прямые evidence и команды](../evidence/ac18-branch38-path/README.md).
[Release-preflight/JUnit](../evidence/ac18-final-release/README.md).

Применимые127 browser/146 frontend/956 backend/108 HTTP PASS и lint/build/idempotency
сохранены для неизменённого runtime tree; текущий run доказывает actual HTTP/PG/LLM,
не synthetic resolver. Точный final released SHA и readback ещё NOT_RUN.
Локальный UI review агента: pending hidden/disabled +submit guards fail-closed;
own validation generation не сбрасывает parent auth generation; late response guards
остаются, reset retry работает; expected email/name/type/step проверяются helper.
Это не человеческое принятие. Primary auth-run root UNKNOWN/causal identity NOT_PROVEN.

Initial free-check launcher failures (old system Python/неверный CLI/нет worktree .venv)
сохранены; с существующим parent CLI и BROWSER_PYTHON финальный9PASS. Product assertions
не менялись. Полные команды/сфера применимости — release evidence README.

Следующий шаг: release commit/push/PR/mandatory CI → человеческое review. Никаких новых платных
run, публикаций или промежуточных deploy. PREP-DIAG-01 отдельно UNKNOWN.
