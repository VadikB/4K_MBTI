# POSTW02-05: замечания UI от 17.11.2026

Прямое поручение: «Замечания которые нужно исправить», затем «запусти задание по замечаниям».
Вложение P4K_POSTW02_05_UI_Followup_2026-11-17.txt — требования; внешняя публикация
не следует из самого вложения. Одна существующая ветка codex/p4k-postw02-05.
Base origin/main c05fe745ca48424796ad38886ee9e03d67d0bd69 (2.1.22), исходный head
7299920071499eff0fdff597081893c821558cd0. Read-only gh pr list по head вернул []:
PR05 фактически отсутствует, см. STATE. Push/merge/deploy не выполняются.

Источники исходной05 и их неизменённая применимость перечислены в PLAN.md.
Восстановлены AGENTS/STATE/decision-register и правила матрицы; дополнительного
методологического аудита нет. Архитектурные источники/статусы не повышаются.
Sites get_site_version повторно подтвердил v10/e44fa78efb1ec8605b28cf9bc2c2272da2b9122a;
точный локальный checkout ../outputs/p4k-postw02-01-20261116/reference-v10/.sites-checkout
совпадает с SHA. Прочитаны screen.css/screen.html/screen.mjs/ui-theme.css и report.html.
Новые состояния drafts отсутствуют в v10: их смысл остаётся из исходной05.

План: убрать конфликтующие старые composer-правила каскада, восстановить постоянные
колонки и фокус, уточнить подписи выбора; общий product-brand без декоративных точек.
Адресно закрыть обнаруженный пропуск05: конфликт блокирует отправку до выбора,
включая повторный runtime poll. Права/сервер/время/idempotency не меняются.
Проверки: frontend, lint, build/dist; существующие browser05/02 + адресные A–F.
Серверная матрица переиспользуется с f9b3bf4 в неизменённой области; полный цикл,
LLM/письма/БД/Docker/Prod не запускаются. CI нового head требует публикации ветки.


## Передаваемый результат

UI-изменение зафиксировано в 458b698. Затем в ту же рабочую ветку интегрирован
свежий main 44349d5784bf71c14b050cdcca4745eeff5a9ae8, версия 2.1.23, REPORT_08/PR238.
Проверенный код совместного результата: e846c8a60834e348f5369bba957dec9fb1270066.
Конфликты были только в generated web/dist; исходники Api/routes.py и index.html
объединились автоматически, bundles пересобраны. В main/Prod ничего не записано.
Финальный head отчёта/пакета: DELIVERY.json в outputs/p4k-postw02-05-20261117
родительского workspace. Отдельного bump/Ready нет.

### Замечание → исправление → доказательство

| Замечание | Исправление | Проверка |
|---|---|---|
| 1. Прямоугольное поле/resize/фокус | Один канонический набор composer-правил вместо нескольких переопределений в interview.css и utilities.css. 96px, min48/max120, padding12, radius8, resize:none; прозрачная рамка, 1px outline только при focus | A JSON: exact computed values на1440/390. B: blur/click/Tab, текст5889символов, selection450–480/backward, scrollTop240, тот же DOM/input/focus после autosave; конец доступен |
| 2. Нестабильная сетка | Desktop явные column1/2 и row2 для поля/кнопки; дополнительные строки обе колонки. Mobile footer в обычном потоке после статуса/выбора, note последняя | A: шесть PNG/JSON, одинаковые ширины/высота поля; desktop200px и общий нижний край. Mobile334px, вертикальный порядок |
| 3. Статусы/действия/disabled | Принятые participant tokens уже содержат нужные цвета; второй палитры нет. Новые ясные подписи, вторичные кнопки ≥44px. Явный конфликт блокирует submit и прямой вызов отправки; poll сохраняет запрет. После выбора проверяются прежние ограничения runtime/pending | C: обе редакции сохраняются до выбора, обе кнопки, 0 новых answer POST при выборе. Frontend две адресные регрессии. B: active/hover, disabled hover/active без изменения цвета |
| 4.1. Материал ситуации | Только первое сообщение до880px, заголовок20/28 и18/26 mobile, абзацы16/24. Короткие реплики прежней ширины | A computed/PNG, материалы synthetic HTTP fixture; реальные payload/snapshots не менялись |
| 4.2–4.3. Таймер и дублирование | Подпись «Осталось на ответы», значение24/32, при перемещении переносится весь timer wrapper. Убрана обычная дублирующая строка; реальные ограничения по-прежнему объясняются | A; regression02: текущая позиция из плана, ASK/ожидание/R1. Runtime-расчёт/лимиты не менялись;120:00 только из fixture7200s |
| 4.4. Завершение | Прежнее отдельное вторичное действие, справа desktop/слева mobile, gap16; навигация/права прежние | A PNG; regression02 проверяет действие под формой и прежние запреты |
| 4.5. История | Контейнер списка сообщений не сжимается flex-родителем; последняя реплика попадает внутрь scroll area. Кнопка вниз скрывается и градиент исчезает в конце | B после reload/восстановления длинного черновика: последняя реплика видна целиком, fade0, arrow hidden; autosave не меняет позицию чтения. latest-turn-390.png |
| 4.6. Узкий/низкий экран | Одноколоночная форма, перенос действий, страница доступна прокруткой | D:320×700,390×390,320×360; каждый control можно вывести в viewport; нет x-overflow, текст сохранён, conflict choices доступны320 |
| 5. Бренд | Общий product-brand, «4К Ассистент», Onest700,20desktop/18mobile; удалены два декоративных ::after | E: 13 существующих состояний ×3ширины ×online/offline, всего78 замеров, navigation labels сохранены |

