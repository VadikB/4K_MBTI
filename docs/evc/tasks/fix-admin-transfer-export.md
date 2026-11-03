# FIX-ADMIN-TRANSFER-EXPORT: восстановить перенос участника

## Результат и область

После подтверждения формы «Перенести» frontend вызывает уже реализованную
`transferAdminOrganizationMember`. Включены только export entry-модуля и регрессионная
проверка. Backend, API, данные, схема БД и правила переноса не меняются.

## Источники и решения

- Основание: дефект на `test`, подтверждённый владельцем 2026-11-03; сборка `2.0.51`, commit `7d8e271`.
- Прочитано: `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `docs/evc/verification-matrix.md`, `docs/evc/review-checklist.md`, `tests/README.md`.
- Трассировка: submit-handler → lazy entry export →
  `transferAdminOrganizationMember` → `POST /users/admin/users/{user_id}/transfer-organization`.
- Пробел: существующий frontend-тест не проверял export entry-модуля.
- Стоп-условия: все — нет; публичный контракт, права, данные и предметный смысл не меняются.

## План, критерии и проверка

- [x] Экспортировать `transferAdminOrganizationMember` из lazy entry-модуля.
- [x] Добавить регрессию на связку handler → export.
- [x] `node --test tests/frontend/arch30-organization-transfer.test.mjs` — 3 PASS.
- [x] `node --test tests/frontend/*.test.mjs` — 125 PASS.
- [x] `npm run lint:js` — PASS.
- [x] `npm run build:web` — PASS; hashed frontend-сборка обновлена.
- [x] `git diff --check` — PASS.
- [ ] После деплоя: ручной перенос на `test` с согласованным тестовым участником.

## Выпуск, риски и откат

- Ветка: `codex/fix-admin-transfer-export`; `branch_push=false`, `pr=false`,
  `merge=false`, `deploy=false`, `version_bump=true` (`2.0.52`), `artifact_publish=false`.
- `npm run ready:prepare -- --candidate 2.0.52` — PASS; кандидат подготовлен от `main@7d8e271`.
- Риск: минимальный; frontend получает доступ к уже существующей функции.
- Откат: revert двух изменений кода/теста; миграции и восстановление данных не требуются.
