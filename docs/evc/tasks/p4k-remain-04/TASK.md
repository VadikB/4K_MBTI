# REMAIN_04 v1.6 — ожидание, briefing и профиль

Основание: команда владельца «Делаем REMAIN_04», 14.11.2026; карточка 1.6 и общий порядок 1.0 из Downloads прочитаны как постановка, не самостоятельные полномочия публикации.

Результат: F24/F25/F26, PM-02 LU-02.4/02.6/02.7/02.8. Participant briefing использует точный source binding; административная готовность новых назначений использует latest confirmed. Только ФИО обязательны; ожидание без legacy/start, с безопасной проверкой readiness. STOP: readback immutable профиля, без AS/Report/генерации.

## Прочитанные источники и границы

README.md, CONTRIBUTING.md, AGENTS.md; docs/evc/{agent-workflow,verification-matrix,artifact-recipe,task-template,review-checklist,decision-register}.md; Product Architecture 1.0 context.md и registry.md; Change 01 WORKING И-2/3; task manifest 2026-10-01; ADR-002 C-23/24; change01-traceability T01; M1 v1.4 README (FROZEN/CURRENT=NO); M4 v1.0 §§M4.1–6 (m4_context_source.md); M3 role contract через опубликованные role refs. ADR-003 и REMAIN_01/02 TASK/STATE — exact assignment и модель доступа. Решение 02 v1.4 сохранено карточкой 04: organizer/purpose/usage, явный confirm, без C04/contact/picker; системный доступ из recipient_access_projection. F05 не переделывается.

Не найдено: отдельный новый runtime policy не нужен; источники и опубликованные пакеты не меняются, CURRENT не присваивается. Полный M3/M1 аудит не выполняется. ART-02/03 legacy долг не расширяется. Новых норм и нормализующих LLM нет.

docs/architecture/product-4k/1.0/updates/2026-10-01/README.md SHA-256 ac082bb94aac1b86c61d7e39589d76c886c6703ef3afc07bc8fecf1676a0a26d
assessment_definitions/contexts/competencies_4k/1.1/m4_context_source.md SHA-256 9af86011c1ea1bef12058700bdd345c5cee335bbc6ec4d392fcfc4f3e5709fd1
docs/adr/002-cycle-as-dialogue-contracts.md SHA-256 4a4e0170bee7faf137301b342fec46b3e8e0209acd26dcb6b2dc7a788c58b25f

## План

1. Разведка actual base и точечные регрессии F24/F25/F26.
2. Исправление выбора источника, optional guards и waiting; producer/consumer/test совместно.
3. Controlled HTTP/PG/VM/browser до профиля; локальный минимум; ревью и bundle.

Стоп-условия workflow: все восемь — нет: не вводятся предметная норма/кардинальность, миграция/удаление, новый артефакт, новый ACL/деплой; additive optional argument совместим, отрицательные состояния сохраняются; откат revert только своих коммитов, старые snapshots остаются. Обнаруженный конфликт блокирует только зависимый шаг.

Проверки: git diff --check; npm run lint:js; node --test tests/frontend/*.test.mjs; npm run build:web; npm run test:backend; адресные HTTP и isolated PostgreSQL; browser на той же synthetic fixture (1440/1366/768/390/320, text200/Tab, login/direct/reload, late response). CI frontend/pytest/full-verification только на будущем PR архитектора. Native zoom/физический телефон отдельно.

Схема/миграции/конфиг/артефакты: без изменений. API аргумент optional; исторический legacy поддерживается только при отсутствии managed schema, новые managed участники без назначения ждут. Privacy и точные checksums проверяются действующими M4 контрактами. Откат: revert коммитов этой задачи, без изменения данных.

branch_push=false; pr=false; merge=false; deploy=false; version_bump=false; artifact_publish=false. Передача локальным bundle/веткой, публикация и продуктовый номер — архитектор.

## Точные выбранные исходники

- ProductArchitecture.Change01 1.0/01 WORKING: docs/architecture/product-4k/1.0/updates/2026-10-01/source.pdf; SHA-256 dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081 (байты сверены).
- M1 1.4 FROZEN: docs/architecture/product-4k/m1/v1.4/source.docx; SHA-256 5fa5ab5735dfe57fac6ef3c93aca50d149fbd7abd365edf80d362c10e2d7a975 (байты сверены).
- M3.RoleProfile 1.0 FROZEN: docs/methodology/source-sets/2026-10-01/originals/M3.RoleProfile-v1.0.docx; SHA-256 a3c085e4182fe8bc5a82204a8d4679a09b85650ea79e2df24fb1ed8ab6604e06 (байты сверены).
- M3.BaseRoles 1.0 FROZEN: docs/methodology/source-sets/2026-10-01/originals/M3.BaseRoles-v1.0.docx; SHA-256 ab04e175bb1bf4ad55c320554068041baf3cb4c1cc2316c16966451b91c465bc (байты сверены).
- M4.Context 1.0 FROZEN: docs/methodology/source-sets/2026-10-01/originals/M4.Context-v1.0.docx; SHA-256 07875e93ae422668b1b30cd60bc1c6140cae91db12b0b80ba4abca441cfe9291 (байты сверены).
