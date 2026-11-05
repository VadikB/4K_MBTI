# Параллельная подготовка пакетов и последовательный выпуск

## Результат

Производственный процесс допускает 2–4 независимо подготовленных пакета в отдельных
worktree и PR, автоматически показывает риск и пересечения файлов, но сохраняет
последовательными обновление от `main`, merge, версионирование и deploy.

## Область

- Включено: Git/worktree-процесс, `depends_on`, риск по путям, обнаружение пересечений
  открытых PR, merge queue/current-main gate, изоляция CI-БД и deploy concurrency.
- Не входит: включение branch protection/merge queue в настройках GitHub, merge,
  release/deploy, изменение приложения, методологии, данных или публичного API.

## Контекст

- Основание: явное решение владельца в запросе от 2026-11-04 изменить процесс.
- Значимые точки входа: `CONTRIBUTING.md`, `.github/PULL_REQUEST_TEMPLATE.md`,
  `.github/workflows/backend-tests.yml`, `.github/workflows/full-verification.yml`,
  документы EVC.
- Архитектура: процессная задача; PM/LU и предметные контракты не затрагиваются.
- `depends_on`: `[]`.
- Ветка / worktree: `codex/process-parallel-delivery` /
  `worktrees/process-parallel-delivery`.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
  `docs/evc/task-template.md`, `docs/evc/review-checklist.md`, архитектурный контекст
  1.0 и Registry, Change 01 route/manifest, текущие workflow и PR-шаблон; первоначальная
  база `717bff56a69c2674434bc20434475d29d3a97d4e`, перед PR пакет перенесён на актуальный
  `origin/main`.
- Пробел: серверные настройки GitHub нельзя зафиксировать diff репозитория; их
  включение остаётся операционным шагом владельца репозитория.
- Решение владельца: модель из запроса применяется как новое правило процесса.
- Дополнение владельца от 2026-11-04: на текущем этапе отменить обязательное ручное
  review при приёмке PR; self-review и автоматические gates сохраняются.
- Стоп-условия: все «нет»; предметные нормы, данные, права и граница deploy не меняются.

## План и состояние

- Завершено: разведка и фиксация отдельного worktree.
- Активный шаг: документы, автоматический PR-анализ и CI-конфигурация.
- Следующий шаг: локальная проверка → PR → включение merge queue/required checks.
- Связанные PR: отсутствуют на момент реализации.

## Ограничения и риски

- Совместимость: `merge_group` добавляется к существующим `push`/`pull_request`.
- Данные: каждый CI run получает уникальное имя PostgreSQL test-БД; схема приложения
  не меняется.
- Безопасность: PR-анализ использует только `contents: read` и `pull-requests: read`.
- Эксплуатация: пересечение файлов сигнализируется, но не заменяет `depends_on` и
  self-review.

## Критерии приёмки

- [x] Задача/PR содержат явный `depends_on`, класс риска и ожидаемые проверки.
- [x] Каждый пакет работает в отдельном worktree; одновременно активны обычно 2–4.
- [x] CI PR автоматически классифицирует пути и перечисляет пересечения с открытыми PR.
- [x] `merge_group` запускает обязательные проверки; перед прямым squash merge нужен
      актуальный `main` и повторный gate.
- [x] Integration job использует уникальную test/pytest-БД, deploy не отменяет проверки.
- [x] Версия и deploy выполняются последовательно ответственным за выпуск.
- [x] Ручное review/approval не блокирует приёмку PR на текущем этапе; обязательны
      self-review, CI и остальные gates, а решения владельцев и допуск выпуска сохранены.

## План проверки

- `node --test tests/process/pr_coordination.test.cjs`.
- Разбор YAML workflow и проверка ссылок/согласованности документов.
- `git diff --check`.
- Полный CI актуального PR обязателен перед merge.

## Откат

Revert squash-коммита процесса возвращает прежние документы и workflow. Изменение
не мигрирует данные; настройки merge queue/required checks откатываются отдельно
в GitHub владельцем репозитория.

## Отчёт реализации

- Изменены процессные документы, PR-шаблон и CI; добавлены чистые функции анализа
  риска/пересечений и их регрессия.
- После дополнения владельца ручной approval исключён из PR gate; это не отменяет
  человеческие стоп-решения, выпуск, предметную/стендовую приёмку и baseline.
- `node --test tests/process/pr_coordination.test.cjs` → PASS, 2 tests.
- `ruby -e "require 'yaml'; YAML.load_file(...)"` → PASS (`workflow_yaml_ok`).
- `git diff --check` → PASS.
- `npm run ready:prepare` → первоначально корректно запросил `2.0.62`, пока CI-only
  анализатор находился в product-каталоге `scripts/`; анализатор перенесён в
  `.github/scripts/`; повторный прогон → PASS: `no product release change`.
- `python3 -c "import yaml; ..."` → NOT_RUN: в локальном Python отсутствует PyYAML;
  синтаксис проверен доступным Ruby Psych, установка зависимости для docs/CI-задачи
  не требуется.
- GitHub CI/фактический `merge_group`, merge queue и deploy → NOT_RUN до PR/настройки
  репозитория. Это не позволяет сливать пакет до зелёных `coordination`, `frontend`,
  `pytest`, `full-verification` на актуальном head/base.
- Риски: схема/API/предметные артефакты/секреты не меняются; post-merge deploy остаётся
  отдельным последовательным workflow; откат — revert пакета и, если включены, возврат
  GitHub settings.
- Следующий шаг: владелец репозитория создаёт PR, делает четыре jobs required и включает
  merge queue (либо сохраняет обязательный current-main gate), а в branch protection
  устанавливает required approving reviews = 0.
- Открытые вопросы: нет; операционное включение GitHub settings остаётся post-merge
  действием владельца, не блокером реализации репозиторного пакета.
