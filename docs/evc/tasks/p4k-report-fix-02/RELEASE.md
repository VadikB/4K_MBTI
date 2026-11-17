# Выпуск P4K-REPORT-FIX-02 — 2.1.29

17.11.2026. Человеческая приёмка: владелец после просмотра результата сообщил
«принято, заливай на main». Разрешены push, один PR, следующий PATCH, Ready,
обязательный CI, squash merge и штатный автоматический deploy TEST
([CONTRIBUTING-MERGE-AUTH-01](../../../../CONTRIBUTING.md)).
`branch_push/pr/merge/version_bump=true`, `deploy=test`, `artifact_publish=false`.

Свежая база `71a9c535cee4aea094d2b49c2b73f39e22f99bbe` / 2.1.28;
кандидат 2.1.29. Принятый локальный результат — `03c74be` (код `9422308`).
В release изменены штатные поля версии/сборка и номер версии synthetic preview:
он читает APP_RELEASE текущего checkout, вместо фиксированной 2.1.28.
Проверка ответа preview включена в существующий сценарий P01/P02.

Локальные проверки кандидата:

- `npm run ready:prepare -- --candidate 2.1.29`: PASS, fresh base/release gate/build.
- `node --test tests/frontend/*.test.mjs`: 404 PASS.
- `npm run lint:js`, `git diff --check`: PASS.
- Три `report-fix02-preview.spec.mjs`: 3 PASS, 8.8 sec; workers=1, retries=0,
  timeout=30 sec, global-timeout=10 min. Проверены новый номер, реальные PDF,
  P01–P06, разные размеры, ошибки/повтор и late response. Свой сервер закрыт.
- Полный локальный минимум принятого кода: backend1224/HTTP202/frontend404/
  browser38 — [CHECKS](CHECKS.md). Релиз не меняет backend/PDF/UI-логику.

Логи release-* и хеши текущей сборки — в evidence. Исходные четыре снимка,
два PDF и identity сохранены как исторический снимок локальной приёмки.
Перед Ready локальная подготовка завершена; обязательный CI точного head,
сверка свежего main, PR, merge SHA и TEST deploy проверяются по GitHub.
Локальные результаты не заменяют обязательные CI `frontend`, `pytest`,
`full-verification` (integration и все browser lanes).

TEST: https://test.4k-assistant.ru . Проверка UI — инструкция [HOW_TO_VIEW](HOW_TO_VIEW.md);
synthetic меню существует только локально, в runtime TEST оно не включается.
Откат — отдельный revert PR приложения и штатный TEST deploy; миграций нет.

PR: [#245](https://github.com/VadikB/4K_MBTI/pull/245). Первый CI c8adcc6:
backend/integration/runtime 4/4 PASS, frontend FAIL на npm audit, fast browser
FAIL на трёх прежних ожиданиях. По отдельному прямому разрешению владельца
выполнен ограниченный [dev-dependency fix](DEPS.md), проверки аудита сохранены;
browser-ожидания обновлены к принятому FIX-02. Перед merge — новый обязательный CI.
