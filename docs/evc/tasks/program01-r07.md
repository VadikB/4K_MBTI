# PROGRAM01 R07 — предметные диалоги подтверждения

## Основание и границы

- Источник: `P4K_PROGRAM01_AUDIT_2.0.47_2026-11-02.zip`, `REMAINING_TASKS.txt`, R07; D07, STATUS-R05, UI04/CA05.
- База: `main@07efba71e3260bc296022d31bce7db9fea43c4ec`.
- Результат: заменить только native confirm отзыва персонального приглашения и отмены назначения оценки.
- Не входит: общий редизайн кабинета, другие destructive actions, изменение прав, API или предметных правил R08.

## Решение и прослеживаемость

- R07 → `<dialog>` с `aria-labelledby`/`aria-describedby` → `web/js/wiring.js`.
- Отзыв → участник и email, последствия для ссылки, назначения и обычного входа → точный `invitation_id` передаётся существующему серверному endpoint.
- Отмена → участник и точная оценка, последствия старта и необходимость нового назначения → точный `assignment_id` передаётся существующему cancellation contract.
- Доступность → безопасная кнопка получает начальный фокус; native modal удерживает фокус; Escape закрывает; после закрытия фокус возвращается к исходному действию; touch target не менее 44 px.
- Стили → `web/styles/screens/admin-organizations.css`; мобильные действия полноширинные.
- Регрессия → `tests/frontend/arch30-member-stage.test.mjs`, `tests/browser/auth-r03.spec.mjs`.

## Проверки и результат

- `node --check web/js/wiring.js` → PASS.
- full frontend suite → 127 PASS.
- targeted browser R07 + сохранённые R06 cancellation scenarios → 7 PASS.
- `npm run build:web` → PASS; committed `web/dist` обновлён.
- Полный локальный набор и CI → ожидают стадии PR.

## Риски и откат

- Схема, конфигурация, секреты и персональные данные не меняются.
- Сервер остаётся источником применимости; диалог не расширяет права и не подменяет проверки состояния.
- Откат: revert одного PR; миграций и публикации артефактов нет.

## Флаги выпуска

- `branch_push=false`, `pr=false`, `merge=false`, `deploy=false`, `version_bump=false`, `artifact_publish=false` до отдельного шага передачи.
