# CHECKS — P4K-REPORT-FIX-02

17.11.2026. Base/FIX-01 `71a9c535cee4aea094d2b49c2b73f39e22f99bbe`,
code candidate/tested SHA **`9422308cce138fd39330412ee7a89021797a678f`**, 2.1.28.
Ветка `codex/p4k-report-fix-02`. Последующая фиксация evidence/STATE меняет только
документы; приложение, сборка и тесты соответствуют этому SHA.

## Результат и прослеживаемость

M8 v1.2 §2/§7.3 и M6 v1.8 §7 → неизменные четыре исхода/числа/допуск →
`m8-report-comparison/1.2.0` → `Api/m8_report_comparison.py`, серверный PDF v3,
`web/js/utils/report-comparison.js` → общая fixture, unit/HTTP/browser/PDF ниже.
PM-06 LU-06.2/06.4 представляет сохранённые результаты;
PM-07 LU-07.1/07.2 размещает/выдаёт их. Admission и расчёт Scores не изменялись.

В обеих сторонах сохранены outcome, completeness (включая неизвестную),
публичные причины/ограничения и allowlisted claims только своего Cycle/Skill.
Старые previous/current/difference и endpoint совместимы; primary C-67/Results
не переписываются. Общие ограничения находятся в ссылках на отчёты, локальные —
рядом с показателем. Новая полнота из отсутствующих полей не выводится.

## AC01–08

| AC | Фактический результат |
| --- | --- |
| 01 | **PASS**, фактическая `npm run preview:reports` напечатала `http://127.0.0.1:18972/__reports/` и code SHA. Меню содержит P01–P06; внутри настоящий product HTML/CSS/dist. Без анкеты/приглашения/кейсов. Два старта после close на том же порту дают 200 и шесть примеров: [lifecycle](evidence/preview-lifecycle.json). |
| 02 | **PASS**, P01 0/2.25/3, три режима/клавиатура/свой навык/цитата. P02 все четыре исхода; непрерывный участок отделён пропусками, нет замыкания через них. В K1 две числовые оси — точки без линии/заливки. REPORT-05 проверяет также пустой результат и один 0. |
| 03 | **PASS**, P03 две серии/даты и квадратные маркеры серой пунктирной серии. Независимые А 1.75→2.25/+0.50, Б 0→0/0, В 2→1.75/−0.25 совпали в списке/панели/реальном PDF. Конкретная пара и выбранный навык пережили reload, «К отчёту» и повторное открытие. |
| 04 | **PASS**, P04 1.50→1.75/+0.25. У обеих сторон outcome=partial_score/completeness=partial, одинаковая собственная непустая часть исходного required set, подпись/ограничение/полый маркер. Настоящий compare_reports разрешил разность; PDF сохранил обе частичности и причины. Разность не названа доказанным развитием. |
| 05 | **PASS**, P05 mixed: А +0.50, Б изменён included set, В full/partial, Г observations, Д no_result. Б/В без delta и общей соединённой фигуры; два вида без числа различимы. Разные роли дают separate; поздний ответ старой пары не подменяет новую. |
| 06 | **PASS в области локальной технической проверки**, Chromium 1440×900 и 390×844; 320 px/200% не создают горизонтального переполнения и потери управления. Панель справа на desktop, ниже на телефоне; все навыки/серии доступны шкалами. Клавиатурный выбор/возврат работают. Эталонные сцены прочитаны и визуально просмотрены, [список фактических имён](evidence/reference-scenes.json). ADMIN при 390: scrollWidth=390, Onest, «Открыть»/«PDF»; тёмное семейство сохранено. Пиксельное соответствие ADMIN не заявляется. |
| 07 | **PASS**, P06 A→история→B503 очищает текст/число/панель A; «Успешный повтор» и «Повторить» показывают B. Отказ PDF/успех проверен из отчёта, истории, ADMIN и сравнения; контекст сохраняется. Регрессии FIX-01 также проверили network/JSON200/неверную сигнатуру/timeout, resize после ошибки, поздний PDF и duplicate click. |
| 08 | **PASS в заданном локальном контуре**: серверный admission неизменён, UI не рассчитывает delta, число осей берётся из сохранённого массива. Unit/HTTP проверяют совместимость, неизменность входов и отсутствие private полей; существующие ACL/REPORT-09 регрессии проходят. Собственные процессы остановлены, LLM=0/писем=0/рабочей БД=0. |

В задании названы report-limited/report-insufficient; в фактическом v10 review это
**report-partial/report-empty**. Использованы именно существующие переходы, а не
новые придуманные URL. Для оболочки переиспользован текущий `initAppHeader` и
`product-brand` POSTW02, профиль/выход/навигация действующие. Новый динамический
индикатор не проектировался. В опубликованной разметке кабинета отдельной точки
у бренда нет; сохранено его существующее представление, новая индикация не добавлялась.

## Проверки

Backend/HTTP выполнялись с `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0`.
Все browser: workers=1/retries=0/timeout=30000/global-timeout=600000.

