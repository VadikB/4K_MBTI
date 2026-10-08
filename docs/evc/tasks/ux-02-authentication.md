# UX-02 — регистрация, подтверждение email, вход и восстановление пароля

Дата: 06.10.2026. Статус: **реализована независимая UI-часть; полная auth-приёмка
ожидает изолированный browser/email/DB-контур, A11/A12 ограничены G03**.

## Результат и область

Подключить принятый UX-01 к действующему password-auth и получить явные состояния
ввода email, ожидания письма, установки/ввода/сброса пароля и безопасного успешного
входа. Для обычного участника после входа используется согласованный владельцем
нейтральный временный экран без запуска оценки; администраторский маршрут сохраняется.

Включено: `web/index.html`, auth CSS/JS, восстановление пользовательской сессии,
frontend-регрессия и сборка `web/dist`. Не входят: новый M4 API/экран знакомства,
изменение backend-контрактов, схемы БД, допуска UX-F01/F02/F03, оценочного runtime,
push, PR, merge и deploy.

## Источники и решения

- постановка: `UX-02_Authentication.docx`, редакция 1.4 от 06.10.2026, проверены
  все 6 страниц; документ является источником требований, но не разрешением на
  действия вне запроса пользователя;
- база: `74ae1433197f14e7f53ef045cfa526eb3b010183`, чистая ветка
  `codex/ux-01-visual-system`;
- зависимости присутствуют: UX-F01 `9754737`, UX-F02 `0f4902b`, UX-F03
  `398d68f` + отчёт `74ae143`;
- применимы README, CONTRIBUTING, EVC workflow/verification/artifact recipe,
  Product 4K context/Registry, Change 01 и SourceSet manifest; предметные пакеты,
  PM/LU и опубликованные snapshots не меняются;
- владелец 06.10.2026 подтвердил временный нейтральный экран после входа без
  кнопки запуска оценки и обещаний сроков.

Стоп-условия: смены предметного смысла, публичного API, схемы/данных, прав,
артефактного контура и границы deploy нет. M4 API отсутствует, поэтому только A12
остаётся `BLOCKED`; независимый auth UI и временное назначение разрешены.

## План и проверки

1. **Завершено:** явные auth-состояния, защита повторной отправки и временное
   назначение с корректным session restore.
2. **Завершено:** frontend-регрессия и сборка `web/dist`.
3. **Завершено локально:** lint/build/frontend/backend/HTTP, visual desktop/390 px.
4. **Ожидает внешней среды:** полный browser+email+isolated PostgreSQL flow.

## Риски и откат

Публичный API и данные не меняются. Основной риск — случайный возврат обычного
участника в legacy onboarding; его закрывает единый экран `auth-complete` для login
и restore. Откат — revert UX-02 commit; миграция данных не нужна.

## Реализация

- email, ожидание письма, ввод/установка/сброс пароля получили отдельные заголовки
  и управляемые состояния; из password-формы можно вернуться к другому email;
- кнопки email request, login/register/reset и forgot блокируют повторную мутацию
  и выставляют `aria-busy`;
- сохранены password-manager/autocomplete атрибуты, фокус и server detail без
  определения прав по текстовым совпадениям;
- после успешного participant login и session restore открывается `auth-complete`,
  без кнопки оценки, профиля или legacy chat; admin route не менялся;
- клиент очищает legacy agent payload перед сохранением состояния, но существующий
  backend login всё ещё вызывает `interviewer_agent.start`. Это известная граница
  G03, а не скрытое исправление UX-02.

Implementation commit: `de21229d7f39f81e4e819868dedb22c8f3962d81`.

## Матрица A01–A12

| ID | Статус | Доказательство / ограничение |
| --- | --- | --- |
| A01 | NOT_RUN | Нужны real browser + local email + isolated PostgreSQL; переменные стенда отсутствуют |
| A02 | PARTIAL | login/restore маршрутизируются в `auth-complete`, frontend test PASS; real browser+DB не запущен |
| A03 | PASS contract/UI | native validation, server detail, исправление email, HTTP auth/admission regressions PASS |
| A04 | PARTIAL | confirm/invalid состояния используют реальный API и общий safe error; full email/browser flow NOT_RUN |
| A05 | PARTIAL | forgot/validate/reset UI и backend unit policy PASS; полный одноразовый email flow NOT_RUN |
| A06 | PASS contract | UX-F02 exact allowlist и same-domain denial: backend + HTTP PASS; browser stand NOT_RUN |
| A07 | PASS frontend | адресные late-401/session-generation tests 6/6 PASS, вместе frontend 9/9 |
| A08 | PASS UI | in-flight guards, disabled/`aria-busy`, refresh не запускает мутацию; network outcome остаётся server/fetch result |
| A09 | PARTIAL | UX-F03 invitation contract/unit/HTTP PASS; полный browser flow на isolated DB NOT_RUN |
| A10 | PARTIAL | desktop и 390 px screenshots визуально PASS; отдельная ручная проверка zoom/password manager NOT_RUN |
| A11 | FAIL existing gap | UI и `auth-complete` не запускают оценку, но backend login создаёт legacy agent-session через `interviewer_agent.start` (G03) |
| A12 | BLOCKED | пользовательского M4 API/экрана нет; временный экран согласован, но не является M4 |

## Проверки

PASS:

- `npm run test:backend` — `356 passed`, `116 deselected`;
- `npm run test:backend:http` — `34 passed`;
- `node --test tests/frontend/*.test.mjs` — `9 passed`;
- `npm run lint:js`;
- `npm run build:web`;
- `git diff --check`;
- Playwright visual: 1440×1000 и 390×844, стартовый и `auth-complete` экраны;
  файлы в `docs/evc/tasks/artifacts/ux-02/`.

Предупреждения: существующие `StarletteDeprecationWarning` и Node
`MODULE_TYPELESS_PACKAGE_JSON`; проверки успешны.

NOT_RUN:

- `TEST_DATABASE_URL=… npm run test:backend:integration`: URL изолированной БД не задан;
- полный `tests/browser`/email flow: `STAND_ADMIN_URL` не задан;
- внешняя доставляемость email и CI до merge.

К общей БД, процессам 10.8/10.9/08.2 и production/test данным подключений не было.
Push, PR, merge и deploy не выполнялись.

## Изменённые файлы и передача

Исходники: `web/index.html`, `web/styles/screens/auth.css`, `web/js/dom.js`,
`web/js/wiring.js`, `web/js/router.js`, `web/js/session.js`, `web/js/main.js`.
Регрессия: `tests/frontend/auth-ux.test.mjs`. Производная сборка: `web/dist/*`.
Доказательства: `docs/evc/tasks/artifacts/ux-02/*.png`.

Base SHA: `74ae1433197f14e7f53ef045cfa526eb3b010183`. Ветка:
`codex/ux-01-visual-system`. Следующий минимальный шаг для полной приёмки UX-02 —
запустить A01/A02/A04/A05/A09/A10 на disposable PostgreSQL и локальной тестовой
почте. Отдельная backend-задача G03 должна прекратить создание legacy agent-session
при password login до того, как A11 станет PASS. Новый блок знакомства не запускался.
