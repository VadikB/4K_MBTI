# UX-01 — минимальная визуальная система входа

Дата: 06.10.2026. Статус: **технически готово; готово частично к визуальной
приёмке**. Выполнен только UX-01. UX-02, auth-клиент, backend, БД, API,
методология, manifest и среда 10.8/10.9/08.2 не изменялись.

## Результат

В существующем frontend создана ограниченная экраном входа визуальная основа:
палитра Lidum, типографическая иерархия, поля, primary/secondary actions,
focus/error/status/disabled/loading состояния, мобильная компоновка и
`prefers-reduced-motion`. Действующие auth ID, формы, autocomplete и JS-оркестрация
сохранены. Это визуальный слой, а не подключение нового пользовательского пути.

Onest и утверждённый web-логотип в репозитории/переданных файлах не найдены.
Использован явно временный fallback существующего font stack; новый знак не
перерисовывался и PDF не выдавался за web-ассет. Поэтому финальный визуальный PASS
брендовой части ждёт ассеты и приёмку Кати.

## UX-01.0 — диагностика базы

| SHA | Локальный факт | Связь / различие |
| --- | --- | --- |
| `15f41a2` | отсутствует в локальном object database | Причина отсутствия локальными refs/reflog не установлена; fetch не выполнялся |
| `8654b97ed6605d560111c37cd291f98f82c41457` | локальный `main`, исходная база UX-00 | Предок `84c3302…` |
| `84c3302907a07b2284bb79747582288a93110a42` | исходный HEAD этой задачи | Добавляет к `8654b97…` только `docs/evc/tasks/ux-00-sources-and-mapping.md` |

Исходный worktree был detached на `84c3302…`; основной checkout остаётся на
`main` `8654b97…`. Для работы создана отдельная локальная ветка
`codex/ux-01-visual-system`. Выбор базы обоснован запросом владельца продолжить
этап 1 поверх принятого UX-00 и проверенной ancestry. Reset, clean, fetch и
переключение основного checkout не выполнялись.

## Источники и решения

Прочитаны: `UX-01_Visual_System.docx` v1.4; отчёт UX-00 на `84c3302…`;
`Design_Source_Map.txt`; страницы 1–10 `Lidum_Current_UI_Extract.pdf`; применимые
`AGENTS.md`, EVC-процедуры, `README.md`, `CONTRIBUTING.md`, текущие HTML/CSS и
package scripts.

Прослеживаемость:

- PDF page 7 → graphite `#222C30`, coral `#FF563D`, cyan `#18B8C6`, canvas
  `#F6F9F9` → auth-scoped CSS variables и состояния;
- PDF page 9 → Onest Regular 400 / Medium 500 / SemiBold 600 → временное объявление
  `"Onest", existing fallback`, без подключения отсутствующего файла;
- PDF page 10 → светлый canvas, cyan primary action, graphite text, большие поля →
  auth form layout desktop/mobile;
- UX-01 v1.4 → visual-only, no auth/backend/API → изменены только HTML auth header,
  cache key и `web/styles/screens/auth.css`.

Предложенные рабочие детали, ожидающие визуальной приёмки: card radius 20 px,
control radius 12 px, form width 480 px, mobile padding 22 px, cyan focus ring.
Это UI-детали, не продуктовые или методологические нормы.

## Изменённые файлы

- `web/styles/screens/auth.css` — auth-scoped palette, typography, components,
  interactive states, 520 px adaptation and reduced motion;
- `web/index.html` — доступная текстовая brand lockup и cache key auth stylesheet;
- этот отчёт.

`web/dist` после штатной сборки побайтово не изменился, поскольку JS/entrypoint не
менялись. `package-lock.json` восстановлен после локальной установки зависимостей и
в diff не входит.

## Область стилей и совместимость

