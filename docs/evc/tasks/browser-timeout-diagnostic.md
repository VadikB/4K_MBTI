# BROWSER-TIMEOUT-DIAG-01 — оставшиеся R10/ADM timeout

## Результат и границы

Основание — «идем дальше» после передачи локального AUTH fix bf637af8e1ee.
Текущий шаг — диагностика оставшегося красного browser gate, не допуск нового
исправления или выпуска. Код продукта, ожидания тестов и штатный config не менять.
Рабочая БД, реальные аккаунты, LLM, bump/push/PR/merge/deploy/публикация/активация
исключены; все release flags false. Baseline не назначается.

## Разведка и источники

Прочитаны первичные full/followup JSON из `path-auth-fix`, helper
`openAdminOrganizations`, R10 и ADM-STATUS тесты в `auth-r03.spec.mjs`, boot в
`main.js`, auth в `wiring.js`, session/router/loader и CLI options из установленного
Playwright1.63.0. README/CONTRIBUTING/EVC workflow/matrix/recipe/review и
архитектурный context/Registry/Change01/M1v1.4 (FROZEN/CURRENT=NO) повторно
используются неизменёнными из предыдущего шага; предметная норма не меняется.
Traceability: первичный timeout → конкретный locator/action и состояние UI →
неизменённый вход продукта → сравнительный synthetic HTTP browser run.

Точная поправка к прежнему отчёту: первый ADM full timeout действительно на
`#verify-magic-link-button.click()` (helper757), но followup JSON показывает
`#email-input.fill()` (helper754). Поэтому прежняя формулировка «тот же шаг»
неточна. Исторический пакет bf637af и manifest183 не переписывать; уточнение
добавляется здесь отдельно. Оба ADM сбоя до layout assertions, но не на одном
действии. R10 full: selectOption662, followup PASS. Не считать причиной ни AUTH
fix, ни optional PasswordCredential, ни sleep машины без доказательства.

`auth-r03.spec.mjs`, `wiring.js`, `main.js` и штатный config между dea8c44 и
bf637af идентичны; дельта продукта — ровно три UI cleanup-модуля и assets.
Восемь стоп-условий workflow — нет для локальной диагностики: нет изменения
предметной нормы/API/данных/прав/контура, область ограничена и откат — удаление
только новых диагностических файлов либо revert рабочего docs commit.

## План

1. Точный current bf637af и неизменяемый comparison commit dea8c44, существующие
   два теста, по3 повтора, retry0; `--trace on --global-timeout 60000` ограничивает
   только диагностический batch (штатные expectations/150000ms не меняются).
   Полные traces только synthetic identities/HTTP; .env/БД/provider нет.
2. Сопоставить действия/ошибки/ответы/время, сохранить отрицательные и положительные
   результаты отдельно. Если воспроизводится дефект — описать cause/unknown,
   исправление только в отдельном явно разрешённом шаге.
3. При достаточных данных — один свежий штатный полный auth/admin run с trace
   retain-on-failure и внешним пределом300000ms, без ослабления assertions/retries.
   Прошлый красный gate не заменять новым. Если условия не позволяют — NOT_RUN.
4. Документальный отчёт/STATE, local working commit и доступный пакет с primary
   evidence. Проверить diff/ссылки и integrity; старые snapshots не пересчитывать.

Шаги1–4 завершены с передачей docs/evidence commit и пакета. Current/comparison
targeted6/6 PASS; старые timeout не воспроизведены, root UNKNOWN. Свежий полный
118 PASS/1 FAIL выявил [R10-STATUS-DIAG-01](r10-status-diag-01.md), который также
получил3/3 FAIL до auth-fix. Новый fix не разрешён, зависимая работа ожидает владельца.
[Отчёт/команды/evidence](../reports/browser-timeout-diagnostic.md).
Новый CI/human review/выпуск NOT_RUN. Main/origin-main — локальные
refs946a46c; test — последний подтверждённый946a46c/2.0.68, fresh remote/server
readback не входит. PREP-DIAG-01 UNKNOWN и старый auth114/1 NOT_ESTABLISHED отдельно.
