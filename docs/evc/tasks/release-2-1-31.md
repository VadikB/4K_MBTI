# Общий выпуск 2.1.31 на test

## Решение владельца и план

05.10.2026 пользователь поручил: «делаем PR по всем последним 7 задачам,
заливаем на test, увеличиваем номер версии». Это явный допуск общего PR и test-выпуска
через штатный squash merge в main и автоматический CI/deploy. Допуск пилота или
нормативное принятие предметных решений не следует из этого поручения.

Состав: REV-01–04 (`c48e331`), 10.4 (`6764131`), 10.5 (`b733807`),
11.2 (`010c2b3`), 10.6 (`d575274`), 8.1 (`80505e0`), 10.7 (`0690e87`).
Main после fetch: `8654b97ed6605d560111c37cd291f98f82c41457`.
Общая ветка: `codex/release-2-1-31`, исходный head `0690e879011cddce693ab90372caad916b12a7da`.

План: состав/версия → bump/build/local checks → общий PR в main → CI точного head →
squash merge по текущему поручению владельца → main CI/deploy → HTTP version/health.
Активный шаг: подготовка общего PR. Итоговые SHA/CI/deploy-ссылки фиксируются в PR,
чтобы не менять проверенный head ради само-ссылки в документе.

## Изменения и источники

Релизные метаданные 2.1.30→2.1.31: pyproject.toml, uv.lock, web/js/config.js;
пересобран web/dist. Прикладной код сверх уже проверенного пула не изменён.
Прочитаны README (версии/рестарт), CONTRIBUTING (PR/squash/test), bump_version.py,
app_version.py, deploy_test_remote.sh, workflow backend-tests.yml;
EVC workflow/matrix/artifact recipe и источники пула переиспользуются из 10.7.
[Отчёт 10.7](task10-7-integrated-product-acceptance.md) и его source checksums сохраняются
исторически; release manifest переснимается для новой сборки.

## Проверки и ограничения

- Пул на 0690e87: 362 unit, 40 HTTP, 92 integration, 4 frontend, 11 browser PASS;
  [PR CI](https://github.com/VadikB/4K_MBTI/actions/runs/37365920378) и
  [push CI](https://github.com/VadikB/4K_MBTI/actions/runs/37365913360) PASS.
- Новый release bump: lint, frontend 4, build, согласованность backend/frontend/lock PASS;
  web/dist — новый bundle 2.1.31. Diff проверяется перед коммитом.
- Полный CI повторяется на release head и затем main; предыдущий зелёный CI не
  приписывается новому SHA. Развёртывание считается завершённым только после проверки.

Предметные ограничения G08/G11/G12, экспертные заключения, approved GC и
Reliability=not_verified сохраняются. Рабочие данные и секреты не читаются.
Самостоятельной публикации кейсов, правки FROZEN, изменения порогов, миграции рабочих
данных и включения платного provider нет. Действующий runtime admission остаётся.

## Риски и откат

Одна согласованная test-сборка семи задач. Продуктовый manifest/схема не меняются
ради выпуска; данные snapshots/IA/Results/C67 сохраняются. Runtime release version
кешируется процессом, поэтому штатный deploy обязательно перезапускает test-service.
Deploy выполняется GitHub Environment test, не ручной загрузкой файлов.
Скрипт сохраняет предыдущий commit и frontend chunks и откатывается при ошибке smoke.
При дефекте уже принятого выпуска — отдельный revert PR; исторические данные не удаляются.

Управляющие документы не менялись; новых стоп-условий выпуска не выявлено.
Проверенные ранее предметные блокеры не снимаются этим техническим выпуском.
