# UX-ADM27 — рабочая админка по принятому прототипу

## Результат и область

Обычный org-admin управляет своей закреплённой организацией в трёх разделах,
сохраняет черновики, приглашает только незарегистрированных людей и явно назначает
выбранную оценку сотрудникам, включая себя. Четыре карточки UX-ADM27 по прямому
решению владельца от 27.10.2026 выполняются одним результатом, одной веткой и одним PR.
Вход, суперадминский дизайн, participant UI, методология, Cycle/AS и LLM не меняются.

## Источники и решения

- База: `origin/main` `4a4701ddd91d01a89031d9a824ffaf937aa8f34e`, версия `2.0.29`.
- Пакет владельца `P4K_Admin_Only_Tasks_2026-10-27.zip`: `START_CODEX.txt`,
  `COMMON.txt`, UX-ADM27-01..04, `CHECKS_AND_HANDOFF.txt`, прототип v3 от 19.10.2026.
- Прочитаны `README.md`, `CONTRIBUTING.md`, обязательные EVC workflow/matrix/recipe,
  архитектурные context/Registry, Change 01, SourceSet manifest, ADR-002 и traceability,
  UX-ADM19-02, UX-FIX20-04, применимые API/frontend/тесты.
- Последнее решение владельца: org-admin может назначить оценку себе в своей
  организации. Registered-пользователь не получает регистрационное письмо.
- Контур выпуска уточнён владельцем: после PR/CI/merge стенд
  `vadim_bogachev@178.236.26.203`, не прежний `test`; pilot/production исключены.
- Стоп-условий нет: узкая expand-схема совместима, опубликованные артефакты и
  snapshots не изменяются. Прототип — визуальный источник, не runtime-пакет.

## Карта требования → контракт → реализация → проверка

| Требование | Контракт/данные | Реализация | Проверка |
| --- | --- | --- | --- |
| Три раздела без верхней legacy-формы | ADMIN UI, scoped organization | `organizations.js`, ADMIN CSS | frontend/browser/visual |
| Draft не требует полного confirm-набора | questionnaire revision draft | существующий `save_preview`, HTML validation | unit/integration/browser |
| Registered без письма | authoritative password credential | invitation API и member projection | HTTP + fake mail |
| Явное назначение, включая себя | `organization_assessment_assignments` | scoped batch endpoint, acquaintance reader | HTTP/integration/browser |
| Без автозапуска | assignment отдельно от queue/Cycle | endpoint не вызывает mail/queue/LLM | HTTP assertions |

## Данные, совместимость и откат

Expand-таблица хранит organization, recipient, assignment_ref, actor, подтверждённую
questionnaire revision, статус, operation/fingerprint и время. Уникальность защищает
повтор и конкуренцию. Legacy personal-registration assignment продолжает читаться
через совместимый `UNION`; массового backfill нет. Откат UI/API — revert PR, новые
строки сохраняются для совместимого чтения; разрушительный `DROP` не применяется.

## План и проверки

- Реализация 01–04 последовательно в `codex/ux-adm27-admin`.
- Локально: `git diff --check`, JS lint/frontend/build, backend unit/HTTP,
  PostgreSQL integration на БД с `test`/`pytest` в имени, Playwright и visual 1440/1280/390/320.
- Затем один PATCH, PR, обязательные CI, review, merge и развёртывание свежего `main`
  на указанном стенде. Визуальная приёмка владельцем остаётся ожидаемой.
