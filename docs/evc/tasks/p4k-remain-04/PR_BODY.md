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
