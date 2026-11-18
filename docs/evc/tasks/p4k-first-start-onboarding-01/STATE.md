# STATE — P4K-FIRST-START-ONBOARDING-01

- База `b5cd92b7d492f31efe3b01ee22699bb34f55248d` (`origin/main`, 2.1.32).
- Ветка `codex/p4k-first-start-onboarding-01`, отдельная локальная копия.
- Сбой воспроизведён в Chromium на исходной сборке с регрессионной версией
  теста. AC-1: 1 оборванный PUT, 0 POST, ошибка подтверждения. Три контроля
  AC-2 на базе прошли.
- В `advance()` добавлена проверка сохранённого статуса и финального шага.
  Сборка пересоздана, а существующий REMAIN05 расширен проверками AC-1–AC-3.
  Перед фиксацией на рабочей сборке прошли все 6 сценариев Chromium.
- Подтверждение точного коммита, команды, журналы и ZIP с bundle передаются
  в локальном `HANDOFF.md`. При передаче сравнить base с текущим `origin/main`.
- Диагностика живого прогона QA‑05 ведётся отдельно. Условия выпуска и
  откат заданы в [TASK.md](TASK.md).

## Выпуск в main и TEST

Поручение пользователя от 18.11.2026: «Слей проверенное исправление первого
старта `2040f061` в `main`» через PR после ревью и зелёного CI с проверкой TEST.
Исходник `2040f0613b118c0670cfd8e519b4a29ce77dbfb5` основан на свежем
`b5cd92b7d492f31efe3b01ee22699bb34f55248d`. PATCH 2.1.33 следует за 2.1.32
по `CONTRIBUTING-MERGE-AUTH-01`.

`branch_push=true`, `pr=true`, `version_bump=true`, `merge=true`,
`deploy=true` (штатный deploy TEST после squash merge), `artifact_publish=false`.
Слияние зависит от человеческого ревью, успешных `frontend`, `pytest` и
`full-verification` на актуальной голове PR и повторной сверки базы.
После слияния проверяется deploy для squash commit и версия
на `https://test.4k-assistant.ru/users/version`.
