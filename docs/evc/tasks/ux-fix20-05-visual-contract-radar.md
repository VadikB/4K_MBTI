# UX-FIX20-05 — визуальный контракт карточек и M8-радара

## Основание и результат

- Источник поручения: `P4K_UX_Fixes_2026-10-20`, редакция 1.0, задача 05.
- База: `95b2c45c3817bdd0310cbcf4c1f0f024035b6571`, `main`, версия 2.0.11.
- F06: внешний `.admin-organization-card` наследует `--radius-xl` (20px) вместо принятого радиуса карточек 8px.
- QA19-04: мобильный M8 уже использует номерные оси и видимый список полных названий. На desktop при минимальной ширине SVG 900px подписи `13` SVG px отображаются примерно как 12,2 CSS px, а шкала `12` SVG px — как 11,25 CSS px; это ниже критериев 14/12 CSS px.
- Результат: карточки управления организации имеют радиус 8px; desktop-подписи и шкала M8 читаемы на средних ширинах без изменения данных, шкалы 0–3 и CMP01.

## Источники и границы

- `AGENTS.md`, `README.md`, `CONTRIBUTING.md`.
- `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`.
- `docs/architecture/product-4k/1.0/context.md`, `docs/architecture/product-4k/registry.md`.
- `docs/architecture/product-4k/1.0/updates/2026-10-01/README.md` и `docs/methodology/source-sets/2026-10-01/manifest.json`.
- Пакет владельца: `COMMON.txt`, `ACCEPTANCE.txt`, `tasks/05_UX-FIX20-05_Visual_Contract_And_Radar.txt`, `reference/admin-account-prototype/DESIGN_CONTRACT.md`.
- Не меняются M8-расчёт, значения, пропуски, сравнимость, сохранённые результаты, палитра, шрифт, навигация и глобальная система радиусов.
- Реальные iOS/Android/Windows/macOS и окончательная визуальная приёмка владельца/маркетолога остаются вне технической проверки.

## Реализация и проверка

- Адресно переопределить внешний и вложенные карточные поверхности организации на `--radius-sm` (8px), не затрагивая pill/круглые контролы.
- Увеличить SVG-размер desktop-подписей M8 так, чтобы при фактическом масштабировании сохранялись минимум 14/12 CSS px.
- Browser-регрессия проверяет 320, 360, 375, 390, 430, 768, 1024, 1366 и 1440 CSS px; 683px моделирует layout 1366px при 200% масштабе.
- Синтетический M8 включает длинные названия четырёх компетенций, 0/3, пропуски, частичный результат, сравнимый и несравнимый предыдущий результат, resize, клавиатурный переход и снимки 390/768/1024.
- Минимум: `git diff --check`, `npm run lint:js`, frontend-тесты, `npm run build:web`, адресный и полный browser-набор. Backend выполняется по полному CI/релизному прогону, хотя предметная backend-логика не меняется.

## Риски и откат

- Риск ограничен геометрией admin-карточек и размером SVG-текста M8; browser-тест проверяет границы, пересечения и горизонтальный overflow.
- Откат: revert PR. Миграций, изменения API, данных и опубликованных артефактов нет.

## Передача состояния

- Версия кандидата: 2.0.12.
- `git diff --check` — PASS.
- `npm run lint:js` — PASS.
- `node --test tests/frontend/*.test.mjs` — 66 PASS.
- `npm run build:web` — PASS.
- Backend без integration/e2e/llm — 485 PASS.
- HTTP/e2e — 66 PASS.
- `npx playwright test tests/browser/auth-r03.spec.mjs --workers=1` — 45 PASS.
- `scripts/check_release_version.py --base-ref origin/main` — PASS, 2.0.12.
- Chromium-проверка охватывает синтетический M8 и снимки 390/768/1024 в JSON browser-result/CI artifact. Реальные устройства — NOT_RUN; окончательная визуальная приёмка — за владельцем и маркетологом.
- PR, итоговый SHA, CI/deploy-test и live test дополняются после публикации.
- Открытых продуктовых решений нет.
