> Выпуск2.1.32: интеграция QA03/main e67cf7a и новые проверки539/HTTP3/browser22 PASS. Текущий этап/CI — [PR.md](PR.md).

> 18.11.2026: результат принят; прямое поручение на PR/merge разрешает этап выпуска. Текущие полномочия и dependency — [PR.md](PR.md). Ниже сохранён локальный этап.

# QA-04 — локальная реализация, 18.11.2026

Код, регрессии и собранный frontend: **a134d583587226bbc624bb45d0e439a5db89a550**.
Ветка `codex/p4k-postw02-qa-04`, main на старте `997e4eb` /2.1.30,
интегрированная локальная база QA03 `8930e64`. Финальный UI head: **a134d583587226bbc624bb45d0e439a5db89a550**. Номер приложения сохранён.
QA03 PR247 на момент проверки открыт; это локальная последовательная интеграция,
а не утверждение, что QA03 принят в main. Внешняя публикация не выполнялась.

## Причины и результат

1. Scroll scheduler работал до добавления pending row. Рендер этой строки был
   `scroll:false`, поэтому новая нижняя граница оставалась за viewport. Выравнивание
   теперь происходит после server trace, pending row, доставки и раскладки controls.
   Только собственная явная отправка принудительно показывает низ; прежняя ручная
   прокрутка и отмена поздних layout callbacks сохранены.
2. Wiring заменял действие кнопки на receipt и возвращал подпись через1200ms.
   Новый AS/ASK мог появиться раньше сброса. Receipt убран из кнопки, timeout удалён;
   каждый runtime render назначает подпись текущей операции. Поздние обработчики
   сохраняют guards owner/epoch/Cycle/AS/ASK/view.
3. Уведомление выбирало факт сохранения через `some(assessee Turn)` и смешивало
   актуальный серверный ответ с повторным рендером кеша. Теперь receipt имеет точные
   turn/request IDs и scope; неизвестная новая отправка не наследует старое
   подтверждение. На reload допускается последний серверный ответ с request ID
   либо точный `clarification.answer_turn_id`. Более поздняя реплика персонажа сама
   по себе не доказывает актуальный receipt. Подтверждённый ACK сохраняется и после
   retirement pending operation, даже если следующий runtime GET не удался.
4. При `scenario_ended + answered + finish allowed` старый placeholder приглашал
   к недоступному вводу. Теперь он сообщает о допустимом завершении; разрешённая
   сервером кнопка сохранена. Во время блокирующей отправки/чтения состояния
   disabled поле также не приглашает писать. Произвольный ввод после M7 не открыт.
5. Настоящий браузер выявил потерю черновика при новом dialogue Turn: `draftSlot`
   менялся, `bind` очищал DOM. Непосланный raw buffer теперь сохраняется при смене
   dialogue slot внутри тех же owner/epoch/Cycle/AS. Новый AS или M7 вопрос получает
   собственный слот. Непустой другой сохранённый вариант использует прежний conflict
   choice/CAS. Принятую точную revision очищаем до смены слота; более новый текст
   не очищается, потерянный ACK не создаёт дубликат черновика отправленного ответа.

Подтверждение и восстановление находятся в прежнем `#interview-error` между
историей и формой, с классом `.processing-notice`. Дубли receipt в draft status
и delivery строки убраны. Pending/rejected/unknown delivery и прежний безопасный
same-ID retry остаются в своём действующем контракте.

Уведомление различает fresh blocking, existing deadline exceeded, accepted/stale,
read failure, unknown receipt и confirmed failure. Порог45s уже существовал;
нового ETA/порога нет. После истечения этого бюджета обновляется подпись без
дополнительного poll. Утверждение о нерасходовании времени требует текущего
`blocking_system_wait=true` и согласованного receipt/trace; ошибка чтения убирает
это утверждение. Фоновый running AI сам не блокирует отправку. При подтверждённом
blocking wait отправка закрыта, но в действующем active/ASK draft scope редактор
остаётся доступным. Новых команд восстановления/норм завершения нет.

