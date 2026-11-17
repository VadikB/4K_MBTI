## Текущее состояние CI

Merge заблокирован. Первый CI head496aa25: unit1248PASS, HTTP216PASS,
integration462PASS/2SKIP; frontend FAIL из-за unpatched picomatch через knip
([GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)).
Последний picomatch4.0.7 и knip6.45.1 не устраняют уязвимость. Audit/CI не ослаблены.
Full verification FAIL: fast340PASS/40SKIP/10FAIL, runtime3 7PASS/1FAIL;
runtime1/4 и4/4 PASS, runtime2/4 CANCELLED на checkout.

Исправлены readback после ответа с лишним адресатом и повторный Finish в browser
driver после закрытия другой вкладкой; прежние invitation-assertions обновлены под
утверждённый QA02 UI. После исправлений локально431 frontend,40 invitation/program
browser,1ADM28 real и1runtime PASS, lint/build/diffPASS. Radar PASS локально на
текущем bundle и неизменённом main71a9c53; причина CI-only font FAIL UNKNOWN.
Кандидат остаётся draft до устранения audit; перед merge обязателен полный CI
актуального head. Подробности и точные границы: STATE.md/REPORT.md рядом.

## Основание изменения

QA-02, матрица приглашений rev1.1 от17.11.2026. Задача:
`docs/evc/tasks/p4k-postw02-qa-02/REPORT.md`; контракт: `CONTRACT.md` рядом.
Base71a9c535cee4aea094d2b49c2b73f39e22f99bbe; один результат, кандидат2.1.29.
Владелец прямо разрешил публично опубликовать код QA-02, тесты, отчёты и PNG
в VadikB/4K_MBTI и слить PR в main после обязательного CI;
разрешены push/PR/Ready/следующийPATCH/merge после checks и штатный deploy TEST.

## Результат

Администраторы видели одинаковый совет проверить email при любых отказах, а ошибка
чтения ответа transport могла ошибочно считаться доказанным отказом. Теперь POST,
GET и список сохраняют безопасную причину и различают отказ, подготовку, принятие
сервисом и неизвестный исход. Unknown проверяет прежнюю команду; частичный batch
не отправляется заново. Сведения выбранной попытки свёрнуты и сохраняют живое
раскрытие при чтении; общая проблема показывается одним блоком перед списком.

## Изменённые файлы

Invitation routes/projection/schemas и mail adapter; presentation/details,
organization UI/wiring/CSS/entrypoint; адресные тесты и синтетические PNG, dist.
Перечень и AC I1–I10 — в REPORT.md.

## Источники и решения

Приложенные QA02/Invitation_Behaviors1.1; Product Architecture1.0 + Change01
WORKING01.10.2026, SourceSet2026-10-01, M1v1.4, относящиеся M7v1.3 §§5–6,
сохранённая выдержка glossary WORKING30.09, EVC/AGENTS. Статусы источников и
методология не меняются. QA05 уже выполнен PARTIAL, повтор TEST-ревизии не было.

## Проверки (команда → результат)

- lint/build/diff PASS; frontend429PASS, backend1247PASS, HTTP216PASS.
- Controlled transport+invitation HTTP61PASS; SQL/HTTP28PASS на owned PostgreSQL.
- Полный integration459PASS/2SKIP/1FAIL: fixture без production created_at;
  исправление проверено адресно. Это не единый зелёный повтор полного набора.
- Browser15PASS, production bundle + controlled API,1440/390/320; real mail/LLM0.
- Required CI актуального head — после публикации Ready PR; приведённые результаты локальные.

Ручная проверка: отказ с безопасным кодом → краткая причина; mixed batch → точные
счётчики; unknown → прежний ID; карточка → свёрнутые сведения/copy/обновление;
открытие/закрытие во время чтения сохраняется. PNG и counters — task/evidence.

## Непроверенное (что и почему)

Причина живого TEST-отказа неизвестна по QA05: серверный доступ недоступен.
Реальная отправка/доставка запрещена областью QA02 и не проверялась. Штатный ready:prepare2.1.29 PASS. CI точного head и review обязательны перед merge.

## Риски: конфиг / схема / деплой / безопасность / откат

Без конфигурационных изменений, миграций, новых grants и деплоя. Additive API;
legacy error безопасно читается без раскрытия raw provider response. Envelope
в существующем TEXT хранит разрешённые параметры и recipient fingerprint.
Откат — revert этого commit вместе с dist; сохранённые ссылки/операции не удалять.

## Следующий минимальный шаг

Поручение владельца на merge получено. Проверить CI точного head, выполнить
squash merge без bypass и подтвердить штатный deploy TEST; pilot/production исключены.

## Открытые вопросы (блокеры)

Нет технического блокера локальной реализации. Для диагностики TEST нужны
существующие реквизиты попыток и адресный операторский сбор по QA05.

## Действия выпуска

- [x] branch_push
- [x] pr
- [x] merge
- [x] deploy
- [x] version_bump
- [ ] artifact_publish

## Готовность

- [x] Один независимо принимаемый результат.
- [x] Локальные проверки и ограничения заполнены; diff --check PASS.
- [x] Синтетические данные; старые данные и sources совместимы.
- [x] Регрессии, controlled transport, HTTP/SQL и browser выполнены.
- [ ] CI актуального head и человеческое review перед слиянием.
- [x] Baseline не присвоен.
