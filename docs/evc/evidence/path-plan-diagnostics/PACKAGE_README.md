# Независимая проверка пакета диагностики и проекта

Этот пакет не разрешает старт, публикацию или платный прогон. Включены проверенный
tests-only collector, профиль/runner/fixtures, исходные receipts/logs/cleanup,
история изменений относительноde3b831 и конкретный проект PATH-PILOT-01 v0.1.
M2=61 сохраняется;39 целей и восемь позиций — предложение на review, не допуск.

После распаковки из корня (Python3, стандартная библиотека; БД/ключи не нужны):

```sh
python3 docs/evc/evidence/path-plan-diagnostics/VERIFY.py
python3 docs/evc/evidence/path-plan-diagnostics/CHECK_PILOT_REVIEW.py
```

Ожидается PASS_OFFLINE_DIAGNOSTICS_AUDIT_NOT_PATH и
PASS_OFFLINE_REVIEW_STRUCTURE_NOT_ADMISSION, human approval PENDING.
Проверяются hashes всех файлов MANIFEST, первичная диагностика/cleanup43d5ca0…,
неизменённый отрицательный run96abd1…, source replay61/55/39/22, переход
author content0.3→0.5 и десять отрицательных mutations. Это не выполнение LLM/БД
и не повтор первоначальных773/108/43/48/38 tests: их журналы сохранены с областью.

Читать решения: docs/evc/reports/path-pilot-admission-proposal.md §7.
Продуктолог P1–P3; методолог M1–M4; технический контракт T1 и release/run R1 —
следующие отдельные ворота. Подписантов/методологический PASS пакет не выдумывает.
Проект JSON/Markdown не загружается как runtime configuration.

MANIFEST-de3b831.json — прежний неизменённый индекс. Текущий MANIFEST.json относится
к этой передаче. Исходные незакоммиченные diff сохранены в resume-*.patch.gz:
gzip распаковывается без изменения bytes, проверяются исходные hashes. Старый
вариант расширения каталога SUPERSEDED_NOT_STARTED, а не реализованная миграция.

Корневые source.bundle / diff-after-2dc98c6.patch и BUNDLE.json добавляются из
exact final handoff SHA. Bundle **incremental**, prerequisite commit
2dc98c6b5b2637c6c505a90686e82f5e4274e763; не выдаётся за standalone clone.
В имеющемся checkout, содержащем этот base:

```sh
git bundle verify /absolute/path/source.bundle
git fetch /absolute/path/source.bundle HEAD
git worktree add --detach /absolute/path/new-review-worktree FETCH_HEAD
```

Source/evidence из ZIP проверяются без восстановления Git. Для запуска всего
продукта нужен полный base checkout и штатные зависимости. RUN_FREE.py использует
существующий guarded test_stand и provider disabled; не запускать его на рабочей БД.
Новых DB/LLM/публикаций/merge/deploy текущая передача не содержит. PREP-DIAG-01 UNKNOWN.