## Приёмка

| AC | Проверка | Итог |
| --- | --- | --- |
| C1 | Production renderer: pending row учитывается в новой высоте; Chromium1440/390/320: собственный pending виден, принятый ответ на снимках; один POST | PASS |
| C2 | На baseline сохранение reading position уже PASS и не переписано; background Turn в Chromium сохраняет scrollTop и raw draft, кнопка вниз достигает конца; ручной scroll отменяет callbacks | PASS |
| C3 | DOM history→notice→form; main button «Отправить»; accepted receipt отсутствует под полем и в delivery; ожидание в одной прежней зоне | PASS |
| C4 | Production wiring + renderer: send→new ASK/AS→layout callbacks; старого1200ms callback больше нет; guards поздних результатов проверяются P3/QA03 регрессиями | PASS |
| C5 | Отвеченное уточнение: disabled поле без приглашения ввода, finish visible/enabled; screenshot на трёх ширинах | PASS |
| C6 | Browser fresh/delayed/stale/read error/unknown/failed; controlled clock45s; GET проверки того же request/turn ID, POST ровно1; unit active AI vs blocking wait; missing/false interval без ложной паузы | PASS |
| C7 |10 новых frontend cases; QA01 delayed conflict/new text/reload, POSTW02-05 durable draft/lost ACK и QA03 time/Next/browser регрессии; точная accepted revision перед сменой слота | PASS |
| C8 |24 файла v10 совпали с SOURCE_IDENTITY; Chromium сравнивает white surface, border3px, radius8px и Onest, порядок зон и кнопку; сценарий/шапка/индикатор не менялись | PASS |

PASS относится к локальному синтетическому контуру, не к живому TEST или пилоту.

## Проверки и доказательства

| Команда / область | Факт |
| --- | --- |
| Те же9 QA04 production-function tests на `git show 8930e64` в отдельном temporary fixture tree |1 PASS /8 FAIL, exit1: [до исправления](evidence/frontend-before.log.gz). Дополнительный новый draft case на старом source:0/1, exit1, [draft before](evidence/draft-before.log.gz). Изменяемые production файлы не подменялись во время проверки текущей ветки |
| `node --test tests/frontend/*.test.mjs` |**473 PASS**, exit0, [полный frontend](evidence/frontend-full.log.gz), включая10 новых случаев |
| `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 .venv/bin/python -m pytest -q -m e2e tests/e2e/test_postw02_assessment_ui_http.py` |**3 PASS**, exit0, production HTTP route/projection + controlled storage, [HTTP](evidence/http.log.gz); Python/API не менялись |
| `npm run lint:js` |PASS, exit0, [lint](evidence/lint.log.gz) |
| `npm run build:web`, повтор и сравнение SHA256 |PASS, exit0;48 файлов побайтово совпали: [build](evidence/build.log.gz), [сравнение](evidence/build-reproducible.json) |
| `node node_modules/@playwright/test/cli.js test tests/browser/qa04-answer.spec.mjs tests/browser/postw02-assessment-ui.spec.mjs tests/browser/answer-drafts.spec.mjs tests/browser/postw02-qa-state.spec.mjs tests/browser/qa03-runtime.spec.mjs --workers=1 --retries=0 --global-timeout=300000 --timeout=20000` |**22 PASS за29.9s**, exit0, [browser](evidence/browser-final.log.gz). После финальных малых правок placeholder/типографики и подписи server-blocked preflight: QA04 тот же профиль, **7 PASS за12.7s**, exit0, [final screen](evidence/browser-screen-final.log.gz). Остальная неизменённая область22 переиспользована |
| v10 checksums + DOM/computed style + визуальный просмотр |PASS: [integrity](evidence/reference-integrity.json), [reference zones](evidence/browser/reference-zones.json), [390 facts](evidence/browser/facts-390.json) |
| `git diff --check`, source/content review |PASS. Права/серверные endpoints/схема/снимки/интервалы/release metadata не менялись |

