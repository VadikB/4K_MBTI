# CHECKS — P4K-REPORT-05

База `4160a589` (2.1.17); кандидат 2.1.18, commit `fa48a3cbd30e1038863139656864709837fc2377`. Controlled synthetic fixtures, один worker, retries=0, платные LLM-вызовы и письма — 0. Снимки в `evidence/`; прототип v9 визуально просмотрен на 1440/390 px. CI точного head пока отсутствует.

| Критерий | Результат | Доказательство и предел |
| --- | --- | --- |
| AC01 ноль, пропуски, частичный, одно/нет числа | PASS локально | `node --test tests/frontend/*.test.mjs`: 354 PASS. Browser: все отсутствуют и одно число не создают линию/заливку; ноль остаётся числом. Циклический и несколько соседних пропусков покрыты unit. |
| AC02 три режима, значение и панель | PASS локально | Playwright REPORT-05 3 PASS: fill/outline/bars, точное значение, ограничение, выбор строки и основания. На 1440 панель справа; на 390 ниже. `evidence/radar-{1440,390}.png`. PDF здесь не изменён. |
| AC03 1440/390/320 и 200% | PASS локально | Снимки выше и Playwright: на 320/200% нет горизонтальной прокрутки всей страницы, основные кнопки доступны. Сверено с `reference/prototype/dist/report.html?scene=report-skill`; условные данные не перенесены. Человеческая визуальная приёмка ещё не выполнена. |
| AC04 клавиатура/focus/resize | PASS локально | Enter по мобильному ключу открывает одну панель и передаёт фокус; явный возврат к строке. `auth-r03.spec.mjs -g 'RAD01|UI02 full overview|QA19-04'`: 3 PASS, включая 320–1440 и подписи. |
| AC05 read-only и каталог отчёта | PASS локально | Browser fixture: восемь навыков четырёх К с сохранёнными IDs/ограничениями, отсутствие POST при выборе/рендере. Сервер/БД не менялись. |
| Регрессия REPORT-04 | PASS локально | `report04-personal.spec.mjs`: 3 PASS до финального изменения только UI выбранного состояния; REPORT-05 browser fixtures повторены после PATCH. |
| Frontend / release | PASS локально | `node --test tests/frontend/*.test.mjs`: 354 PASS после PATCH; `npm run lint:js`: PASS; `.venv/bin/python -m pytest -q tests/unit/test_release_version.py`: 11 PASS. `git fetch origin main` и штатный `npm run ready:prepare -- --candidate 2.1.18`: PASS, без изменения файлов; удалённый `main` = `4160a589`. |
| `git diff --check` | PASS локально | `git diff main...HEAD --check`; commit hook проверил staged frontend/dist. |
| CI/PR/TEST/Prod | PARTIAL | Ready PR #233 на `ae03a0c6`: `CI / frontend` и `CI / pytest` PASS. `Full verification / browser (runtime-4-of-4)` FAIL: три сценария вызывали общий helper с прежним селектором `#m8-report-skills`, тогда как текст «общий уровень навыка не присваивается» теперь находится в связанной панели `#m8-report-detail`. Исправлен адресный selector в `tests/browser/runtime.spec.mjs`, добавлена регрессия панели в REPORT-05 fixture: 1 PASS локально. Остальной полный CI точного исправленного head ожидается; review и deploy не выполнялись. |

Откат: revert commit REPORT-05 и обратный штатный PATCH-кандидат при публикации; SQL/миграций/новых артефактов нет. Перед merge повторно проверить свежий `origin/main` и обязательный CI точного head.
