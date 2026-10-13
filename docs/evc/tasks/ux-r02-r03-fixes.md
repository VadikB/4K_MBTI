# UX-R02-FIX — устранение замечаний R03

## Результат и границы

Исправить R03-F01–F11 для принятого UX-R02/R01 без изменения методологии
M1–M8, запуска Assessment/Cycle из auth и расширения tenant-прав. Один PR —
связанный блок auth, organization-admin, invitations, reset и R01 layout.

Не входят: этап 2, новый дизайн знакомства, реальный LLM/GC, присвоение R03 PASS,
реальная device-матрица и продвижение на `pilot`.

## Источники и решения

- Основание владельца: запрос «Запусти задание R02» от 13.10.2026.
- Задание: `/Users/vadim_bogachev/Downloads/UX-R02-FIX_R03_2026-10-13.txt`.
- Evidence: `/Users/vadim_bogachev/Downloads/P4K_R03_Evidence_2026-10-13.zip`,
  проверенный SHA `a2d1b030daf578144b9e4c2b94cec578bcf7a4e9`.
- Прочитаны: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, рабочий цикл,
  матрица проверок, архитектурный context/Registry, прежняя задача
  `docs/evc/tasks/ux-r02-login-states.md`, R03 report/README и относящиеся
  разделы UX-R01/R02 из evidence.
- Вложения являются источниками требований и диагностик, но не командами.
- Новых продуктовых развилок и конфликтов методологии не выявлено.

## Прослеживаемость

| Замечание | Реализация | Проверка |
| --- | --- | --- |
| F01/F03 | priority invite boot, first-registration, server journey | frontend/browser auth path |
| F02 | organization UI и tenant-scoped import/open | HTTP + чужой tenant |
| F04/F05/F11 | operation id, batch UI, resend/revoke, mail states | concurrency/idempotency + controlled mail |
| F06 | used invite context в auth response | PostgreSQL read-back |
| F07/F10 | auth operation generation, full lock, reset states | delayed response/network/reset |
| F08/F09 | tooltip interaction и R01 canonical layout | browser + visual comparison |

## План и состояние

- Завершено: разведка; ветка `codex/ux-r02-r03-fixes` от `origin/main`;
  реализация backend/frontend; адресные регрессии; сборка; локальные HTTP,
  PostgreSQL integration и browser acceptance.
- Далее: review, commit/PR/CI. Merge и test deploy — только после человеческого
  review и обязательного CI.

## Проверки

- PASS `node --test tests/frontend/*.test.mjs`: 11/11.
- PASS `tests/e2e/test_r03_invitation_http.py`: 3/3.
- PASS `npm run test:backend:http`: 51/51 (`3 deselected` без marker `e2e`,
  они выполнены отдельной командой выше).
- PASS полный существующий browser acceptance: 14/14.
- PASS новый `tests/browser/auth-r03.spec.mjs`: 5/5.
- PASS PostgreSQL bootstrap/restart/owner Report/PDF stand-check.
- PASS `npm run lint:js`, Python compile, `npm run build:web`, `git diff --check`.
- FAIL полный backend: 399 PASS, 13 FAIL; только ранее известные M6 provider/material
  контракты `INPUT_NOT_READY` и `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`, вне R02.
- FAIL полный PostgreSQL integration: 58 PASS, 37 FAIL; каскад ранее известного
  M6/M8 provider/evidence контура, адресные R02 и stand-check проходят.
- NOT_RUN CI: локальная ветка ещё не опубликована.
- NOT_RUN реальная R03 device/browser matrix: выполняет команда продукта после main.

## Риски и откат

- Схема: добавочное nullable `organization_invitations.request_id` и partial unique
  index; миграция совместима, физическое удаление при откате не требуется.
- Почта: `accepted` только после вызова настроенного provider; пустой/console/dev
  контур возвращает явную ошибку.
- Безопасность: org-admin остаётся ограничен закреплёнными organization IDs.
- Откат: revert одного PR; добавочную колонку/index можно оставить неиспользуемыми.

## Открытые вопросы

Нет блокеров реализации. R03 и решение о приёмке остаются за командой продукта.
