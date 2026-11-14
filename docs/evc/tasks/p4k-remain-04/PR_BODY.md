# REMAIN_04: ожидание, briefing и профиль

## Результат

Участник без назначения больше не попадает из ожидания в legacy chat: действие
повторно получает server journey и защищено owner/epoch. Briefing участника читает
подтверждённую revision его активного assignment binding, тогда как admin readiness
сохраняет latest confirmed для новых назначений. Для UserContext обязательны только
ФИО; отсутствие должности или email не блокирует профиль. Исторические snapshots и
опубликованные предметные источники не меняются.

Локальная задача: `docs/evc/tasks/p4k-remain-04/TASK.md`.
Полная передача: `docs/evc/tasks/p4k-remain-04/STATE.md`.
Матрица и receipts: `docs/evc/tasks/p4k-remain-04/CHECKS.md`.

## Проверки

- backend: 1092 PASS;
- HTTP: 153 PASS;
- frontend: 275 PASS;
- controlled PostgreSQL/HTTP exact scope: 3 PASS;
- browser REMAIN_04: 2 PASS; admin/superadmin/W02 regression: 3 PASS;
- lint, build, reproducible dist и `git diff --check`: PASS;
- release preflight: PATCH `2.1.4`, fresh `origin/main`, release gate PASS.

Первый полный локальный integration run сохранил факт `399 PASS, 2 skipped, 5 FAIL`:
пять отказов относились к старому component seed без назначения. Product guard не
ослаблялся; все пять сценариев после ограниченной test-only fixture получили PASS в
адресных повторах. Новый полный зелёный локальный run не заявляется. Обязательные
GitHub `frontend`, `pytest`, `full-verification` должны пройти на точном PR head.

Первый Ready full run на head `1d024890` выявил один FAIL в старом runtime browser
launcher: отключение component plan fixture одновременно отключало отдельную legacy
acquaintance boundary, и проверка настоящего LIMITED start gate не доходила до своей
области. Boundary разделены: plan/start gate в этом сценарии остаётся настоящим.
Локально guard unit — 29 PASS, точный test — 1 PASS, весь runtime shard 1/4 —
9 PASS. Первый FAIL сохранён; новый полный CI требуется на текущем head.

Второй full run подтвердил integration и все runtime shards, но fast lane выявил
9 одинаковых setup FAIL старых owned stands: общий legacy seed guard допускал только
test gateway 1, тогда как эти stands используют gateway 0 с отключённым provider.
Guard допускает 0/1, сохраняя обязательные isolated DB, exact owner marker и
disabled provider. Локально guard unit — 29 PASS, все шесть affected browser-файлов
— 10 PASS. Второй FAIL также сохранён; нужен третий полный CI текущего head.

## Риски и границы

Test-only legacy fixture сохраняет старые component-регрессии и не является новым
runtime fallback или доказательством современного assignment. Native zoom,
физический телефон и человеческая визуальная приёмка TEST локально не выполнялись.
Реальные LLM-вызовы и письма отсутствуют. Схема и миграции не меняются.

## Откат и деплой

Откат — revert squash-коммита; сохранённые профили, source bindings и старые Cycle
не переписываются. После успешного review и обязательного CI используется только
штатный squash merge в `main`; он запускает `deploy-test`. Ручная загрузка файлов,
pilot/Prod и публикация предметных артефактов не входят в этот PR.
