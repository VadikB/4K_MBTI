# CI-PAR-01: параллельная проверка Pull Request

## Результат

Полный обязательный CI сохраняет прежнее покрытие, но unit/HTTP, integration и
browser acceptance выполняются параллельно. Browser acceptance делится на два
автоматических Playwright shard. Устаревший незавершённый run того же PR отменяется.

## Область

- Включено: `.github/workflows/backend-tests.yml`, эксплуатационная документация
  тестов и матрицы проверок.
- Не входит: отключение полного post-merge CI, изменение branch protection,
  merge queue, deploy-процедуры, продуктовый runtime и тестовые сценарии.

## Контекст

- Основание: запрос владельца от 2026-10-30 проверить дублирование pytest и
  оптимизировать длительную сборку; продолжение «можешь сделать?».
- Base: `origin/main`, commit `13e77ef2abebfe1be40d497963d80045db282e04`.
- Наблюдение: в исследованных PR/main runs последовательный `pytest` занимал
  9–12 минут; browser acceptance — около 6–7 минут, integration — 2–4 минуты.
- Значимые точки входа: `.github/workflows/backend-tests.yml`,
  `playwright.config.mjs`, `tests/browser/README.md`.
- Архитектура/ADR/PM/LU: неприменимо; предметная логика и данные продукта не меняются.
- Публичный API, схема БД, snapshots и артефакты методологии не затронуты.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
  `docs/evc/task-template.md`, `docs/evc/review-checklist.md`, `tests/README.md`,
  `tests/browser/README.md`, workflow и browser specs на указанном base commit.
- Решение владельца: выполнить безопасную первую стадию оптимизации без ослабления
  обязательной проверки до и после merge.
- Существующее имя обязательного check `pytest` сохраняется агрегатором, чтобы
  изменение не требовало синхронной перенастройки branch protection.
- Browser shards формируются Playwright автоматически; новый spec не требует
  ручного включения в одну из групп.
- Стоп-условия: нет. Миграции, персональные данные, секреты и новые внешние сервисы
  отсутствуют. Отмена post-merge полного набора остаётся отдельным решением владельца.

## План и состояние

- Завершено: анализ двух GitHub Actions runs; выбор совместимой структуры jobs;
  реализация и локальная валидация workflow/docs.
- Активный шаг: PR и фактический GitHub CI для измерения wall-clock времени.
- Следующий шаг: review результата и решение владельца о merge.
- Ветка: `codex/ci-parallel-tests`.

## Действия выпуска

- `branch_push=true`: после локальных проверок.
- `pr=true`: отдельный PR для review и измерения CI.
- `merge=false`.
- `deploy=false`.
- `version_bump=false`: меняются только `.github/`, `tests/` и `docs/`, что
  классифицируется release guard как непроизводственное изменение.
- `artifact_publish=false`.

## Ограничения и риски

- Совместимость: обязательные внешние checks остаются `frontend` и `pytest`.
- Данные: каждый parallel job получает отдельный runner и PostgreSQL service;
  рабочие/test-данные системы не используются.
- Производительность: runner-minutes могут вырасти из-за повторной установки
  зависимостей, ожидаемое сокращение относится к wall-clock времени PR.
- Внутри каждого browser runner сохраняется `workers=1`; Playwright распределяет
  spec-группы между изолированными runners без изменения порядка внутри файла.
- Фактический выигрыш и корректность GitHub expression проверяются только реальным CI.

## Критерии приёмки

- [ ] `backend`, `integration` и два экземпляра `browser` стартуют независимо.
- [x] Каждый browser-тест входит ровно в один shard, evidence загружается раздельно.
- [x] `pytest` успешен только при успехе всех параллельных тестовых jobs.
- [x] `deploy-test` по-прежнему зависит от `frontend` и итогового `pytest`.
- [ ] Новый commit в открытом PR отменяет его незавершённый устаревший run.
- [ ] Product code, schema/API и состав тестовых сценариев не изменены.

## План проверки

- `git diff --check`.
- Проверка YAML парсером и адресная проверка workflow/deploy-теста.
- `npx playwright test --list --shard=1/2` и `--shard=2/2`: непересекающееся
  объединение равно полному `npx playwright test --list`.
- `python scripts/check_release_version.py --base-ref origin/main`.
- Фактический GitHub CI PR: все jobs PASS, сравнение длительности с исходными runs.

Локальные результаты на рабочем diff:

- YAML parse — PASS.
- `tests/unit/test_test_deploy_bootstrap.py tests/unit/test_release_version.py` —
  23 PASS за 39.17 s.
- Playwright list/shards — PASS: полное множество 85, shard 1 — 70,
  shard 2 — 15, diff объединения с полным списком пуст.
- Release guard — PASS, `2.0.38`; version bump не требуется.
- `git diff --check` — PASS.

## Откат

Revert одного commit возвращает последовательный job `pytest`, единый browser run
и прежнюю concurrency-схему. Данные и миграции при откате отсутствуют.
