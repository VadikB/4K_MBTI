# PROGRAM01 R08 — отзыв приглашения после начала знакомства

Статус: реализация и локальная проверка завершены; ожидает Draft PR и CI.

## Основание и границы

- Внешний аудит `P4K_PROGRAM01_AUDIT_2.0.47_2026-11-02.zip`, SHA-256
  `5cc38524ec2f3c152f7acbb721eb93155c3862673a0a431414f6ef051533d31b`:
  `START.txt`, `REMAINING_TASKS.txt`, R08 / D08 / STATUS-R03 / IN01 / IN02.
- Base: `main@45503202f536fec5e605d43428e84d9e95cf23f3`.
- Ветка: `codex/program01-r08`.
- Один результат: не позволять отзывать ещё не использованную персональную ссылку,
  если адресат уже начал знакомство через существующий обычный вход; объяснить
  штатные конфликты и перечитать применимые действия.
- Не входят: R09, отправка писем, отзыв живых приглашений, новая сущность приглашения,
  изменение M6–M8, схема БД и публикация предметных артефактов.

## Источники и решения

Прочитаны: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
`docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
`docs/evc/artifact-recipe.md`, Change 01 README и task manifest,
`docs/architecture/product-4k/1.0/context.md`, Registry, ADR-002, фактические
контракты `Api/routes.py`, `Api/auth_service.py`, `Api/acquaintance.py`,
`Api/acquaintance_state_store.py`, frontend API/организации и связанные тесты.

Change 01 и M1 v1.4 не меняются и не получают CURRENT. Предметный артефакт не
создаётся. Пробелов, требующих новой нормы, не выявлено: уже существующие строки
`organization_invitations`, `users` и `participant_acquaintance_states` дают точную
связь по организации и нормализованному email.

Техническое решение: revoke сохраняет блокировку точной строки приглашения, затем
берёт ту же блокировку пользователя, которую использует запись acquaintance, и
проверяет начало (`status != not_started` либо `current_step > 0`). Это сериализует
accept/revoke и acquaintance/revoke без новой сущности. Повтор уже выполненного
revoke остаётся идемпотентным. Публичные коды не расширяются: используются
`INVITATION_NOT_FOUND`, `INVITATION_ALREADY_USED`, `INVITATION_STATE_CHANGED`.

Стоп-условия: нет. Смысл оценки, PM/LU, права, схема, миграция, чувствительные данные
и контур развёртывания не меняются. Откат — revert одного PR; данных и миграций нет.

## Изменённые файлы

- `Api/routes.py` — блокировка адресата и запрет revoke после начала знакомства.
- `web/js/api.js` — безопасные сообщения штатных кодов приглашения.
- `web/js/screens/admin/organizations.js` — обновление карточки после конфликта и
  человекочитаемый итог команды.
- `tests/e2e/test_program01_invitation_revoke_http.py` — HTTP-контракт.
- `tests/integration/test_program01_invitation_revoke_db.py` — реальная PostgreSQL
  блокировка, replay, scope и конкурентный accept/revoke.
- `tests/frontend/arch30-member-stage.test.mjs`, `tests/browser/auth-r03.spec.mjs` —
  frontend/browser-регрессии.
- `web/dist/*` — собранный frontend.

## Проверки

- `python -m py_compile Api/routes.py` → PASS.
- `node --check web/js/screens/admin/organizations.js` → PASS.
- `python -m pytest tests/e2e/test_program01_invitation_revoke_http.py -q` →
  4 passed.
- `TEST_DATABASE_URL=postgresql://pytest:***@127.0.0.1:55437/f22_integration_pytest
  python -m pytest tests/integration/test_program01_invitation_revoke_db.py
  --run-integration -q` → 2 passed.
- `node --test tests/frontend/*.test.mjs` → 131 passed.
- `npm run build:web` → PASS.
- `npx playwright test tests/browser/auth-r03.spec.mjs --grep "PROGRAM01 R08"
  --workers=1` → 1 passed.
- `git diff --check` → PASS.

Первый integration/browser запуск внутри sandbox не получил loopback (`Operation
not permitted` / `listen EPERM`); тот же набор повторён с разрешённым локальным
контуром и прошёл. Это не продуктовый FAIL.

## Непроверенное и следующий шаг

Полный `frontend`, `pytest` и `full-verification` точного head ещё не запускались;
они выполняются в PR. Живые приглашения и персональные данные не использовались.
Следующий шаг: review diff, коммит, push и Draft PR; после быстрых проверок — отдельное
решение владельца о release candidate и `Ready for review`.

## Риски и откат

- Конфиг/схема/артефакты: без изменений.
- Совместимость: ранее допустимый revoke остаётся допустимым для `not_started`;
  used и replay сохраняют прежнее поведение.
- Безопасность: чужая организация остаётся 404; UI не расширяет права и перечитывает
  серверную применимость после 404/409.
- Откат: revert PR возвращает прежнюю проверку; сохранённые приглашения и acquaintance
  не преобразуются.

Открытых блокеров нет.
