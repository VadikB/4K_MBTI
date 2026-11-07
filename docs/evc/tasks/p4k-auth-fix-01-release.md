# P4K_AUTH_FIX_01 — выпуск на test 07.11.2026

Прямое основание — последующее разрешение владельца от 07.11.2026 завершить
выпуск на test. Исторические локальные отчёты 05.11 и 07.11 сохраняются как срезы
с прежними ограничениями; для настоящего выпуска действует это новое разрешение.

## Границы и разрешения

branch_push=true; pr=true; version_bump=true (следующий свободный PATCH);
merge=true после обязательного CI и предусмотренного человеческого review;
deploy=true только автоматический deploy-test; artifact_publish=false.
Prod, pilot, реальные письма, продуктовые LLM и изменения рабочих данных не разрешены.
Защита main и управляющие документы не меняются; обход checks/review запрещён.

## Состав кандидата

База origin/main: 65c1f4c04466b60d4c6ce4611346fc92c617ed74, версия 2.0.75.
Она включена merge-коммитом 396a0d879f01f6d9ea061b09a577ad7b1d5d4f84.
Повторный fetch перед выпуском подтвердил ту же базу.
Следующий PATCH 2.0.76 назначается штатным ready:prepare с пересборкой bundle.

Реализация и traceability: [исходная задача](p4k-auth-fix-01.md) и
[локальное завершение](p4k-auth-fix-01-completion.md).
AUTH-V01: белая оболочка, отдельный бренд/релиз, геометрия карточек, footer,
адаптивность и длинные ошибки. AUTH-F01: своевременное снятие ошибки email,
возврат CTA «Продолжить» после отказа/сбоя при сохранении busy/password guards.
B-01 уже устранён PR174 архитектора; повторной runtime-реализации нет.
Сохранены readiness/generation guards PR180. Добавлены управляемые recovery
регрессии с поздней загрузкой chat, успешным восстановлением и старым 401.
Серверные API, БД, методология, admission и предметные пакеты не изменены.

## Проверки и приёмка

Минимум для точного release SHA: diff, lint, frontend regression, build и
совпадение dist, backend unit, HTTP-контракты, AUTH/recovery/readiness browser.
Локальные unit/HTTP — sterile env, dotenv disabled, loopback port9 sentinel;
browser — synthetic loopback fixtures. Реальные письма и LLM не вызываются.
Предыдущий неизменённый UI срез396a0d8: frontend147, unit956, HTTP108, browser57 PASS.
После bump результаты повторно фиксируются для окончательного кандидата.

Обязательный CI: frontend, pytest, full-verification (integration + все browser lanes).
Человеческое review требуется CONTRIBUTING.md; отчёт агента его не заменяет.
Точный SHA, результаты и PR записываются во внешнем постоянном отчёте
outputs/p4k-auth-fix-01-release-20261107/ исходного workspace после commit.

После CI/review: повторный fetch, актуальность base/номера/head, squash merge через PR,
ожидание deploy-test. Проверить публичные HTML/assets/version по HTTPS
https://test.4k-assistant.ru и AUTH экран без авторизации/изменения данных.
Физические Safari/mobile keyboards не проверялись; Chromium эмуляция — отдельный scope.

Риск: непредвиденное взаимодействие CSS на иных устройствах; shared palette и
runtime main guards сохранены. Откат после merge — отдельный revert PR с новым
согласованным релизом; deploy script сохраняет прежний commit при неуспешном smoke.
Ручная загрузка файлов на сервер не используется. Продвижение в pilot/prod отсутствует.
