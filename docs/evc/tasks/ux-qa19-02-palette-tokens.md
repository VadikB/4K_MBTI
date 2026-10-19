# UX-QA19-02 — разрешимость токенов палитры

## Результат и границы

Использования отсутствовавших `--palette-cyan-600`, `--palette-coral-600` и
`--palette-graphite-100` сопоставлены с утверждённой палитрой. Акцентные cyan и
coral используют соответственно `*-500`; светлые поверхности используют
`--palette-graphite-050`, а границы — `--palette-graphite-200`.

Предметные данные, оценки, M8-радар, API, права, таймеры, snapshots и методология
не меняются. Новые цвета и совместимые alias не вводятся.

## Источники и решения

- Комплект `P4K_Admin_and_Bugfixes_2026-10-19_v2`, редакция 2.0; checksum 29/29 PASS.
- `COMMON.txt` и `tasks/UX-QA19-02_Palette_Tokens.txt`.
- `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, EVC workflow и verification matrix.
- База: `origin/main@71045de3e4ac6661de04bbf459bc5b8026a0dbee`.
- UX-QA19-01 уже закрыт PR #72 и повторно не реализуется.

Стоп-условия не открыты: изменение ограничено UI-токенами и их тестом. Откат —
revert одного PR; миграция и восстановление данных не нужны.

## Проверки

- `git diff --check` — PASS.
- `npm run lint:js` — PASS.
- `node --test tests/frontend/*.test.mjs` — PASS, 62/62.
- `npm run build:web` — PASS; JS не менялся, существующий `web/dist` остался
  актуальным, CSS подключается напрямую.
- `npx playwright test tests/browser/auth-r03.spec.mjs --grep 'QA19-02'` — PASS,
  Chromium, synthetic routes; auth focus/outline, admin primary и card border,
  ширины 320/360/375/390/430/768/1024/1366/1440 без page overflow.
- Матрица физических iOS/Android/Windows/macOS Safari/Chrome/Яндекс — NOT_RUN:
  соответствующие устройства и браузеры локально недоступны; требуется приёмка
  владельца и маркетолога после deploy-test.

Регрессия обходит все CSS-файлы, проверяет palette-ссылки с учётом fallback,
разрешает цепочки корневых токенов и отклоняет циклы и три устаревших имени.
