# UX-ADM19-02 — собственная оценка администратора заказчика

## Результат и границы

Единый аккаунт org-admin переключается между «Управление» и «Моя оценка» без смены `user_id`, роли или пароля. Личный раздел следует серверному `journey-state`; административная capability хранится отдельно от активной области. Суперадминские полномочия, схема БД, trusted assignment, Cycle/AS и M8 не меняются.

Реализованы: вход в личный маршрут из кабинета организации, постоянный возврат к управлению на личных экранах, восстановление выбранной области после reload/deep-link, сохранение выбранного блока и текстового черновика управления при переключении без перезагрузки страницы, ожидание назначения без перехода в legacy профиль. Прямое и массовое API предварительной подготовки исключают самого назначающего. После готовности отчёта личный маршрут использует сохранённый M8-результат и радар.

## Источники и решения

- `START_CODEX_Admin_and_Bugfixes_2026-10-19_v2.txt`, SHA-256 `cbebc745f171587ca20d6aa5eaf16c8bb2ca5a612b8207db020376c291055f70`.
- `P4K_Admin_and_Bugfixes_v2/COMMON.txt`, редакция 2.0, SHA-256 `363f807c543f57b1a3138233781b643d04b3ff2722c78f515fb77c0a1343d5e7`.
- `P4K_Admin_and_Bugfixes_v2/tasks/UX-ADM19-02_Admin_Own_Assessment.txt`, редакция 1.0, SHA-256 `31ada30ac4278c2aaf017cd7062662211ac0034ff053974f0df0d4dad26d65d3`.
- Change 01 WORKING, ADR-002, task SourceSet 2026-10-01; runtime publication методологии не меняется.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`, `docs/architecture/product-4k/1.0/context.md`, `docs/architecture/product-4k/registry.md`, `docs/architecture/product-4k/1.0/updates/2026-10-01/README.md`, `docs/methodology/source-sets/2026-10-01/manifest.json`, `docs/adr/002-cycle-as-dialogue-contracts.md`, применимые код и тесты. Противоречащих обязательных источников не обнаружено.
- Branch: `codex/ux-adm19-02`; base: `main` `72d8f97606ca3d091455e45c3ff41b0ab2c139fb`.

## Карта текущих вызовов и решение

`openAdminAssessmentDashboard` раньше принудительно сбрасывал `isAdmin` и всегда открывал legacy `reopen-profile`. Теперь он запрашивает защищённый `/{user_id}/journey-state`, применяет принадлежащие серверу идентификаторы Cycle/AS и открывает штатный этап. `canAdmin` сохраняет capability, `activeArea` — выбранную область. Авторизация API остаётся серверной.

`Api/org_access.py` уже признаёт административную membership явной связью с организацией и не требует повторного добавления email. У org-admin без персонального приглашения `Api/acquaintance.py` теперь возвращает `waiting_for_assignment`, не заимствует общий подтверждённый questionnaire. Существующий `prepare-assessment` требует superadmin; в этом изменении дополнительно запрещено назначение себе по прямому API и исключён actor из массовой операции. `Api/routes.py` journey и report endpoints сохраняют проверку собственного `user_id`/владения. Новых прав или источников предметных значений нет.

Стоп-условия рабочего цикла: нет. Публичный API, схема и владение данными не меняются; новое значение readiness находится внутри существующей словарной проекции. Миграция не требуется. Откат определён ниже.

## Изменённые файлы

- `Api/acquaintance.py`, `Api/routes.py` — персональное ожидание назначения и запрет self-assignment.
- `web/js/state.js`, `web/js/session.js`, `web/js/main.js`, `web/js/router.js`, `web/js/wiring.js`, `web/js/screens/admin/dashboard.js`, `web/js/screens/admin/organizations.js`, `web/js/dom.js` — переключение, серверное восстановление раздела и черновика.
- `web/index.html`, `web/styles/screens/dashboard.css`, `web/dist/*` — управление в личной области и актуальная сборка.
- `tests/browser/auth-r03.spec.mjs`, `tests/e2e/test_adm19_02_self_assignment_http.py`, `tests/integration/test_w02_acquaintance_db.py` — регрессии.

## Проверки и откат

- `npm run lint:js` → PASS.
- `node --test tests/frontend/*.test.mjs` → PASS, 62.
- `npm run build:web` → PASS.
- `.venv/bin/python -m pytest -m "not integration and not e2e and not llm"` → PASS, 458.
- `.venv/bin/python -m pytest -m e2e tests/e2e/test_adm19_02_self_assignment_http.py` → PASS, 2.
- `TEST_DATABASE_URL=…adm19_02_test .venv/bin/python -m pytest --run-integration -m integration tests/integration/test_w02_acquaintance_db.py` → PASS, 1; изолированная временная PostgreSQL остановлена после прогона.
- `npx playwright test tests/browser/auth-r03.spec.mjs` → PASS, 33, включая два сквозных ADM19-02.
- `git diff --check` → PASS.

Непроверенное: CI `frontend`/`pytest`, deploy-test и визуальная проверка опубликованного test до PR/слияния не выполнялись. Синтетический browser тест подтверждает маршрут и сохранённый M8 fixture; реальный org-admin на опубликованном test требует отдельной приёмки после деплоя.

Риски: конфиг и схема без изменений; серверные права не зависят от `activeArea`. Текстовый черновик управления хранится только в памяти вкладки и сохраняется при переключении без reload. File input браузер не разрешает восстанавливать программно. Откат — revert PR маршрутизации и readiness; связи, назначения, отчёты и snapshots не удалять.

Следующий шаг: PR и обязательный CI; после review владельца — слияние и deploy-test, затем проверка опубликованного личного пути org-admin. Открытых предметных решений нет.
