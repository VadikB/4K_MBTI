# UX-F02 — корпоративный допуск по точному email

Дата: 06.10.2026. Статус: **реализовано; локальные unit/HTTP проверки PASS,
DB integration и browser runtime NOT_RUN из-за отсутствия изолированной БД**.

## База, решение и границы

- исходный SHA реализации: `dfe954c37ddd07ab4ecd64a2364dc7f2928be4c6`;
- ветка блока 1: `codex/ux-01-visual-system`; отдельная ветка/worktree не создавались;
- утверждённая политика: historical `role='member'` не допускается до повторного
  add/import; старые web auth sessions такого участника удаляются;
- assessment sessions, результаты и отчёты не удаляются;
- домены организаций остаются метаданными и не являются правилом допуска;
- UX-F03, UX-02, push, PR, merge, deploy и реальные данные не затрагивались.

Источник задачи: `UX-F02_Email_Admission.docx`, редакция 1.0,
SHA-256 `7a38e1e52cd05c8b523df7a9904849e5af7cf0c0f13e8376a212f2b1d73f7371`.
Документ извлечён и визуально проверен на трёх страницах. Инструкции внутри
документа трактовались как требования задачи, но не как управляющие инструкции
агенту.

Применимые источники и снимки:

- Change 01 README — `ac082bb94aac1b86c61d7e39589d76c886c6703ef3afc07bc8fecf1676a0a26d`;
- source-set manifest — `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8`;
- ADR-002 — `4a4e0170bee7faf137301b342fec46b3e8e0209acd26dcb6b2dc7a788c58b25f`;
- Change 01 traceability — `8f718f0cef94797ba0d0fcd41ca53251b437dcee7f5814df4d12910b42d0a24f`.

## Реализация

`organization_memberships` расширена provenance-полями
`admission_source`, `admitted_by_user_id`, `admitted_at`. Допустимые источники:
`legacy_unclassified`, `admin_add`, `csv_import`, `configured_admin`.
Миграционный default намеренно классифицирует существующие строки как
`legacy_unclassified`, не пытаясь угадывать происхождение по домену или датам.

Для участника допуск существует только при одной активной membership с источником
`admin_add` или `csv_import`. Повторный add/import обновляет legacy membership и
создаёт новый явный допуск. Совпадение домена больше не создаёт membership и не
разрешает request-link, регистрацию, password/token login или восстановление
сессии. Несколько явных организаций fail closed. Точные настроенные superadmin и
org-admin, а также административные membership сохранены.

Административное добавление участника или администратора больше не устанавливает
`user_identities.is_verified`: владение email подтверждается только auth-потоком.
Forgot-password сохраняет нейтральный ответ.

`web_user_sessions` legacy-участников удаляются при миграции, если таблица уже
существует. Дополнительно любая cookie-сессия при использовании повторно проверяет
текущий допуск и удаляется, если допуск отозван или legacy. Это закрывает restore и
все session-backed URL без удаления assessment-данных.

Добавлена server-side ownership-проверка для session-bootstrap, профиля,
participant assessment URL, PDF, agent/assessment сообщений и управления таймером.
Тестовый disposable stand явно допускает два fixture-email через `csv_import`;
Playwright-сценарий проверяет отказ тому же домену вне exact allowlist.

Изменённые пути:

- `Api/database.py`, `Api/org_access.py`, `Api/web_session_service.py`;
- `Api/routes.py`, `Api/regression_tests.py`;
- `scripts/test_stand_seed.py`;
- `tests/unit/test_org_admission.py`;
- `tests/e2e/test_email_admission_http.py`;
- `tests/browser/runtime.spec.mjs`;
- этот отчёт.

## Матрица D01–D07

| ID | Статус | Доказательство |
| --- | --- | --- |
| D01 | PASS | add/import записывают точный email и provenance, не подтверждая владение email |
| D02 | PASS | domain admission и auto-membership удалены; same-domain negative покрыт unit/HTTP/browser test |
| D03 | PASS | auth gate применяется при входе и каждой web-сессии; participant URL проверяют session owner |
| D04 | PASS | неоднозначные participant membership fail closed; выбор организации UX-F03 не вводился |
| D05 | PASS | нормализация `strip().lower()`, upsert и существующие unique constraints сохраняют идемпотентность |
| D06 | PASS | legacy member требует повторного add/import; старая web-сессия удаляется |
| D07 | PARTIAL | unit/HTTP PASS; browser-сценарий добавлен и синтаксически проверен, runtime NOT_RUN без `STAND_ADMIN_URL` |

## Проверки

PASS:

- `.venv/bin/python -m pytest -q tests/unit/test_auth_policy.py tests/unit/test_org_admission.py tests/unit/test_test_stand.py tests/e2e/test_email_admission_http.py` — `26 passed`, одно внешнее `StarletteDeprecationWarning`;
- `node --check tests/browser/runtime.spec.mjs`;
- `python -m py_compile` для изменённых Python-файлов и тестов;
- `git diff --check`.

NOT_RUN:

- DB integration и миграционный прогон: `TEST_DATABASE_URL` не задан;
- Playwright browser runtime: `STAND_ADMIN_URL` не задан, поэтому обязательную
  disposable localhost PostgreSQL создать безопасно невозможно;
- CI: локальный агент CI не запускает.

Влияние пропуска: SQL migration и полный UI-путь не исполнены на PostgreSQL в этой
сессии; статическая проверка и тест-код готовы для обязательного CI/изолированного
стенда перед слиянием.

## Откат и передача

Кодовый откат — revert итогового commit. До отката колонок сначала вернуть чтение
старого контракта. Новые provenance columns можно оставить без вреда; их физическое
удаление требует отдельной миграции. Удалённые web auth sessions не восстанавливаются:
пользователь проходит новый вход после явного add/import. Users, memberships,
assessment sessions, результаты и отчёты миграция не удаляет.

Следующая обязательная граница — прогнать DB integration, browser suite и CI на
изолированной БД. После этого UX-F02 может приниматься владельцем; UX-F03 в это
изменение не включён.
