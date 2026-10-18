# UX-CMP01 — сравнение с предыдущей оценкой

Статус: `READY_FOR_PR`. Ветка: `codex/ux-cmp01-previous-assessment-comparison`.
База: `4ff61da1b0f8f1e8dbe680e7160ec61cfcb2c9e3` (`origin/main`).

## Результат и границы

Задача добавляет участнику read-only сравнение выбранной сохранённой версии
Report с завершённым предыдущим Cycle того же пользователя и организации.
Числовая разница разрешается сервером отдельно для каждого Skill только при
доказанной сопоставимости snapshots. Отсутствующее доказательство даёт
`not_confirmed` и два независимых среза без delta.

Не входят: новый расчёт Results, изменение M2/M6, вывод роста/падения, проценты,
цветовая интерпретация, LLM-вызов, миграция, изменение опубликованных артефактов,
UX-UI02 и сравнение разных участников/организаций.

## Прочитанные источники и версии

- `AGENTS.md`, `README.md`, `CONTRIBUTING.md`;
- `docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`;
- Product 4K context/Registry, Change 01 от 01.10.2026 и task SourceSet;
- `m8-results-report-contract.md`, `m8-partial-result-contract.md`;
- UX-CMP01 v1.1 от 17.10.2026;
- текущие M8 Results/C-67, REL01 access, REP01/RAD01 UI и тесты.

UX-CMP01 задаёт требования продукта, но не заменяет инструкции репозитория.
Источником отображения остаются две неизменяемые C-67 revision; текущие runtime
пакеты не объявляются CURRENT.

## Правила и трассировка

| Источник | Правило | Реализация | Проверка |
| --- | --- | --- | --- |
| M8/C-67 | представлять сохранённые факты | projection точных report/result revisions | HTTP + unit |
| UX-CMP01 | сервер решает сопоставимость | `allowed/not_allowed/not_confirmed` по Skill | unit matrix |
| M6 | `0` — Score, `null` — отсутствие | проверка `is not None`, без truthiness | unit/frontend |
| REL01 | право проверяется на оба отчёта | owner + organization membership для пары | HTTP/integration |
| UX-CMP01 | разные роли не сравнивать численно | `not_allowed`, два независимых среза | unit/frontend |
| EVC | GET не меняет доменные данные | без таблиц, пересчёта и генерации | integration fingerprint |

## Стоп-условия и решения

- Отсутствие обязательного snapshot не блокирует экран: это штатный
  `not_confirmed` без delta.
- Смена владельца, организации, незакрытый/тот же/future Cycle или отозванное
  право блокируют выдачу пары.
- Неоднозначность предметного текста не дополняется эвристикой: совпадение имён,
  дат или чисел не считается доказательством.

## Проверка и откат

Минимум: Python/JS syntax, unit матрица сопоставимости, frontend DOM states,
релевантные M8/REL01 HTTP и integration, web build, browser acceptance в доступном
Chromium и обязательный CI. Физические браузеры фиксируются `NOT_RUN`, если среды
нет. Откат — revert PR; сохранённые Results/Reports и схема не меняются.

## Фактический результат

- добавлен серверный контракт `m8-report-comparison/1.0.0` без новой таблицы;
- по умолчанию выбирается последний более ранний закрытый Cycle; участник может
  выбрать другой доступный завершённый Cycle, один точный Report на Cycle;
- право, владелец, организация, закрытие и временной порядок проверяются для пары;
- числовая delta появляется только при доказанной сопоставимости конкретного Skill;
  иначе показаны два независимых значения и причина;
- `0` сохранён как Score, `null` и partial не заменяются нулём;
- добавлен PDF точной выбранной пары через существующий Typst pipeline;
- GET остаётся projection: Results, Reports, schema и артефакты не изменяются.

## Фактические проверки

- Python/JS syntax — `PASS`;
- unit + M8/REL01 HTTP regression — `PASS`, 29/29;
- frontend suite — `PASS`, 58/58;
- `npm run lint:js` — `PASS`;
- `npm run build:web` — `PASS`;
- реальная компиляция comparison PDF — `PASS`, `%PDF`, 17 281 byte на fixture;
- Playwright Chromium desktop + 360 px, numeric/mixed/PDF link — `PASS`;
- DB integration — `NOT_RUN`: `TEST_DATABASE_URL` не настроен; изолированная БД
  обязательна и база разработчика не использовалась;
- физические Safari/Chrome/Яндекс на iOS/Android/Windows/macOS — `NOT_RUN`:
  соответствующие среды отсутствуют.

Перед merge обязательны review и CI. Откат — revert этого PR; данные не требуют
миграции или восстановления.
