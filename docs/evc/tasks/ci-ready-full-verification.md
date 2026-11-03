# CI-READY-FULL-VERIFICATION — полный CI только для Ready PR

## Результат

Draft PR получает быстрые проверки `frontend` и `pytest`, а дорогой
`full-verification` выполняется только для Ready PR и актуального head.

## Область

- Включено: события и условие workflow `Full verification`, отмена устаревшего
  прогона одного PR, регрессионные тесты конфигурации, описание процесса.
- Не входит: состав тестовых наборов, параллелизация jobs, кэширование браузера,
  изменение обязательных checks ruleset, merge, deploy и product version bump.

## Контекст

- Основание: явное решение владельца от 2026-11-03 сократить повторные полные
  прогоны: полный набор при `Ready for review`, быстрые проверки в draft.
- Значимые точки входа: `.github/workflows/full-verification.yml`,
  `.github/workflows/backend-tests.yml`.
- Архитектура/ADR: предметные контракты и PM/LU не затрагиваются; изменение
  относится к CI и процессу передачи результата.
- Существующие тесты: `tests/unit/test_ci_verification_workflows.py`.
- Прослеживаемость: решение владельца → правило Ready/Draft → workflow condition
  → unit-проверка конфигурации → обязательный GitHub check.

## Источники и решения

- Прочитано на commit `eafb0f9`: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`,
  `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
  `docs/evc/task-template.md`, `docs/evc/review-checklist.md`, `tests/README.md`,
  оба CI workflow и тест конфигурации.
- Пробел: локально нельзя доказать обработку события GitHub; фактическое поведение
  проверяется на Draft PR и после перехода в Ready.
- Принятое решение: сохранять обязательный check `full-verification`, запускать
  его при `draft == false` на `opened`, `reopened`, `synchronize` и
  `ready_for_review`; отменять предыдущий незавершённый прогон того же PR.
- Стоп-условия: миграции, публичный API, предметные нормы, данные и секреты не
  затронуты. Управляющие документы меняются отдельной явно согласованной задачей.
- Требуется решение владельца: нет.

## План и состояние

- Завершено: разведка, реализация, регрессионные тесты и локальная проверка.
- Активный шаг: Draft PR и проверка быстрых checks.
- Следующий шаг: перевод в Ready и подтверждение
  обязательного полного прогона.
- Ветка: `codex/ci-ready-full-verification` от `origin/main` (`eafb0f9`).

## Действия выпуска

- `branch_push=true`
- `pr=true`
- `merge=false`
- `deploy=false`
- `version_bump=false`
- `artifact_publish=false`
- Основание `branch_push` и `pr`: подтверждение владельца «давай так сделаем»
  после предложения оформить отдельное изменение процесса и ruleset.
- `npm run ready:prepare` не применяется: product-файлы и версия не меняются.

## Ограничения и риски

- Совместимость: required check сохраняет прежнее имя; ruleset не ослабляется.
- Данные, миграции, персональные данные, LLM: не затрагиваются.
- Эксплуатация: ошибки integration/browser обнаруживаются позже — при Ready, а не
  на промежуточном draft commit. Новый Ready commit снова запускает полный набор.

## Критерии приёмки

- [ ] Draft PR запускает `frontend` и `pytest`, но не исполняет полный набор.
- [ ] Переход в Ready запускает `full-verification` актуального head.
- [ ] Новый commit Ready PR повторяет полный набор, а устаревший прогон отменяется.
- [x] Required checks ruleset `frontend`, `pytest`, `full-verification` сохранены:
  имя job и настройка ruleset не меняются.
- [x] Предметное содержание и исторические snapshots не затронуты.

## План проверки

- `git diff --check`.
- `.venv/bin/python -m pytest tests/unit/test_ci_verification_workflows.py`.
- Содержательное review workflow и согласованности документации.
- GitHub: Draft PR, затем `Ready for review`; merge/deploy не выполнять.

## Откат

Revert PR возвращает запуск `full-verification` на каждый head Draft и Ready PR;
данные и опубликованные артефакты не изменяются.