### Что было в базе, что появилось в05

Проверено по git diff c05fe74..7299920: interview.css и onboarding.css в исходной05
не менялись. Resize:vertical, ширина760/заголовок16, маленький таймер без подписи,
дублирующая строка и два декоративных псевдоэлемента были в базе после03.
В05 добавлены status/actions и underlined actions в utilities.css. При auto placement
новые узлы сдвинули footer на следующую grid-строку; это расхождение внесено05.
В05 также не было блокировки отправки при незавершённом выборе версии; она добавлена
адресно, без смены server CAS/прав/offline-send/idempotency. Проблема сжатия списка
истории тоже была в базе; текущая проверка подтвердила её на длинном материале.

Причина точки в фактическом коде — статические #onboarding-home::after и
.shell:has(> #auth-complete-panel.w02-waiting:not(.hidden)) .auth-header-brand::after.
В первом был дополнительный mobile5px. Статусной JS-логики у этих псевдоэлементов
нет; они удалены из источника CSS. Functional preparing/presence/error indicators
не менялись. Product brand обновлён в шапках auth, знакомства, ожидания,
«Мои оценки», ai-welcome, администратора, организаций, пустого кабинета
администратора, prechat, интервью, processing и чата профиля. Auth/waiting
используют один DOM-бренд. У отчёта существующий заголовок «Результат оценки»;
он сохранён, дополнительного бренда/точки не добавляли. Навигационные заголовки
«Управление кейсами», отчётов/профиля/Prompt Lab сохранены.
В знакомстве менялись только бренд/декор; вопросы, тексты и поведение прежние.

### A–F и проверки

| Пункт | Итог | Свидетельство |
|---|---|---|
| A | PASS | saved/offline/conflict-{1440,390}.png и одноимённые JSON; screenshots.json содержит native размеры и SHA256 |
| B | PASS | interaction.json; те же input/focus/caret/selection/scroll/text после autosave, blur/click/Tab, long-text end; лог disabled.log.gz |
| C | PASS | browser.log.gz, answer-drafts.test.mjs и postw02-assessment-ui.test.mjs: выбор не отправляет ответ; unresolved conflict не обходит submit/runtime poll |
| D | PASS эмуляция | keyboard-emulated-*.png; узкие overflow/control checks; физическое устройство/настоящая ОС-клавиатура NOT_RUN |
| E | PASS | headers.json:78 computed замеров, network/width не создают декор; это короткие markup fixtures, не полные E2E каждого экрана |
| F | PASS локально; CI NOT_RUN | lint, frontend380, browser7, HTTP7, build/rebuild44 и diff-check. Полная серверная матрица05 не повторялась |

Команды на общем коде с новым main:

```sh
npm run lint:js
node --test tests/frontend/*.test.mjs
npm run build:web
git diff --exit-code -- web/dist
POSTW05_EVIDENCE=docs/evc/tasks/p4k-postw02-05/evidence/ui-followup POSTW02_UI_EVIDENCE=docs/evc/tasks/p4k-postw02-05/evidence/ui-followup/regression02 npx playwright test tests/browser/answer-drafts.spec.mjs tests/browser/postw02-assessment-ui.spec.mjs
.venv/bin/python -m pytest -q -m e2e tests/e2e/test_answer_drafts_http.py
git diff --check
```

После добавления disabled-hover assertions повторён только затронутый UI B/D:
PASS1, disabled.log.gz. Реальные CSS transitions дожидаются завершения; так в PNG
не попадают промежуточные оттенки. На раннем прогоне exact-float сравнение ширины
срабатывало во время entrance animation; измерение исправлено ожиданием завершения.
Первичные ошибки layout/прокрутки исправлены в коде, не ослаблением guards.
Логи с exit0 — evidence/ui-followup/*.log.gz. HTTP7 запущены адресно после
автоматического совмещения Api/routes.py; БД для них не используется.

Серверная реализация draft/CAS/expiry не менялась с f9b3bf4; прежние backend1193,
HTTP196, SQL95 — историческое доказательство исходной05 на base03, см. REPORT.
Они не заявляются повторно выполненными на новом main. Docker, БД, реальные LLM,
письма, полный Cycle, ожидание настоящего deadline и Prod — NOT_RUN.
Все fixture HTTP servers закрыты (cleanup.json), временные PostgreSQL не запускались.

Проверка gh pr list --head codex/p4k-postw02-05 --state all вернула []. CI05 не
запускался: ветка не экспортирована. Ранее automatic approval review отклонил push
кода/тестов/отчётов/PNG в VadikB/4K_MBTI из-за отсутствия прямого разрешения на такой
экспорт. Новых попыток и обходов не делали. Для продолжения требуется прямое
разрешение пользователя на этот состав, push своей ветки и draft PR; обязательные
CI frontend/pytest проверяются для точного нового head, full-verification — после
отдельно разрешённого Ready. Merge/deploy не разрешены.

Изменённые UI исходники: web/index.html, web/js/answer-drafts.js,
web/js/screens/interview.js, web/styles/screens/interview.css,
web/styles/screens/onboarding.css, web/styles/utilities.css. Регрессии:
tests/browser/{answer-drafts,postw02-assessment-ui}.spec.mjs,
tests/frontend/{answer-drafts,postw02-assessment-ui}.test.mjs. Дополнительно dist,
свидетельства и локальная документация05. Интеграция REPORT_08 сохраняет его код.

Откат UI: отменить patch коммита458b698 с сохранением принятого main, затем
пересобрать web/dist и повторить frontend/browser checks. Изменений схемы или данных
в UI-follow-up нет. Полный task05 не слит, локальный bundle содержит исходный base
и всю ветку; исходные7299920 и458b698 сохранены в истории. Не откатывать main/REPORT_08
ради отката оформления. Ручная приёмка и CI перед слиянием остаются отдельными.


### Подготовка к разрешённому merge и регрессии полного CI

Поручение владельца «Хорошо, сливай на main» разрешило push, PR/Ready, следующий
PATCH и штатный deploy на test. Создан PR241; base02596d7/2.1.25, candidate2.1.26.
Первый полный CI на4c26656: frontend/pytest и четыре runtime-shard PASS; integration
и fast-browser FAIL. Ошибки исправлены без ослабления production guards:

- Изолированный queue fixture создавал только таблицу очереди; новый maintenance
  требует draft expiry table. Fixture теперь создаёт минимальный expiry-контракт,
  только если таблицы ещё нет, и удаляет только свою таблицу при teardown.
  Существующая полная runtime-таблица не заменяется. Production schema/cleanup прежние.
- W02 readiness mock не знал GET draft и бросал unexpected-request exception.
  Добавлен точный owner/Cycle/AS/slot read-only projection; проверяется метод GET.
- E01 draft fixture теперь возвращает настоящий контракт чтения/записи с CAS и
  deadline. Reload по-прежнему обязан восстановить введённый текст.
- Общий бренд сохраняет20/18px и700; desktop line-height24px сохраняет принятую
  геометрию auth. Кнопка отправки48px (padding11 + border1 + text24), соответствует
  min48 эталона и прежнему E01; нормальные/disabled токены прежние.

Локально после исправления: четыре ранее упавших browser-теста PASS; queue+draft
SQL14 PASS как на существующем test-контуре, так и на заново созданной пустой
изолированной test-БД. Новая БД удалена, native PostgreSQL остановлен. Frontend380
PASS, UI05/02 PASS7. Native PNG/JSON перезаписаны окончательными размерами кандидата;
повторный UI05 PASS4. Логи: ci-regressions/ci-clean-sql/ci-ui-final.log.gz.
Полный CI повторяется для нового head в том же PR; merge разрешён только после PASS.