Все новые токены и overrides находятся под `.auth-panel`; глобальные tokens,
runtime, dashboard, reports, onboarding, profile и admin styles не перекрашены.
Существующие DOM ID, `name`, `required`, `autocomplete`, submit actions и скрытые
auth states сохранены. Универсальное текстовое поле подготовлено как scoped
`.auth-textarea`, но в product flow не добавлено: M4 API не выдумывался.

Состояния:

- normal/filled: существующие input и form;
- focus: cyan ring, видимый при keyboard Tab;
- invalid: `[aria-invalid="true"]` + coral outline;
- server error: coral surface, icon из существующей системы и текст, не только цвет;
- status/success: cyan surface и существующий live region;
- loading: `[aria-busy="true"]` spinner с reduced-motion fallback;
- disabled: отдельные background/text/cursor без снижения читаемости.

## Проверки V01–V06

| ID | Статус | Доказательство / ограничение |
| --- | --- | --- |
| V01 | PASS частично | Палитра и типографические веса прослежены до pages 7/9/10. Onest/logo files отсутствуют, брендовая финализация ожидает Катю |
| V02 | PASS | Общие существующие `.field`, `.primary-button`, `.ghost-button`, auth state containers переиспользованы; API/M4 props не добавлены |
| V03 | PASS | Интерактивно проверены desktop, 390×844, 360×800, заполнение, keyboard Tab/focus и server-error state; autocomplete/password manager атрибуты сохранены |
| V04 | PASS статически | Все новые selectors scoped `.auth-panel`; глобальные tokens и другие screen CSS не менялись |
| V05 | PASS | `npm run lint:js` exit 0; `npm run build:web` exit 0; `git diff --check` exit 0 |
| V06 | PASS | Diff ограничен двумя UI-файлами и отчётом; backend/auth JS/DB/normative/test не изменены |

Visual QA выполнялась локальным статическим процессом без БД на свободном порту
4173 в изолированном in-app browser. Скриншоты desktop, 390 px error и 360 px focus
были визуально просмотрены в ходе проверки; постоянные бинарные вложения не
создавались, поэтому путь к screenshot-артефакту — NOT_RUN. Это ограничение
доказательств для внешнего review, но не подмена browser-проверки чтением кода.

## Проверки и команды

| Команда | Результат |
| --- | --- |
| `npm install` | PASS; установлены локальные dev dependencies, tracked lock восстановлен |
| `npm run lint:js` | PASS, exit 0 |
| `npm run build:web` | PASS, exit 0 |
| `node --test tests/frontend/*.test.mjs` | PASS, 3/3, exit 0; только существующие auth 401 regressions |
| `git diff --check` | PASS, exit 0 |
| Локальный browser desktop / 390 / 360 | PASS для layout/focus/error; backend path не проверялся |
| Browser auth flow / email / HTTP / DB / LLM | NOT_RUN, не входят в UX-01 |
| GitHub CI / PR / deploy | NOT_RUN, запрещены границами |

## Стоп-условия, риски и откат

Новые предметные нормы, публичные контракты, права, schema и данные не менялись.
Gaps UX-00 по допуску, canonical M4 и late-401 не затрагивались. Неразрешённая
визуальная зависимость ограничена Onest/logo: независимая компоновка продолжена,
финальный брендовый PASS не заявлен.

- Конфиг/схема/данные/deploy: без изменений.
- Безопасность: новых сетевых источников/CDN нет; тестовые адреса `.invalid`.
- Совместимость: CSS ограничен auth panel, HTML IDs/form semantics сохранены.
- Откат: revert локального commit UX-01; данных и миграций нет.

## Передача

Техническая часть UX-01 готова. Для полной визуальной приёмки Катя предоставляет
или подтверждает web-файлы Onest (400/500/600) и векторный/растровый web-логотип,
после чего выполняется адресная замена fallback/brand placeholder и повторная
desktop/mobile проверка. Продуктолог принимает рабочие размеры/интервалы и тексты.

После отчёта работа остановлена. UX-02 не запускать до отдельного поручения и
принятия UX-01.
