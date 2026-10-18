# UX-UI03 — обязательная палитра и графитовая админка

Дата: 18.10.2026. Base: `main@9141be150b07b8f4c385cdb7d4a88bdaf5aa0fef`.
Ветка: `codex/ux-ui03-required-palette`.

## Границы и решения

Включено: сохранение источников, единые цветовые/семантические токены, общий Onest,
canvas, состояния кнопок, ошибок и representative status-компонентов существующих
AUTH/ADMIN/CHAT/ЛК/Report экранов. Не включено: UI01, E01-ADD01, RAD01, CMP01, UI02,
изменение layout, API, данных, прав и предметной логики.

Стоп-условия: все «нет». Точные цвета и их назначения прямо заданы владельцем;
схема/данные/PM/LU не меняются; откат — revert UI/docs commit, сохранённых данных нет.

## Источники и проверка

- `UX-UI03_Required_Palette_and_Graphite_Admin_2026-10-17.txt`;
- `P4K_UI_Baseline_2026-10-17.txt`, редакция 1.2;
- `палитра.pdf`, 1 страница, визуально отрендерена и проверена;
- SHA-256 PDF совпал: `6eabd7841d5f951f2ddc2bfec50cde9f74aea0732c25c2457482de9c6226c5ea`;
- README, CONTRIBUTING, EVC workflow/matrix, Product 4K context/registry,
  Change 01/manifest, текущие HTML/CSS и frontend-тесты.

## Прослеживаемость

| Правило | Токен/компонент | Проверка |
| --- | --- | --- |
| canvas `#F6F9F9` | `--palette-canvas`, `--bg-soft` | static token + computed style |
| admin primary `#222C30/#FFFFFF` | admin panel overrides | frontend + browser |
| participant primary `#18B8C6/#222C30` | `.primary-button` | frontend + browser |
| wait `#FFE5E0/#FF563D` | warning aliases/status pills | frontend + browser |
| ready `#D9F6F8/#222C30` | success aliases/status pills | frontend + browser |
| errors `#B42318` | `--danger`, error states | frontend + browser |
| общий Onest | global font tokens/local font | computed style |

## Состояние

- [x] Разведка и источники.
- [x] Решения и границы.
- [x] Реализация и сборка.
- [x] Визуальная проверка representative экранов.
- [ ] PR / обязательный CI / merge после решения владельца.

## Фактические проверки

- `git diff --check` — PASS;
- `npm run lint:js` — PASS;
- `node --test tests/frontend/*.test.mjs` — PASS, 48/48;
- `npm run build:web` — PASS;
- in-app Chromium, реальные computed styles — PASS: canvas `rgb(246, 249, 249)`,
  Onest, admin primary `rgb(34, 44, 48) / rgb(255, 255, 255)`, participant primary
  `rgb(24, 184, 198) / rgb(34, 44, 48)`, error `rgb(180, 35, 24)` на
  `rgb(255, 229, 224)`;
- визуальная проверка AUTH на desktop viewport — PASS, без изменения layout;
- iOS Safari/Яндекс, Android Chrome/Яндекс, Windows Chrome/Яндекс,
  macOS Safari/Chrome/Яндекс — NOT_RUN: соответствующие среды недоступны локально.

Пользовательский untracked `docs/evc/timer-and-configuration-storage.md` не входит
в задачу и не изменяется.
