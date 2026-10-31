# PILOT31-01 — Шапки входа и знакомства

## Результат

На входе, восстановлении доступа и знакомстве название продукта и текущий релиз
показываются в отдельной верхней шапке. Версия в auth-footer не дублируется.

## Область

- Включено: shell auth/onboarding, существующий frontend release resolver,
  адаптивность 1440/1024/768/360/320, регрессии разметки и видимости.
- Не входит: поля и валидация входа, права, API/БД, методология, компоновка
  административного кабинета, публикация артефактов и deploy.

## Источники и решения

- Пакет `P4K_Pilot_Tasks_01-03_2026-10-31.zip`, `START_ARCHITECT.txt`,
  `PILOT31-01_HEADER.txt`; manifest SHA-256 проверен полностью.
- Решение владельца от 31.10.2026: релиз размещается наверху рядом с названием;
  повторное согласование не требуется.
- Прочитаны `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, рабочий цикл, матрица,
  шаблон задачи и review checklist; архитектурные context/Registry/Change 01 и
  task manifest. Предметные PM и runtime-артефакты не затронуты.
- База реализации: `origin/main` / `fa38c46`, версия 2.0.43.
- Стоп-условий для UI-изменения нет. Live-инвентаризация PILOT31-02 отдельно
  заблокирована недоступностью разрешённого SSH host с Mac и не подменяется этой задачей.

## Прослеживаемость

`PILOT31-01` → отдельная page header и единый release target → `web/index.html`,
`components.css`, `auth.css`, `onboarding.css`, release/footer helpers → frontend,
build и browser visual checks.

## Критерии приёмки

- [x] Auth/restore используют отдельную шапку 80px; brand не позиционируется от карточки.
- [x] Auth и onboarding показывают один build release в шапке; auth-footer не дублирует его.
- [x] «ЗНАКОМСТВО» центрировано по viewport; mobile допускает две строки без наложения.
- [x] Invalid release скрывает весь бейдж; backend outage сохраняет build release.
- [x] Auth/restore/password/email/loading не меняют существующие контракты и состояния.

## План проверки

- `node --test tests/frontend/release-version.test.mjs tests/frontend/ui01-common-footer.test.mjs tests/frontend/pilot31-entry-header.test.mjs`.
- `npm run lint:js`, `npm run build:web`, `git diff --check`.
- Browser/visual: 1440×1024, 1024×768, 768, 360×800, 320; auth, restore,
  password recovery/email confirmation/loading, onboarding.
- Перед merge: обязательный CI окончательного SHA.

## Риски и откат

Публичные API, данные, схема, права и предметные артефакты не меняются. Риск —
геометрия на малой высоте и неверная видимость общей шапки при смене panel.
Откат — revert единственного UI-коммита; данные не затрагиваются.

## Состояние

- Реализация завершена. Изменены только UI shell, release/footer helpers, сборка и регрессии.
- `node --test tests/frontend/*.test.mjs` — PASS, 116/116.
- `npm run lint:js` — PASS; `npm run build:web` — PASS; `git diff --check` — PASS.
- Четыре адресных Playwright-сценария — PASS, включая auth/restore/no-JS,
  onboarding и viewport 1440×1024, 1024×768, 768, 360×800, 320px.
- Первый sandbox-запуск Playwright — FAIL до тестов (`listen EPERM`); повтор с
  разрешённым loopback — PASS. Это ограничение среды, не дефект продукта.
- Ветка: `codex/pilot31-01-header`, база `fa38c46`.
- Непроверено: реальные email/provider, внешние устройства и test deploy; поведение
  не менялось, перед merge требуется обязательный CI окончательного SHA.
- PR/merge/deploy/version bump/artifact publish: не выполнены.
