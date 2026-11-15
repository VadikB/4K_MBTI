# ADD01 — перепроверка W02

Историческая запись. ADD02 удаляет полный повтор return policy из ready; актуальные
четыре кадра и проверки — [ADD02_CHECKS.md](ADD02_CHECKS.md).

Основание: уточнение владельца rev1.0 от15.11.2026. Продолжение PR224,
base `f5053402ab4fe11ead3447642c960bca9dfa81f9`, PATCH2.1.11 после занятого main2.1.10.
Изменения main/PATH guard сохранены merge8935b31, новый PR не создавался.
Точные source/dist hashes: [checked-content.json](evidence/add01/checked-content.json).
Передаваемый head и окончательный CI — локальный RELEASE_STATUS.json и checks PR.

## Происхождение старого reference

Повторно проверены байты пользовательского LIDUM-W02.html и распакованного
LIDUM-W02.html.gz из ea93a15:204878байт, SHA256 в обоих случаях
`2ae50fbe1ef73b4eb9fa6c808fec16d31475fb5cf79bb3d69ff275d41447170c`.
В HTML нет строки «Версия»,2.1.10 и product runtime. Сам исходник не подменён.

Сохранённый `/private/tmp/p4k-w02-fix-browser.py` объявляет W02_REFERENCE_HTML
как пользовательский путь LIDUM-W02.html. Прежний reference test делал goto file://
с hash stage/show и fullPage=true, но не проверял фактический вход/SHA/scene/fonts,
сетевые запросы или загруженный runtime. Старые plan.json не сохраняли разрешённое
значение env и документ браузера. Реально использованные при старом рендере bytes
по этим записям **не установлены**; возможная перезапись снимка не имеет audit trail.
Инвентарь неизменённых старых PNG и hashes —
[old-reference-inventory.json](evidence/add01/old-reference-inventory.json).

ADD01 сообщает о версии2.1.10 на приложенном reference. При повторном просмотре
сохранённого в ветке reference-failed-locked-1440.png видна карточка без шапки и
подвала в кадре; происхождение строки версии из описания ADD01 по сохранившимся
данным не установлено. Причина расхождения/возможной перезаписи: **UNKNOWN**.
Не выдаём гипотезу о данных demo или времени захвата за установленную причину.
Прежнее утверждение CHECKS о доказанном прямом clean render и достаточный
PASS LOCAL VISUAL **отозваны**. История и старые файлы сохранены, не перезаписаны.

## Новый независимый reference

