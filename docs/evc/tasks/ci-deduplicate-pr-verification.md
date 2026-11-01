# CI: устранение повторного выполнения PR-проверок

## Основание и границы

- Решение владельца: оптимизировать повторные CI-запуски между публикацией PR и merge.
- База: `main` / `1abb9cf71212ed2be214bd74267daebd070f942b`.
- Включено: workflow, регрессия CI-контракта и согласованная документация.
- Не включено: product runtime, branch ruleset, release/version, deploy и предметные артефакты.

## Решение

1. `pytest` остаётся единственным владельцем unit и HTTP/e2e.
2. `full-verification` выполняет только integration и browser acceptance.
3. Новый commit (`opened`, `reopened`, `synchronize`) запускает быстрый и полный CI.
4. Draft → Ready на том же SHA повторяет быстрые jobs и release gate, но переиспользует полный check точного SHA.
5. `converted_to_draft` не запускает проверки: код и SHA не изменились.
6. Обязательные check names `frontend`, `pytest`, `full-verification` сохранены.

## Безопасность и откат

- Failed/pending `full-verification` не заменяется новым skipped-check при Ready: workflow на это событие не запускается.
- Любой новый commit инвалидирует прежний полный check и запускает его снова.
- Откат: revert workflow и документации; данные и runtime не затрагиваются.

## Проверки

- YAML parse обоих workflow — PASS.
- `tests/unit/test_ci_verification_workflows.py`, `tests/unit/test_release_version.py`, `tests/unit/test_test_deploy_bootstrap.py` — 28/28 PASS.
- `git diff --check` — PASS.

## Состояние передачи

- Ветка: `codex/ci-deduplicate`.
- Изменения не закоммичены, version bump не выполнялся.
- Следующий шаг: review diff, commit, draft PR и фактическая проверка матрицы запусков GitHub Actions.
