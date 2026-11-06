# BROWSER-TIMEOUT-DIAG-01 — итог диагностики, без нового product fix

Продолжение после локального AUTH fix `bf637af8e1ee89c1a8d5621c4ce694a52bb0806e`.
Новых изменений продукта, тестовых assertions/config, dist, backend, БД и
предметных артефактов нет. Ветка `codex/path-final-audit`; точный docs/evidence
commit и дерево передаются в HANDOFF пакета, product code SHA остаётся bf637af.

## Результат

| Проверка | Факт | Первичные evidence |
| --- | --- | --- |
| Два прежних timeout-сценария, current bf637af, по3 повтора | exit0,6 PASS,14.1s, retry0 | [JSON](../evidence/browser-timeout-diagnostic/current-targeted/results.json),6 traces |
| Те же сценарии до fix, immutable dea8c44, по3 повтора | exit0,6 PASS,14.2s, retry0 | [JSON](../evidence/browser-timeout-diagnostic/comparison-targeted/results.json),6 traces |
| Свежий полный auth/admin + AUTH recovery | **exit1,118 PASS/1 FAIL**,209.6s, retry0 | [JSON](../evidence/browser-timeout-diagnostic/current-full/results.json), failure trace/PNG/context |
| Новый R10 status-loss на dea8c44,3 повтора | **exit1,3 FAIL** на493,23.4s, retry0 | [JSON](../evidence/browser-timeout-diagnostic/comparison-status/results.json),3 failure traces |

Старые два timeout сейчас **NOT_REPRODUCED**, причина UNKNOWN: это не доказанный
исправленный defect и не признанный infrastructure-only сбой. Отрицательные
full117/2 и followup1/1 из bf637af сохранены, не подменяются новым run. Исправлена
неточная интерпретация старого JSON: ADM full был на click757, followup на fill754,
не «тот же шаг». Исторический пакет/manifest183 не переписывался.

Полный текущий gate всё ещё **FAIL**, но с конкретным новым основанием:
[R10-STATUS-DIAG-01](../tasks/r10-status-diag-01.md). Trace показывает PASS490
(сообщение уже было), release questionnaire503 и FAIL493 (элемент исчез).
Исходный loadAdminOrganizations завершает Promise.all и заново рисует карточку;
DOM-only status не восстанавливается. Background render:false недостаточен.
Подключённая программа остаётся видимой; это потеря feedback, не подключения/AS.
3/3 FAIL на том же assertion до auth-fix подтверждают preexisting характер.
Ни этот дефект, ни успешные6/6 не устанавливают причину исторического timeout.
Предложение узкого исправления и scope guards — в отдельной карточке; пока
**FIX_NOT_AUTHORIZED**, скрытых product изменений нет.

## Фактические команды и применимость

Node25.5.0 / Playwright1.63.0 / Chromium1243, те же lockfile dependencies.
Из каждого checkout, sterile env (`env -i PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
HOME=/Users/vadim_bogachev`), без .env, БД, реальных identity/cookie и ключей LLM:

```sh
node node_modules/@playwright/test/cli.js test tests/browser/auth-r03.spec.mjs \
  --grep 'restores the exact connected program after reopening|keeps superadmin participant cards readable on narrow viewports' \
  --trace on --global-timeout 60000 --repeat-each 3 --workers 1 --retries 0 \
  --output .test-stand/timeout-diag-current
# Та же команда в dea8c44, output timeout-diag-comparison.
node node_modules/@playwright/test/cli.js test tests/browser/auth-r03.spec.mjs tests/browser/auth-recovery.spec.mjs \
  --trace retain-on-failure --global-timeout 300000 --workers 1 --retries 0 \
  --output .test-stand/timeout-diag-full
# Только comparison dea8c44, тот же test/ожидание, другой grep:
node node_modules/@playwright/test/cli.js test tests/browser/auth-r03.spec.mjs \
  --grep 'finishes exact program connection while questionnaire refresh is pending' \
  --trace on --global-timeout 60000 --repeat-each 3 --workers 1 --retries 0 \
  --output .test-stand/r10-status-comparison
```

Global timeout — внешний диагностический предел, не увеличенное ожидание и не
штатная настройка: per-test150000ms/expect5000ms остались исходными. Ни один batch
не достиг global deadline. Первый comparison shell exit1 до запуска тестов:
не был создан собственный .test-stand; каталог создан, учтён только настоящий run.
Traces только синтетические, содержат fake fixture credentials, не рабочие секреты.

Source identity `auth-r03.spec`, config, main/wiring/organizations совпадает между
commits; hashes в diagnosis.json. Product diff после bf637af пуст. Точные45 assets
повторно не строились: проверенный bf manifest/code hashes переиспользован.
Backend920/HTTP108/frontend142/lint/build из bf637af переиспользованы только для
неизменённого продукта. Для нового docs/evidence шага: diff/ссылки, Node syntax,
COLLECT/CHECK, integrity/fresh bundle restore. CI/human acceptance нового кода
**NOT_RUN**; новый product fix не сделан. Autotests не касались рабочей БД.

## Передача, история и откат

Локальная диагностика завершена. Человеческое решение нужно только для нового
узкого R10 fix; не для повторного подтверждения уже разрешённого AUTH fix.
Main/origin-main — локальные refs946a46c/2.0.68, fresh fetch NOT_RUN. Test — последний
подтверждённый946a46c; новый server readback/CI/PR/bump/push/merge/deploy/активация/
публикация/LLM не выполнялись. Готовность выпуска не заявляется. Baseline не назначен.
Откат — revert только нового docs/evidence commit, без данных/рабочего контура.

Временные node_modules symlinks в двух checkout удалены без удаления targets.
Два исторических ADM PNG штатный тест перезаписал: новые сохранены отдельно,
старые восстановлены из bf637af; остальные пользовательские файлы не менялись.
Исторические CHECK170/183 повторены только в их immutable restored checkout.
Новый FILES/CHECK относится к этому шагу и проверяет **записанные** результаты,
не запускает продукт заново и не объявляет отрицательные прогоны PASS.
PREP-DIAG-01 UNKNOWN и auth114/1 NOT_ESTABLISHED сохраняются независимо.
