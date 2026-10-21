# UX-FIX20-01 — доверенное назначение

## Результат и границы

Исключить self-invite из серверного основания допуска к собственной оценке, сохранив
membership, роль администратора, регистрацию по приглашению и законное назначение
другим уполномоченным лицом. Публичный API, схема БД, методология и использованные
Cycle snapshots не меняются.

## Источники и решения

- Пакет владельца `P4K_UX_Fixes_2026-10-20`, редакция 1.0; задача
  `tasks/01_UX-FIX20-01_Trusted_Assignment.txt`.
- База: `origin/main` `96705b0806df74080d0a62f2896c99407b5fb871`.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, EVC workflow/matrix/recipe,
  Product 4K context/Registry, Change 01, source-set manifest, ADR-002 и traceability.
- Фактический контур: `send_personal_organization_invitations` проверяет полномочия
  автора; `early_readiness` формирует серверный gate journey/acquaintance/start.
- Авторитетное основание в действующей модели — invitation с `created_by_user_id`,
  созданный защищённым endpoint. Сам автор не может назначить себя. Revocation
  сохраняется через `revoked_at`; история не удаляется.
- Противоречий обязательных источников и стоп-условий не выявлено.

## План и критерии

- [x] Найти фактический admission gate и источник назначения.
- [x] Исключить сохранённые и новые self-invite без удаления истории.
- [x] Покрыть self/independent/revoked assignment на PostgreSQL.
- [x] Проверить HTTP self/bulk/retry и итоговый readiness gate.
- [ ] Выполнить локальный минимум EVC, CI, review, merge и deploy-test.

## Совместимость, риски и откат

Схема и данные не мигрируют. Ранее созданный self-invite остаётся регистрационным
артефактом, но больше не является назначением. Независимая активная запись продолжает
давать доступ. Release-gate требует patch-кандидат `2.0.8` от актуального main
`2.0.7`; версия и собранный frontend входят в тот же независимо принимаемый PR.
Откат — revert единственного PR; восстановление данных не требуется.

## Проверки

- PASS `python -m py_compile Api/acquaintance.py tests/integration/test_w02_acquaintance_db.py`.
- PASS `pytest tests/e2e/test_adm19_02_self_assignment_http.py tests/e2e/test_r03_invitation_http.py -q`: 13/13.
- PASS одноразовый PostgreSQL 16 `agent4k_pytest`,
  `pytest --run-integration tests/integration/test_w02_acquaintance_db.py -q`: 2/2.
- PASS `pytest -m "not integration and not e2e and not llm" -q`: 483/483,
  209 deselected.
- PASS `pytest -m e2e tests/e2e -q`: 61/61, 11 deselected.
- PASS `git diff --check`.
- PASS `scripts/check_release_version.py --base-ref origin/main`: `2.0.8`.
- PASS `npm run lint:js`; PASS `node --test tests/frontend/*.test.mjs`: 65/65.
- PASS `npm run build:web`; committed dist соответствует release `2.0.8`.
- Одноразовый контейнер удалён. Реальные письма, production-данные и внешние LLM
  не использовались.
