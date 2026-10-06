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

## Диагностика release CI

PR #39 создан в main; технический дубликат #40 закрыт. Push CI 37367840930
на 55a0276: frontend/unit/HTTP/integration PASS, browser 10 PASS / 1 FAIL.
Recovery-сценарий не дождался подтверждения профиля после смены аккаунта
при второй открытой вкладке. Слияние ожидает исправления и зелёного CI.

Прочитаны tests/browser/runtime.spec.mjs, web/js/api.js, session.js,
main.js и polling в screens/interview.js; правила EVC переиспользованы.
План: воспроизвести отложенный реальный 401 во второй вкладке после нового
login; проверить, что устаревшая вкладка не отзывает новую shared-cookie сессию;
исправить только восстановление устаревшей сессии, выполнить браузерную регрессию,
frontend/backend/HTTP минимум и повторить CI. Предметные нормы, схема и права
доступа не меняются. Откат — revert исправления; выпуск до CI не выполняется.

Причина подтверждена детерминированно: реальный 401 второй вкладки удерживается
до нового login; старый resetStaleUserState отправлял logout с новой общей cookie.
Новая регрессия на исходном коде FAIL: backgroundLogouts=1 вместо 0.
Исправление session.js убирает серверный logout из восстановления stale-сессии;
локальная очистка и явный logout сохраняются. Браузерный тест проверяет отсутствие
фонового logout и сохранение authenticated=true/email нового синтетического owner.
Исходный Recovery отдельно 3/3 PASS показывает зависимость сбоя от порядка событий.

После исправления: адресные Recovery / Late 401 / S10.4 — 3 PASS, retries=0;
362 unit, 40 HTTP, 4 frontend, lint, build — PASS. Release manifest пересчитан
по новой сборке. Версия остаётся 2.1.31, ещё не опубликованной на test.
PR CI 37368938883 на предыдущем head не получил hosted runner и завершился
Internal server error; это инфраструктурный сбой, не PASS. Новый head должен
пройти полный CI (включая теперь 12 browser tests) перед слиянием.

## Запас ожидания S10-C1/C2 — 2026-10-06

Основание: пользователь принял предложение увеличить ожидание calculated
с 60 до 120 секунд и общий timeout только этих двух сценариев до 240 секунд.
На 2cced077 PR CI 37371498658, attempt 2: frontend и backend этапы прошли;
browser 11 PASS / 1 FAIL — S10-C1, ожидание calculated на строке 221.
GitHub Actions восстановлен; этот FAIL уже не относится к выдаче runner.

Прочитаны tests/browser/runtime.spec.mjs, playwright.config.mjs,
scripts/browser_stand.py и Api/m7_completion_worker.py: синтетический бюджет
30 секунд, период worker 30 секунд, затем расчёт. Источники архитектуры и
Change 01 переиспользованы из отчёта 10.7; нормы и runtime не меняются.
README, CONTRIBUTING, EVC workflow/matrix/artifact recipe прочитаны повторно.
Пробел: таймаут сам по себе не доказывает конкретную причину задержки;
проверяется согласованная гипотеза недостаточного запаса, а не снятие проверки.

Изменение ограничено tests/browser/runtime.spec.mjs. Все утверждения о
calculated, причине закрытия, запрете позднего Turn и сохранении единственного
ответа сохранены; retries=0. Общий timeout остальных тестов остаётся 150 секунд.
План проверок: S10-C1/C2 по три повтора в owned test БД, node --check,
lint/build, diff и manifest, затем полный CI точного head. Первичный запуск
в sandbox остановлен запретом запуска Chromium до выполнения сценариев;
повтор выполняется вне sandbox. Данные/схема/права/PM-контракты не меняются.
Откат: revert тестовой правки; при повторном FAIL дальнейший рост ожидания
не применяется без диагностики. Новых предметных стоп-условий нет.

Результат: `npm run test:browser -- --grep 'S10-C[12]' --repeat-each=3`
на изолированном локальном PostgreSQL — 6 PASS / 0 FAIL, 8.4 минуты,
retries=0. Полные сценарии C1 занимали 1.4–1.5 минуты, C2 — 1.3 минуты.
`node --check tests/browser/runtime.spec.mjs`, `npm run lint:js`,
`npm run build:web`, frontend tests (4 PASS), `git diff --check` — PASS.
Сборка не изменила web/dist; manifest обновлён (531 файл, пропущенных нет).
Review: правка только ожидания в тестах и отчётных метаданных, все assertions
сохранены; production таймеры, БД, конфигурации и версия не изменены.
Полный backend/HTTP/integration/browser повторяется штатным CI нового head;
локально повторно выбран затронутый браузерный путь. До зелёного CI слияния нет.
