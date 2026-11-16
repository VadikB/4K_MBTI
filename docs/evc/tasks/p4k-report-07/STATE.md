# STATE — P4K-REPORT-07

- Base `6c67dd74`; ветка/worktree `codex/p4k-report-07` / `worktrees/p4k-report-07`.
- Разведка и проверяемая таблица допуска записаны до изменения runtime. SHA источников M6 v1.8, M8 v1.2 и Change 01 совпали с manifest.
- Реализованы адресный допуск по Skill, выбор пары по времени закрытия, отображение программ/дат, две серии шкал и причины, устойчивая смена выбора, PDF из той же пары. Редакции Report не создают новые прохождения.
- Кандидат `2.1.20` подготовлен штатной `npm run ready:prepare -- --candidate 2.1.20` после сетевого fetch `origin/main=6c67dd74`.
- Локальные проверки: backend 1133 PASS (первый sandbox run 1123 PASS/9 `ps` PermissionError; повтор всех 19 synthetic-limits и финальный полный run с разрешённым subprocess PASS), frontend 354 PASS, адресные unit/HTTP 27 PASS, PostgreSQL15 integration 3 PASS, browser 1 PASS с тремя состояниями и снимками 1440/390, release unit 11 PASS, lint/build/diff PASS. Подробности — `CHECKS.md`.
- PR [#236](https://github.com/VadikB/4K_MBTI/pull/236) открыт из опубликованной ветки `codex/p4k-report-07`.
- CI head `cb46b67a`: 9 successful, 1 skipped (PR deploy), обязательный `full-verification` PASS. Дополнительно проверена раскладка при 683 CSS px (эквивалент 1366 px / 200%), снимок в `evidence/comparison-200pct-equivalent.png`. Изменённый head требует повторного CI.
- Открыто: человеческая визуальная приёмка и TEST/Prod release. Синтетические fixtures не доказывают развитие человека или содержательную валидность M6.
- Следующий шаг: дождаться обязательного CI и review; merge/deploy отдельно по действующему release gate.
- `branch_push=true`, `pr=true`, `merge=false`, `deploy=false`, `version_bump=true`, `artifact_publish=false`.
