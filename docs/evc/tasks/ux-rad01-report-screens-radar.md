# UX-RAD01 — экраны отчёта участника и радар

Статус: `IMPLEMENTED_LOCAL`. Ветка: `codex/ux-rad01-report-screens-radar`.
База: `bd27dc8e7b599785c635cc2a8c2920a29cb1b398` (`origin/main`).

## Результат и границы

Задача расширяет существующий участнический M8 Report представлением
`общий обзор → Competency → Skill → основание`: радаром SkillScore 0–3,
горизонтальными шкалами, постоянным текстовым эквивалентом и подробностями
выбранного Skill. Источником остаётся сохранённый C-67 точной Report revision.

Не входят: UX-CMP01 (сравнение оценок), UX-UI02 (финальная настройка подписей и
отступов), новый расчёт, CompetencyScore, Skill Level, Recommendations, новый LLM
вызов, изменение Results/Report schema, прав REL01 или PDF pipeline REP02.

## Прочитанные источники и версии

- `AGENTS.md`, `README.md`, `CONTRIBUTING.md`;
- `docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`;
- Product 4K context/Registry и Change 01 от 01.10.2026;
- task SourceSet от 01.10.2026: M6 v1.8 и M8 v1.2 FROZEN, SHA-256 из manifest;
- `m8-results-report-contract.md`, `m8-partial-result-contract.md`;
- UX-RAD01 v1.1 от 17.10.2026 и `P4K_UI_Baseline` v1.2;
- текущие `Api/m8_results.py`, REP01/REP02/REL01 UI и тесты.

UX-RAD01 и приложения являются требованиями задачи, но не заменяют инструкции
репозитория. HTML-прототип — визуальный референс с синтетическими данными; его
данные и тексты не переносятся в runtime. Общая палитра уже введена UX-UI03 и
используется через существующие tokens.

## Правила и трассировка

| Источник | Правило | Реализация | Проверка |
| --- | --- | --- | --- |
| M6.7.3–4 | 0 — значение, отсутствие Score — не ноль | `score.value == null` не создаёт точку | unit frontend |
| M6/M8, C-67 | четыре исхода Skill сохраняются | маркер/текст исхода без нового расчёта | fixture states |
| M8 PM-06/07 | Report представляет сохранённые факты | данные только из выбранного `report.c67` | REP01/REL01 regression |
| UX-RAD01 | шкала 0–3, fill/outline/bars | три вида, единая геометрия | frontend + browser |
| UX-RAD01 | пропуски не соединяются | линии строятся только по непрерывным сериям | unit frontend |
| UX-RAD01 | график не единственный носитель | постоянный список и SVG text alternative | DOM assertions |

## План проверки

- синтаксис изменённых JS;
- frontend tests, включая full/partial, 0/null, все null и все нули;
- build web;
- релевантные unit/e2e/integration по M8 и REL01;
- browser acceptance 360 px и desktop в доступном Chromium;
- полный обязательный CI перед merge.

Физические iOS Safari/Яндекс/Chrome, Android Chrome/Яндекс, Windows
Chrome/Яндекс и macOS Safari/Chrome/Яндекс фиксируются `NOT_RUN`, если среды
фактически недоступны; viewport-эмуляция не выдаётся за такой PASS.

## Риски и откат

Схема, миграции, конфигурация, артефакты M2/M6/M8 и секреты не меняются.
Основной риск — ложное соединение через отсутствующий Score; он закрывается
чистой функцией сегментации и тестами. Откат — revert этого PR: неизменяемые
Results/Reports и их PDF остаются без изменений.

## Фактические изменения

- добавлена чистая сегментация радара без соединения через `null`;
- добавлены общий обзор и навигация по сохранённым Competency;
- добавлены `Заливка`, `Контур`, `Шкалы`, SVG text alternative и постоянный список;
- полный/частный Score различаются маркером и текстом; `0` не смешивается с отсутствием;
- мобильный общий обзор оставляет все Skills списком, радар появляется для выбранной Competency;
- runtime API, Results, C-67, PDF renderer и доступ REL01 не изменены.

## Проверки

- `node --check web/js/screens/report.js web/js/utils/report-radar.js` — `PASS`;
- `node --test tests/frontend/*.test.mjs` — `PASS`, 56/56;
- `npm run lint:js` — `PASS`;
- `npm run build:web` — `PASS`;
- `.venv/bin/python -m pytest -q tests/unit/test_m8_results.py tests/unit/test_m8_descriptive_report.py tests/unit/test_m8_context_selection.py` — `PASS`, 21/21;
- `npx playwright test tests/browser/auth-r03.spec.mjs --grep "RAD01 renders"` — `PASS`, Chromium desktop + 360 px, изолированный синтетический C-67;
- runtime browser + PDF — `NOT_RUN`: локально не задан обязательный изолированный
  `STAND_ADMIN_URL`; тест корректно отказался запускаться до обращения к данным;
- физические браузеры из матрицы UX-RAD01 — `NOT_RUN`: среды в текущем контуре отсутствуют.

Перед merge обязательны CI и review. Окончательная визуальная приёмка остаётся у
владельца после публикации main; UX-CMP01 и UX-UI02 выполняются отдельными PR.
