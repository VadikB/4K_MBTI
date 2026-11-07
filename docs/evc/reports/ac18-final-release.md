# AC18-FINAL-REL-01 — подготовка единого выпуска

07.11.2026. В работе; финальный номер/PR/head ещё не зафиксированы.

| Контур | Результат |
| --- | --- |
| Полный PATH ветки38bf8244 | PASS: generation/tester/challenger, AS admission PASS, start201, первая AS, ответов0 |
| Primary evidence |64 original files/hashes,27 visual reviews, independent cleanup readback PASS |
| Адресные runner/release regressions до bump |24 PASS на runtime38bf8244; новый primary JUnit |
| Документальные проверки |10 local links, diff-check и повтор offline verifier PASS |
| Свежий main/test |339aff9034ff005bc20d072876b3fbef4f834c5e /2.0.74, новый fix не deployed |
| Release preflight |exit2: требует отдельного утверждения PATCH2.0.75; ожидаемый stop, файлы версии не менялись |
| Новый CI/review/merge/deploy |NOT_RUN; человеческий code review не подменяется branch acceptance |

Границы/прочитанные источники/проверки/stop conditions/откат —
[карточка](../tasks/ac18-final-release.md). Уже реализованный code c4a6a0c не менялся.
В этом шаге добавлены сохраняемые в Git оригинальные64 JSON/PNG и offline verifier;
исходный sidecar package, негативный run и прежние документы не переписаны.
[Прямые evidence и команды](../evidence/ac18-branch38-path/README.md).
[Release-preflight/JUnit](../evidence/ac18-final-release/README.md).

Применимые127 browser/146 frontend/956 backend/108 HTTP PASS и lint/build/idempotency
сохранены для неизменённого runtime tree; текущий run доказывает actual HTTP/PG/LLM,
не synthetic resolver. Точный final released SHA и readback ещё NOT_RUN.
Следующий шаг: решение владельца номера, canonical preparation и бесплатные release
checks → commit/push/PR/mandatory CI → человеческое review. Никаких новых платных
run, публикаций или промежуточных deploy. PREP-DIAG-01 отдельно UNKNOWN.