Новый [w02-reference.spec.mjs](../../../../tests/browser/w02-reference.spec.mjs)
не использует product fixture/server hooks. Перед каждым рендером читает realpath,
проверяет точный SHA. Для каждой пары создаёт отдельный browser context без storage,
service workers blocked, DPR1, locale ru-RU. Навигация к автономному file:// HTML,
точные hash `#stage=preparing&show=1`, `failed-locked`, `ready`, `organization`.
Нет addStyleTag/addScriptTag, DOM-подстановок или продуктовых CSS/JS.
Ожидаются document.fonts.ready, настоящий standalone title, секция ОЦЕНКА и footer.
Проверяются отсутствие внешних scripts/styles, версии и запросов /users/*.

Вход, URL, requests, viewport, capture mode и SHA каждого PNG сохранены рядом с
[восемью reference PNG](evidence/add01-verified/). Viewport1440×1024 /390×844,
fullPage=false, без масштабирования. Ready reference содержит demo8/60/72;
product содержит fixture5/75/48 и прежнюю серверную return policy.

Фактическая команда (из корня worktree):

```sh
python3 /private/tmp/p4k-w02-add01-browser.py add01-verified \
  w02-reference.spec.mjs w02-readiness.spec.mjs auth-r03.spec.mjs \
  --grep 'W02 ADD01|W02-02|PARTICIPANT-LAYOUT-01|AUTH-RESUME.*S0[134]'
```

Прочитанный runner сохранён как [runner-used.py](evidence/add01/runner-used.py),
reporter — [progress-reporter.cjs](evidence/add01/progress-reporter.cjs).
Для воспроизведения в этом checkout runner запускается из корня с теми же аргументами;
его ссылки на `/private/tmp` требуют восстановления reporter по сохранённым bytes.
Непосредственный Playwright command и ограничения —
[plan.json](evidence/add01-verified/plan.json); W02_REFERENCE_HTML фактически проверен
в каждом reference JSON. Полный stdout — [verified.log.gz](evidence/add01/verified.log.gz).

## Техническая приёмка

| AC | Результат |
| --- | --- |
| AC01 | Invitation → оба шага пароля → waiting_for_organization/assignment_sources;1440/390: точный заголовок/описание/примечание ADD01, две secondary48px кнопки, mobile column. Reason остаётся в модели/data diagnostic, отсутствует в видимом тексте. Нет history/saved answers. Frontend отдельно проверяет unassigned/expired/network с тем же reason; browser existing состояния unassigned/expired/access/network сохранены. |
| AC02 | 8 независимых reference рендеров PASS, вход/SHA/scene/runtime/request assertions и receipts. Старое происхождение UNKNOWN, прежнее достаточное visual доказательство отозвано. |
| AC03 | 8 новых product кадров: early + preparing/failed-locked/ready на1440/390. Измерены header/main/card/actions/diagnostics/tail/footer, включая центр всей группы. Таблица различий ниже; галерея открыта и изображения просмотрены. |
| AC04 | 41/41 адресный browser PASS13.6s; из них6 ADD01 product,8 reference, early invitation и existing W02 readiness/start/retry/history/footer. Отдельно AUTH-RESUME S-02/S-03:2/2 PASS2.1s. Refresh не вызывает prepare/start; retry требует server retry_allowed; queued и running дают один live текст при разных model statuses. |
| AC05 | Старые и новые доказательства разведены. Local technical PASS и LOCAL VISUAL RECHECK не являются human TEST или CI. Mandatory frontend/pytest/full-verification нужны на точном новом PR head. |

Локальный минимум: diff-check PASS; lint:js PASS; build:web PASS;
frontend334/334 PASS. Логи — evidence/add01/*verified.log.gz и build-final.log.gz.
Старый FIX01 technical scope с ea93a15 переиспользован для неизменённых issue
message/draft/consent/3questions/competencies/process contracts; новые HTML/CSS
селекторы ограничены standalone и ранним waiting. Backend/схема не менялись,
полный локальный PATH/Report/CI не повторялся. Mandatory CI сохранён.

Ранние capture01(15PASS),capture02(7PASS),final(41PASS) — промежуточные измерения
перед найденными scoped уточнениями. Они не подменяют последний verified run.
Ошибок тестов ADD01 нет, retries=0. В extra auth-команде использован правильный файл
`auth-recovery.spec.mjs --grep 'AUTH-RESUME S-0[23]'`; первоначальный grep другого файла
не выдаётся за проверку этих сценариев.

## Прямая визуальная сверка

[Галерея продукта и исходного HTML](VISUAL_REVIEW.html).
Исходные rect/style/paragraph observations — JSON рядом с PNG;
[comparison.json](evidence/add01/comparison.json) содержит исходные измерения пар.
Все8 product PNG и соответствующие reference просмотрены. Состав/геометрия,
абзацы и отступы сравнивались непосредственно, не только по overflow.

Общие совпадения: desktop header72/mobile64, секция ОЦЕНКА по центру/справа;
карточка x340,width760 / x16,width358; padding32/24,radius8,title22/30 и20/28,
icon40. Ширины текста696/310. Background/text/border/error palette сохранена.
Существующие metrics получили span14/21 и soft background исходного HTML;
mobile gap8 и padding14/12 восстановлены по прямому reference, без новых метрик.
Ready primary48; standalone secondary50 фактических px как в HTML, ранние
waiting secondary48 по явному ADD01. Диагностика свёрнута, margin20,summary44.
Tail через16px после карточки,44px text action с её левого края.

| Пара | Reference card y / height | Product card y / height | Фактические отличия |
| --- | --- | --- | --- |
| preparing1440 |288.5 /363|272.5 /363|Высота/состав/отступы совпали. Product footer128 вместо96 из-за версии: доступная область меньше32, вся группа423px сдвинута центровкой на−16. Индикатор «Подготовка выполняется» в обоих. |
| preparing390 |152.5 /419|136.5 /419|Аналогичная центровка−16 при footer156 вместо124; группа479. Все действия и footer в viewport. Фаза вращения spinner может отличаться. |
| failed-locked1440 |276.5 /387|260.5 /387|Высота и группа447 совпали, центровка−16 из-за версии. Только «Проверить состояние», collapsed «Сведения об ошибке», history под карточкой. Operation ID — demo или fixture, скрыт до раскрытия. |
| failed-locked390 |144.5 /435|128.5 /435|Та же разница footer/центра−16, группа495. Заголовок переносится в2строки одинаково, действия/diagnostics/tail не обрезаны. |
| ready1440 |188.5 /563|128.5 /651|Product на88px выше из-за сохранённого текста return policy72px и16px интервала. Группа711 вместо623; с учётом footer+32 центр даёт y−60. Product5/75/48 и реальное название вместо demo8/60/72. |
| ready390 |88 /697|88 /905|Длинное server name добавляет24px; return policy168+16px добавляет184: всего208. Обе группы превышают свободную область: стартуют с top padding24 и прокручиваются, без fixed overlay. Существующий footer/browser case проверяет доступность нижних действий/подвала. |
| early1440 ↔ organization |308.5 /323|343.5 /281|В HTML нет early сцены. Карточка organization ПОСЛЕ ответов — только геометрический образец. Early содержит1согласованный абзац+note, две48px secondary; нет saved answers/history, есть выход. Product card центрирована в main72..896. Не выдано за равенство сцен. |
| early390 ↔ organization |176.5 /371|181.5 /389|Те же намеренные смысловые отличия. Early текст310px, кнопки по310×48 в колонку; main64..688, card центр совпадает376. Footer не перекрывает карточку. |

Удалён конфликтующий min-height calc(100dvh−164px); panel/shell теперь заполняют
реальную свободную область flex. Убраны inherited description/feature-list отступы,
восстановлены note20/diagnostics20 и secondary padding. Нет ручного margin-top под PNG.
Механизм версии и юридических ссылок сохранён. Иллюстративные SVG и общий бренд
используют существующий продуктовый rendering; пиксельная идентичность всего demo
не заявляется. Серверные числа/return policy не заменены демонстрационными.

## Ресурсы, риски и передача

[resources-final.json](evidence/add01/resources-final.json): все5 owned process groups
отсутствуют, registry отсутствуют, фиксированные18764/18766 и записанные ephemeral
порты закрыты. Все browser contexts закрыты. Restart policy=no; DB/containers/LLM/mail0.
Чужие ресурсы и файлы не менялись. Старые runs/PNG сохранены для аудита.

Риск — scoped UI на controlled fixtures. API/data/admission/start/retry/таймеры прежние;
FIX02 и причина подготовки не расследуются этим изменением. Откат — revert своего PR.
Human review и визуальная приёмка фактического TEST: **PENDING**. Merge/deploy=false.
