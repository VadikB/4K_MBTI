# AUTH-DIAG-01 — отложенная очистка стирает ошибку входа

Область: отдельная диагностика по списку владельца, base/main/test946a46c /2.0.68.
Продукт не изменялся. Не смешивать с PREP-DIAG-01.

## Факты и причина нового воспроизведения

1. Настоящий entry/dist получает synthetic password-login200, затем journey401.
2. В `api.js::readApiResponse` recovery запускается fire-and-forget; ошибка401
   немедленно передаётся в `wiring.js::applyAuthResponse`.
3. `session.js::resetStaleUserState` вызывает returnToStart, затем ждёт lazy
   `screen-loaders.js::resetChatScreen` → import chat entry.
4. Пока HTTP загрузка chat chunk задержана, catch applyAuthResponse показывает
   «Сессия входа не сохранилась». Это зафиксировано before PNG и наблюдением.
5. После разрешения настоящей загрузки `screens/chat.js::resetChat` вызывает
   `showError(authError, '')` и стирает сообщение. Финальная проверка присутствия
   ошибки **FAIL**, exit1, retries0; она не ослаблялась ради PASS.

Scope — deterministic synthetic transport reproduction, не подмена DOM/fetch/
таймеров/метода продукта. Вмешательство только в сетевые test responses и время
загрузки реального JS asset. Ровно1 journey401 и1 held chat request.

Команда: `node node_modules/@playwright/test/cli.js test --config
docs/evc/evidence/path-final-audit/auth-diagnostic.config.mjs`, sterile env,
localhost18765, без .env/БД/реального пользователя/LLM. Не включена в штатный
`*.spec.mjs`: отрицательная диагностика имеет расширение `.diagnostic.mjs` и
явный opt-in config. Default suite/config не изменены, retries0.

Первичные [JSON](../evidence/path-final-audit/auth-diagnostic-results.json),
[наблюдение](../evidence/path-final-audit/auth-observation.json),
[до](../evidence/path-final-audit/before-delayed-cleanup.png),
[после](../evidence/path-final-audit/test-failed-1.png), stdout/error-context gzip.
Исходный spec — `tests/browser/auth-recovery-race.diagnostic.mjs`.

## Историческая причинность и границы

В прежнем full114/1 на рабочем2.0.67 JSON и PNG показывают такое же пустое
auth-error и возврат email form со старым password title. Это совместимо с новой
гонкой, но timing/network trace того run не сохранён: причинность **NOT_ESTABLISHED**.
Причина нового controlled reproduction установлена; причина старого единичного
сбоя остаётся UNKNOWN. Поздние115 PASS не опровергают новый deterministic FAIL.
Нет доказательства обхода авторизации или доступа к чужим данным.

## Исправление и дальнейшая проверка — отдельный шаг

Нужно устранить конкуренцию error rendering и lazy cleanup: либо дождаться
разрешённого recovery до финального показа ошибки, либо отделить chat cleanup от
auth status текущего поколения. Не убирать fail-closed/epoch guards и не вводить
таймаут/задержку в тест как продуктовый fix. Проверить delayed/fast chunk,
concurrent401, поздние ответы старой сессии и переключение аккаунта/таба.
Пока это проект технического исправления, **product_fix=NOT_PERFORMED**.
Новый bump/PR/CI/review/merge/deploy не разрешены данным диагностическим шагом.
