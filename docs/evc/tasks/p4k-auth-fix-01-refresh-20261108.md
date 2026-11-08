# P4K_AUTH_FIX_01 — обновление кандидата08.11.2026

Основание: прямой запрос владельца повторить обновление main и запуск CI;
действует прежнее разрешение на patch/push/PR и merge/deploy-test после CI/review.
Prod/pilot, реальные письма, продуктовые LLM и рабочие данные не разрешены.

Сохранён старый head acfffdfabc05cf900d97744587a8bb877362d2c6:
backup/p4k-auth-before-main-20261108; прежние bundles/patches/evidence не переписаны.
Свежий main7de0277d8c3b8f92fb74a3a5bb9d01f2b8ce4944, версия2.0.82,
включён merge-коммитом a31b1191c3b5612b47da9499a532c31f88b3bfef.
Конфликты release-файлов разрешены наследованием2.0.82; AUTH header/copy/layout
сохранены. Все generated dist конфликты устранены штатной пересборкой sources.
Тесты auth-r03 автоматически объединились с новыми AC18-FIX-02 регрессиями;
импорты AUTH helpers и guards main сохранены. Новые main product-cycle-start/
interview/onboarding изменения не откатывались. B-01 повторно не реализуется.

AGENTS/CONTRIBUTING/README/tests README/verification-matrix/package files
не изменились относительно ранее прочитанного main65c1f4c. Diff и применимые
release/CI scripts повторно просмотрены. Предметные изменения main приняты
интеграцией; реальные provider-проверки из чужого отчёта не запускаются.

Предыдущий AUTH номер2.0.76 не выпускался; main уже2.0.82, поэтому по прежнему
разрешению владельца на следующий свободный PATCH штатный ready:prepare назначает
2.0.83. Это актуализация кандидата относительно новой базы, не повторный bump
неизменённого выпуска. release gate против свежего main обязателен.

Локальный минимум exact candidate: diff/lint/frontend/build/dist, backend unit,
HTTP и browser AUTH/recovery/readiness/footer плюс4 новых AC18-FIX-02 synthetic
регрессии. Backend/HTTP — sterile env, dotenv disabled, loopback DB port9,
browser — local fixtures; опубликованный origin не задаётся. Снимки AUTH01/02/03
и no-JS1440×1024/DPR1/100%/Onest. Повторный preflight/fetch перед push.

На старте08.11: PR181 OPEN Ready, headacfffdf;0 CI runs и публичныйHTTP404.
Обновление собственной ветки даёт штатный synchronize. Внешний отчёт фиксирует
точные SHA/команды/exit codes и результат actual-head CI. Старое различие
видимости авторHTTP200/public404 не считается исправленным без новой проверки.

Merge только после frontend/pytest/full-verification актуального head/base и
человеческого review. Нельзя подставлять статусы или обходить ruleset.
Затем ожидать deploy-test и сверить actual release/assets/AUTH на test.
Если CI не создаётся, явно сообщить NO_RUN_CREATED; ни локальный PASS, ни
старые CI других PR не заменяют required checks. Риски/откат — исходная карточка
p4k-auth-fix-01-release.md; после merge откат отдельным revert PR.