Для воспроизведения browser: `POSTW02_REFERENCE` указывает на распакованный
`REFERENCE_V10.zip` с каталогом `dist`, `QA04_EVIDENCE` — каталог снимков. Регрессии
используют `POSTW05_EVIDENCE`, `POSTW_QA_EVIDENCE`, `QA03_EVIDENCE`, а прежний
assessment spec — `POSTW02_UI_EVIDENCE`. Синтетические compatibility screenshots
сохранены вне diff в workspace `outputs/p4k-qa04-answer-20261118/compatibility`;
assessment evidence из `.test-stand/postw02-ui` скопировано туда при завершении.

Начальный browser sandbox EPERM случился до запуска продукта; localhost был
разрешён штатной эскалацией. Браузер доказал потерю draft и привёл к описанному fix.
Один промежуточный прогон не вошёл в interview при bootstrap; точная причина
не установлена (он совпал с повторной сборкой dist, это возможное объяснение,
не подтверждённая продуктовая причина). Диагностика сохранена в
[browser-final-before](evidence/browser-final-before.log.gz). После прекращения
сборки во время browser run окончательные22 и7 прошли. Автоматических retries0.

## Снимки

- [Ожидание390](evidence/browser/waiting-390.png).
- [Accepted/stale320](evidence/browser/accepted-stale-320.png).
- [Задержка1440](evidence/browser/delayed-1440.png).
- [Ошибка чтения390](evidence/browser/read-error-390.png).
- [Ошибка обработки320](evidence/browser/failed-320.png).
- [Неизвестный receipt390](evidence/browser/unknown-receipt-390.png).
- [Допустимое завершение1440](evidence/browser/finish-allowed-1440.png).
- [Эталон390](evidence/browser/reference-waiting-390.png).

Всего30 PNG в browser:10 состояний/сравнений ×3 ширины. Просмотрены desktop1440,
mobile390 и320, включая окончательный placeholder в stale320. Горизонтального
переполнения нет. Список/хеши — [manifest](evidence/manifest.json).

## Границы, риски и откат

Источники/версии/полномочия/стоп-условия и traceability — [TASK](TASK.md).
Production изменён только в interview.js, wiring.js, answer-drafts.js и3 правилах
interview.css (единый Onest/16px/24px/radius8px также для ошибки); dist пересобран, тесты адаптированы к новому месту статуса.
Генерируемые chunk names меняются штатно. Зависимости и версия приложения прежние.

Серверная причина живой задержки, реальная реакция персонажа, полнота Cycle/Report,
доставка писем и готовность пилота **NOT_RUN / не заявляются**. QA05 не подменяется.
Runtime API не содержит отдельного freshness timestamp для этого блока: текущим
считается успешный scoped GET, кешовый re-render не сбрасывает read failure;
receipt до согласованного trace показывается как уточняемое состояние.

Полный backend/DB integration не нужен для неизменённого серверного контракта;
проверен адресный HTTP. GitHub CI, human review, Ready/release и живая TEST-приёмка
**NOT_RUN**: разрешён только локальный этап. Перед PR нужны актуальная общая база
после QA03, отдельный допуск публикации и штатные gates перед будущим merge.
Человеческое принятие не заменяется этим отчётом.

Собственные HTTP servers закрыты; независимая проверка портов —
[cleanup](evidence/cleanup-verified.json). Созданных БД0, реальных LLM0/mail0;
рабочие БД, `.env` и чужие процессы не затронуты. Нового артефактного долга нет.

Откат: `git revert a134d583587226bbc624bb45d0e439a5db89a550 ebce9a3722b0d9755fb2ac36b967ee6cc3d873c9 4fb685643fd6884379520da1428c532983df8f95` отменяет только
собственные UI/tests/dist, сохраняя QA03 и server Turns/интервалы/snapshots.
При будущем выпуске revert проходит обычный release/CI процесс.
