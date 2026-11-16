# POSTW02-01 — результат доработки после визуальной сверки

16.11.2026. Локальный результат **PASS в проверенной области**. Та же ветка
`codex/p4k-postw02-01`, предыдущий результат `dc65d392a99216610d80324accb2d4d833936366`
сохранён. Base `2afcc37912fb2219f0710a5836b7417ce01d8e8e`, версия приложения 2.1.11.
Эталон v10: `e44fa78efb1ec8605b28cf9bc2c2272da2b9122a`.
[Снимки результата](HEADER_REVIEW.html), [план и основания](POST_REVIEW_PLAN.md),
[identity source/dist/evidence](evidence/header-review-refine/identity.json).

## Что изменено

- `app-header.js` выделяет общее отображение identity и навигацию на существующей
  шапке. Вторая шапка/копия для кабинета не создана. Это первое извлечение общего
  JS-компонента из прежней повторяющейся HTML-разметки; его participant-вариант
  включён только для кабинета. Другие панели не переводились на новый компонент.
- Отображается полное доступное `user.full_name`, без угадывания порядка ФИО и без
  замены именем прототипа. Пробелы нормализуются, инициалы — первые буквы первых двух
  слов. Только пустое/отсутствующее имя даёт «Участник»/«У». `greeting_name=коллега`
  не выдаётся за имя. Данные вставляются через textContent.
- Аватар перед именем, как в v10: круг 32×32, фон `#F0F0F0`, тёмные инициалы
  `#222C30`, интервал до имени 10px. На mobile имя скрывается в строке шапки по
  эталону и доступно в меню пользователя; имя также есть в aria-label/title.
- «Мои оценки» и логотип вызывают существующий read-only `openDashboard`.
  Старые обработчики профиля, сведений и выхода сохранены. На desktop выход справа
  от аккаунта; на mobile — в пользовательском меню, без перегрузки узкой шапки.
- Три participant semantic tokens в корне `tokens.css` задают фон аватара,
  фон метки `#FAFAFA` и текст подвала `rgb(100 116 139 / 60%)`. Общий footer остаётся
  одним; его тема следует видимой панели. Локальных литералов этих цветов нет.
- Фон страницы, основной текст, бирюзовая кнопка, рамки, сетка, две информационные
  карточки, история, повтор организации и max-width названия программы сохранены.
  Пересобран соответствующий dist; смена хешей импортируемых chunks не означает
  изменения исходников остальных разделов.

## Источники и конфликт палитры

Применены ранее выбранные архитектурные источники и статусы из [TASK](TASK.md),
AGENTS/workflow/matrix, decision-register/архитектурный Registry, первичные
[UX-LK01](../ux-lk01-participant-cabinet.md),
[UX-UI01](../ux-ui01-common-footer.md),
[UX-UI03](../ux-ui03-required-palette.md), reference задания 01 rev1.1/v10.
M1/M7/Change01 и контракты данных этим follow-up не менялись.

| Роль | Прежняя UI Baseline 1.2 / реализация | v10 / прямое новое указание владельца |
| --- | --- | --- |
| Фон нейтральной метки | `#F7F9FB`, `--control-bg` | `#FAFAFA`, `--participant-status-surface` |
| Текст общего подвала | `#68777C`, `--palette-graphite-600` | `rgb(100 116 139 / 60%)`, `--participant-footer-text` |
| Аватар | 36px, тёмный, скруглённый квадрат | 32px, круг, `#F0F0F0`, `--participant-avatar-surface` |

Первичный текст `P4K_UI_Baseline_1.2.txt` (ред.1.2/17.10.2026) и его SHA-256
`20b8c0dafec51b3699371459bab11afb9ec9ae626c7425c5ecdac05897644b3d` зафиксированы
в identity. Путь первичного источника сохранён там полностью. Значения 1.2 действительно
отличаются от v10; прежний отчёт не считается доказательством совпадения этих цветов.

Основание изменения — прямой текущий запрос владельца POSTW02-01, перечисляющий
точные новые значения и требующий общих токенов. Это явно ограниченное изменение
participant-ролей, а не молчаливая отмена всей палитры 1.2. Generic/ADMIN/W02 токены
сохранены. Browser computed-style проверка после переключения видимой панели на
ADMIN подтвердила прежние 36px/тёмный аватар и цвет общего подвала `#68777C`.
Это проверка CSS-изоляции, не полноценный пользовательский путь ADMIN.

В decision-register, Registry, LK01/UI01/UI03 и их применимых первичных основаниях
не найдено согласованного требования сохранять тёмный квадратный аватар или
сокращённое имя. Прежнее поведение найдено в `.user-avatar`/`user-chip` и
`getSignupFirstName`, оно не объявлено самостоятельной нормой. Реальная функция
выхода/меню берётся из действующего `wiring.js`; отдельная прототипная копия не нужна.
Сам v10 (`dist/report.html`, `report.css`, `report-cabinet.css`) задаёт avatar→name,
навигацию «Мои оценки», 72/64px шапку и скрытие имени на узком экране.

## Происхождение содержимого

| Отображение | Рабочий источник и ограничение | Доказательство |
| --- | --- | --- |
| Имя/инициалы | session restore/bootstrap `data.user` → `state.pendingUser` → `appHeaderIdentity(user.full_name)` | `web/js/session.js:106,141`; новые unit/browser known+fallback |
| Организация | `_build_dashboard`: `m5_cycles.organization_id` → `organizations.name`, owner_user_id и membership | `Api/routes.py:685`; прежние owner HTTP checks, backend не менялся |
| Программа | configuration.name связанной personalized profile / assignment; до Cycle — существующее readiness назначение | тот же query и early projection `routes.py:799`; renderer читает card.title |
| Дата истории | `collection_closed_at` закрытого Cycle → card.closed_at → formatAssessmentDate | `routes.py:729`, `dashboard.js:127`; новый browser payload с 13.02.2030 |
| Текущая позиция N | предъявленная started AS, position_no того же Cycle/plan revision с provenance | `Api/participant_dashboard.py:20`; прежние HTTP/provenance checks |
| Знаменатель M | полная сохранённая revision read_plan, checksum/profile/cycle, len(route) | `participant_dashboard.py:9–19`; не число уже materialized Cases |

