# UX-REL01 — получатели и автоматическая выдача результата

## Результат и границы

- Ветка: `codex/ux-rel01-report-access`, база `main@d8f60d9` после REP02.
- Участник остаётся обязательным получателем собственного M8 Report.
- Представители заказчика выбираются явно из действующих администраторов организации;
  выбор замораживается для Cycle и при каждом чтении пересекается с текущими правами.
- Включены настройка, frozen access snapshot, API/PDF/прямая ссылка, минимальная
  навигация в существующем административном списке и отрицательные проверки.
- Не входят почтовая отправка, групповые отчёты, новая ролевая система и очистка legacy.

## Источники и решения

- `UX-REL01_Report_Access_2026-10-17.txt`, редакция 1.0, решение владельца D06.
- Прочитаны `README.md`, `CONTRIBUTING.md`, обязательные EVC документы, Product 4K
  context/Registry, Change 01/manifest, ADR-002, M8 contract и задачи W02/ADM01/E02/
  LK01/REP01/REP02; проверены текущие org scope, questionnaire, Cycle, M8 и legacy routes.
- Старый `recipient_mapping` — информационная категория, не список разрешений.
- Стоп-условия: нет. Совместимое расширение схемы и прав прямо разрешено задачей;
  опубликованные Results/C-67 не меняются, старые Cycle остаются owner-only.

## Трассировка

| Правило | Данные/контракт | Реализация | Проверка |
| --- | --- | --- | --- |
| Участник обязателен | owner membership + assessee C-67 | существующий owner path | HTTP/DB regression |
| Заказчик выбирается явно | immutable access revision | questionnaire confirmation UI/API | unit/frontend/DB |
| Условия Cycle неизменны | frozen Cycle access snapshot | создание M5 Cycle | DB integration |
| Отзыв действует сразу | snapshot ∩ active admin membership | проверка каждого GET/PDF | HTTP negative |
| Старые данные fail-closed | отсутствие snapshot | customer deny, owner unchanged | compatibility regression |
| Один фактический Report | saved assessee C-67 → restricted customer projection | customer API/PDF | equality/absence checks |

## План и состояние

- Завершено: разведка, схема, backend ACL, настройка, административная навигация
  и адресные регрессии.
- Активный шаг: review, commit и PR.
- Далее: обязательный CI и человеческое review перед merge.

## Проверки

- Backend, HTTP и frontend по `docs/evc/verification-matrix.md`.
- PostgreSQL integration только в изолированной БД с `test`/`pytest` в имени.
- Реальные браузеры/устройства и production/test PII не используются; недоступное — NOT_RUN.

Фактически до PR:

- Python/JS syntax и `git diff --check` — PASS.
- `npm run lint:js`, `npm run build:web` — PASS; `web/dist` обновлён.
- `node --test tests/frontend/*.test.mjs` — 44 PASS.
- `npm run test:backend:http` — 57 PASS, 11 deselected.
- адресные HTTP/unit — 8 PASS.
- полный локальный backend — 430 PASS / 13 FAIL в прежнем M6/provider-контуре
  (`INPUT_NOT_READY`, `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`), не связанном с REL01.
- новый PostgreSQL integration — 1 PASS (pure projection), 1 SKIPPED: локальный
  `TEST_DATABASE_URL` не настроен; обязательный CI запускает его на PostgreSQL 16.
- реальные iOS/Android/Windows/macOS и Яндекс Браузер — NOT_RUN.

## Совместимость и откат

- Таблицы аддитивны. Старые questionnaire revisions и Cycle не получают customer ACL
  задним числом. Results/C-67 неизменяемы.
- Откат — revert runtime/UI; access revisions и frozen snapshots оставить как историю,
  без удаления. Owner-доступ продолжает прежний контракт.