| Команда | Итог / evidence |
| --- | --- |
| `npm run test:backend` | **1224 PASS**, 662 deselected, 46.88 sec, exit 0; [лог](evidence/backend-final.log.gz). Включает новую компактную группу `test_report_fix02_projection.py`: независимые числа/outcomes, legacy/null, отсутствие private, неизменность, настоящие PDF. |
| `npm run test:backend:http` | **202 PASS**, 15 deselected, 16.57 sec, exit 0; [лог](evidence/http-final.log.gz). Новый HTTP→real compare→real PDF частичной пары, прежние проверки доступа сохранены. SQL connection подставной; рабочая БД не читалась. |
| `node --test tests/frontend/*.test.mjs` | **404 PASS**, exit 0; [лог](evidence/frontend-final.log.gz). |
| `npm run lint:js` | **PASS**, exit 0; [лог](evidence/lint-final.log.gz). |
| `npm run build:web` | **PASS**, exit 0; [лог](evidence/build-final.log.gz), [SHA-256 48 файлов](evidence/build-sha256.json). После сборки diff web/dist относительно code commit пуст. |
| `npx playwright test tests/browser/report-fix02-preview.spec.mjs tests/browser/report04-personal.spec.mjs tests/browser/report05-radar.spec.mjs tests/browser/report06-history.spec.mjs tests/browser/report08-admin.spec.mjs tests/browser/report09-correction.spec.mjs tests/browser/report10-pdf.spec.mjs --workers=1 --retries=0 --timeout=30000 --global-timeout=600000 --reporter=line` | **38 PASS**, 29.1 sec, exit 0; [лог](evidence/browser-final.log.gz). Три новых сценария используют общий preview/fixtures и настоящую сборку; старые fixtures/ожидания сохранены. |
| `pdftoppm …` и `pypdf` | **PASS**: оба новых PDF просмотрены, текст/кириллица/оба периода/полноты/0/разности сохранены; отсутствие перекрытия и обрезания проверено визуально. |
| `git diff --check` | **PASS**, exit 0. |
| `lsof -nP -iTCP:18964 -iTCP:18965 -iTCP:18966 -iTCP:18968 -iTCP:18969 -iTCP:18970 -iTCP:18972 -iTCP:18973 -sTCP:LISTEN` | Нет вывода, exit 1: слушающих preview нет. CLI остановлен Ctrl+C; afterAll закрывает серверы/Chromium; отдельно проверено закрытие TTL с укороченным интервалом 150 ms при штатном default=15 минут. |

[Identity](evidence/preview-identity.json) фиксирует реальную команду, SHA,
хеши исходников/сборки, меню и фактические ADMIN-метрики.
[Источники](evidence/sources.json): 43 файла reference совпали с manifest;
fetch подтвердил origin/main=base, diff пуст. Ни source sets, ни REPORT-11 не менялись.

## Визуальные артефакты

Четыре представительских изображения:

- [Один отчёт, 1440](evidence/single-1440.png).
- [Две серии, 1440](evidence/comparison-1440.png).
- [Частичная пара по направлению, 390](evidence/partial-390.png).
- [Mixed: только допустимые точки, 390](evidence/mixed-390.png).

Два новых PDF: [P03](evidence/normal-comparison.pdf), [P04](evidence/partial-comparison.pdf).
Исторические изображения/PDF, перезаписанные прежними тестами, восстановлены.
Новые результаты сохранены только в этой карточке.

## Review, исправленные сбои и пределы

Self-review: проверены потребители 1.2.0, allowlist claims, независимые Cycles,
нулевой Score, пропуски/менее трёх осей, URL/epoch/lifetime, late response и
PDF state при resize. В первой серии browser собственные проверки учитывали
скрытый одиночный график; scope исправлен на вид сравнения. В локальном сценарии
ADMIN выбиралась кнопка «Открыть» вместо «PDF» — исправлен selector. Эти начальные
сбои сохранены [1](evidence/browser-initial.log.gz), [2](evidence/browser-second.log.gz).

Финальный расширенный прогон выявил реальную регрессию resize: полная перерисовка
вида удаляла ошибку PDF. Теперь тот же DOM action сохраняется на той же паре;
смена пары по-прежнему подавляет старый запрос. Начальный [FAIL](evidence/browser-resize-failure.log.gz),
после исправления code SHA 833ff7d все 38 PASS. Финальный PDF-only commit 9422308 удерживает карточку навыка целиком на странице; после него повторены все применимые наборы с теми же PASS. PDF-вёрстка также проверена после
удаления лишнего символа переноса. Три frontend source assertion обновлены под
новый модуль/«Разность» и точный разрешённый цвет #64748B; защита палитры сохранена.
[Первый frontend лог](evidence/frontend-initial.log.gz).

NOT_RUN: PostgreSQL integration (схема/поведение БД не менялись; применима HTTP
строка матрицы), полный реальный путь оценки/реальные LLM/почта (вне объёма),
CI/push/PR/merge/deploy/version bump (текущий запрос — локальный результат).
Это техническая проверка synthetic fixtures, не доказательство качества M6,
развития человека, полного набора прав на реальной БД или человеческая приёмка.

Откат — обратный diff приложения/сборки/аддитивной проекции/preview.
Сохранённые Results/C-67, права, публикации и Scores неизменны.
Команда владельцу и фактические кнопки — [Как посмотреть](HOW_TO_VIEW.md).
