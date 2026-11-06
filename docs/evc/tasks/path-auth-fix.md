# AUTH-DIAG-01-FIX — локальное исправление очистки auth feedback

## Результат и допуск

Владелец 06.11.2026 подтвердил «Да, исправить AUTH-DIAG-01 локально»:
узкое исправление и регрессии, fail-closed и session-generation guards сохраняются.
База — `dea8c44a183c2ac5f4b527e53cdeed0a39bcf454`, ветка
`codex/path-final-audit`; main/test — последний подтверждённый
`946a46cb71e5ca5cc99778f036807d6c193188dc` / 2.0.68.
Рабочая БД, LLM, bump, push, PR, merge, deploy, публикация и активация исключены.
Все release flags `false`; это рабочий шаг, не новый выпуск и не baseline.

## Разведка и решение

Повторно использованы неизменённые README.md, CONTRIBUTING.md, EVC workflow,
verification-matrix, artifact-recipe/review-checklist, архитектурный context/Registry,
Change 01/manifest и M1 v1.4 FROZEN/CURRENT=NO из предыдущего шага.
Непосредственно прочитаны `path-auth-diagnostic.md`, `api.js`, `session.js`,
`screen-loaders.js`, `screens/chat.js`, `router.js`, auth-часть `wiring.js`,
`api-unauthorized.test.mjs`, `auth-ux.test.mjs`, затронутые auth-r03 browser tests,
`tests/README.md` и `tests/conftest.py`.

Цепочка: protected journey401 → readApiResponse fire-and-forget recovery →
синхронный fail-closed/returnToStart → lazy resetChat → очистка уже показанной ошибки.
Решение: очистить прежнюю ошибку синхронно при recovery, а delayed chat cleanup
не очищает auth feedback. Обычный reset/logout сохраняет прежнее поведение по умолчанию.
Проверка generation остаётся перед вызовом resetChat после загрузки модуля.
Слой UI/session lifecycle; HTTP, server auth/cookie, PM-03/04, методология,
admission/repair и версии предметных артефактов не меняются. Нового долга нет.

Пробелы: исторический auth114/1 не имеет timing trace, его причина UNKNOWN /
NOT_ESTABLISHED; новое воспроизведение не доказывает историческую причинность.
PREP-DIAG-01 остаётся отдельным UNKNOWN. Все восемь стоп-условий workflow — нет:
предметная норма/API/БД/данные/артефакт/права/контур не меняются, локальный откат
определён, область явно разрешена. Дополнительного решения для локального шага нет.

## План и проверки

1. Сохранённое отрицательное воспроизведение на dea8c44 переиспользовать; добавить
   штатные deterministic browser regressions для delayed/eager cleanup и смены
   поколения/аккаунта/таба, без подмены DOM/fetch/таймеров продукта.
2. Узкая реализация, адресные browser + весь frontend, lint/build/idempotency.
   Concurrent401/late old responses — существующие executable Node regressions.
3. По auth-строке матрицы — backend unit и HTTP-контракт без реального LLM/БД;
   integration не требуется: поведение БД/server неизменно. Полный auth/admin
   synthetic HTTP browser suite, безопасный localhost, собственные fixtures.
4. Сохранить результаты/ограничения, локальный working commit, STATE и доступный
   независимый пакет. Новый обязательный CI NOT_RUN: PR не разрешён.

Шаги1–3 завершены: before1 FAIL → targeted4 PASS, frontend142/backend920/HTTP108
PASS, lint/build/idempotency45 PASS. Широкий browser119: **117 PASS /2 timeout**;
адресный повтор двух: **1 PASS /1 timeout**. Это не полный browser PASS.
Причины timeout UNKNOWN; автоматический retry0, исходные результаты сохранены.
Активно: локальная фиксация и независимая передача, без выпуска.
Исторический FILES.json audit170 относится только к immutable dea8c44: не
пересчитывать его под новым кодом. Новые evidence хранить отдельно.

## Откат

До выпуска — revert только нового локального working commit; main/test не меняются.
Данные и опубликованные snapshots не затронуты. Старое отрицательное evidence
сохраняется; после fix не выдавать его прежний checker за checker нового дерева.

Итог/точные команды/ограничения — [отчёт](../reports/path-auth-fix.md),
первичные результаты — [новый evidence](../evidence/path-auth-fix/after/full-results.json).
Новый локальный commit передаётся в package HANDOFF.json; новый CI/review и выпуск
не выполнялись. Готовность выпуска не заявляется, широкий browser gate красный.