В production renderer нет подстановки «ООО Север», demo-программ/дат или фиксированного
3 из 8. Новый synthetic payload намеренно отличается: Марина Тестова, центр «Вектор»,
две тестовые программы, 13 февраля 2030, N=2/M=5 при legacy total_cases=1 и неизвестном
completed_cases. Desktop/mobile используют один и тот же dashboard JSON; fallback
меняет только full_name на null. Значения из fixtures не становятся runtime-конфигурацией.
Browser stub доказывает корректное отображение API-ответа, а не работу живой БД;
owner/provenance подтверждены отдельно ранее выполненными server checks.

## Фактические проверки

| Проверка | Статус / доказательство |
| --- | --- |
| Затронутые frontend: LK01 + общая палитра + общий footer | **PASS 12**, `header-review/frontend.log` (сам этот первый запуск также содержит отдельный FAIL нового name fixture) |
| Header identity: известное ФИО/порядок слов, пробелы/одно имя, отсутствие имени | **PASS 3**, `header-review/frontend-name-final.log` |
| Browser known/fallback ×1440/390, новые цвета/аватар, API данные, GET-only logo/nav, exit, overflow320, CSS-изоляция | **PASS 4**, `header-review/result.json`; после avatar→name повторён только затронутый набор, **PASS 4**, финальный `header-review-refine/result.json` |
| Сверка computed avatar и двух цветов с неизменённым exact v10 | **PASS**, `header-review-refine/exact-reference-1440.json`, `exact-reference-390.json` |
| Ручной просмотр четырёх финальных full-page PNG | **PASS**, known/fallback 1440/390; одинаковый dashboard payload |
| `npm run lint:js` | **PASS**, `header-review/lint.log` |
| `npm run build:web` | **PASS**, `header-review/build.log`; последующий refine менял только HTML/CSS и browser assertion, JS/dist не менялись |
| `git diff --check` / source-dist identity / cleanup | **PASS**, identity и cleanup-summary; оба owned registry удалены, оба localhost порта ECONNREFUSED61 |
| Прежний server owner HTTP/outcome | **PASS 24, reuse**, `corrected/backend.log`; backend/schema/контракты не менялись |
| Прежняя проверка saved-plan provenance | **PASS 4, reuse**, `backend-provenance.log` |
| Прежние visual 5сцен×2ширины +2long, unknown/error, ready/return navigation | **PASS 12+1+3, reuse по неизменённой области**, `corrected`, `corrected-refine`, `corrected-navigation`; новые цвета и header перепроверены выше |
| Обязательные GitHub CI/frontend/pytest/full-verification | **NOT_RUN для нового SHA**: существующий PR не найден, публикация нового PR запрещена; workflows не ослаблялись |
| Полный локальный backend/integration/PATH, реальные DB/LLM/mail, Prod, Safari/другие браузеры | **NOT_RUN**, не входят в узкую локальную доработку |

Первый запуск нового identity unit-fixture завершился **FAIL** при импорте:
старый browser config обращается к window, а fixture не создал synthetic window.
Исправлен только тестовый setup; три новых unit-проверки после этого PASS.
Исходный FAIL сохранён, не выдаётся за успешный запуск. Незакрытых FAIL в проверенной
области нет. Полный прежний набор не повторялся ради нового отчёта.

Все browser runs: workers1/retries0, whole180s/test60s/idle60s, собственный ephemeral
HTTP, afterAll.close и bounded owned-process teardown. DB/LLM/mail=0. Снимки текущего
результата относятся к финальному refine, снимки первого follow-up сохранены как история.
Точные команды есть в плане/runner и логах; исходный reference checkout не изменялся.

## Оставшиеся различия и передача

- Реальные user menu/стрелка раскрытия/выход и строка версии 2.1.11 отсутствуют
  в прототипе. Сохранены функции существующего продукта и единый footer UX-UI01;
  строка версии делает footer выше эталона. Демо-имя и плашка «Прототип» не перенесены.
- Реальные имена и данные назначений меняют длину текста/переносы относительно
  demo-сцены. В новой паре screenshot desktop/mobile данные одинаковы; mobile имя
  доступно в меню, как описано выше. Совпадение всей страницы pixel-perfect не заявлено.
- Подтверждённых оставшихся расхождений в запрошенных avatar/status/footer/name
  свойствах не выявлено. Конфликт исходных цветов 1.2/v10 явно зафиксирован выше.
- `list_artifacts` вернул пустой список. `gh pr list --state all --head
  codex/p4k-postw02-01` и поиск POSTW02 вернули []. Ссылка/номер существующего PR
  запрошены у владельца. **Обновление существующего PR и его CI — NOT_RUN** до
  однозначного определения цели. Новый PR/ветка не создавались, push не выполнялся.
- Merge/deploy/Ready/version bump не выполнены. Задания02–05 не включены. Откат —
  revert собственного follow-up commit с кодом, dist и тестами; данные не менялись.

Локальный commit/SHA после сохранения записывается во внешний DELIVERY_STATUS.json,
чтобы не создавать самоссылочный commit. Человеческая приёмка остаётся за владельцем.
