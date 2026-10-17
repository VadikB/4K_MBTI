# UX-REP01 — результат участника и PDF

## Результат

Участник открывает конкретную сохранённую редакцию M8 Report, видит понятные
исходы, ограничения, покрытия, разрешённые основания и рекомендации и скачивает
PDF того же `report_id`. Технические идентификаторы и несуществующие агрегаты в
основном представлении не показываются.

## Область

- Включено: participant UI C-67, четыре исхода M8, группировка по Competency,
  основания, рекомендации, partial-result, PDF exact revision и ошибка скачивания.
- Не входит: пересчёт M6, новая шкала/Skill Level/Competency Score, радар, P4K-34,
  групповые отчёты, сравнение Cycle, новые права, схема БД и регенерация.

## Источники и решения

- Запрос: `UX-REP01_Participant_Result_Report_2026-10-16.txt`, редакция 1.0,
  владелец Дмитрий, Product Lead.
- Применены: Change 01 И-5/И-6, M8 v1.2 §§1–3, 5–7, 9, ADR-002 C-67,
  `m8-results-report-contract.md`, `m8-partial-result-contract.md`, задачи 10.6,
  10.12, 10.14 и 11.2; runtime package `m8-basic-report/1.3.0` не изменяется.
- База реализации: `main` / `3fe6809f5db5405a1bdbf826af7d54f12d48bc24`.
- PM-06 владеет сохранёнными Results, PM-07 представляет owner-scoped C-67.
- Стоп-условия: все восемь — нет. Публичный API, схема, права, предметные правила,
  опубликованные snapshots и граница развёртывания не меняются.
- Пробел: полная матрица реальных браузеров и экспертная визуальная приёмка остаются
  человеческой приёмкой; локально проверяются Chromium desktop/mobile и CI.

## План и состояние

- Завершено: разведка; participant UI; version-bound PDF renderer; unit/frontend
  regression; сборка; визуальная проверка восьми страниц synthetic PDF.
- Активный шаг: финальная самопроверка и передача в PR.
- Следующий шаг: commit/push, PR и обязательный CI.
- Ветка: `codex/ux-rep01-participant-report`.

## Критерии приёмки

- [ ] Четыре исхода, `0` и отсутствие Score различаются без синтеза Level/агрегатов.
- [ ] Навыки доступны в четырёх навигационных группах; mobile не требует горизонтального скролла.
- [ ] Разрешённые основания не показывают IA/Turn/Fragment IDs.
- [ ] Partial-result и пять покрытий не смешиваются и объясняют ограничения.
- [ ] Исторический `report_id` сохраняется при reload; экран и PDF используют его же.
- [ ] Ошибка PDF не скрывает экранный Report и допускает повтор.
- [ ] Старые C-67/PDF не перезаписываются; GET не запускает вычисление.

## План проверки

- `git diff --check`, `npm run lint:js`, `node --test tests/frontend/*.test.mjs`,
  `npm run build:web`.
- Адресные backend/HTTP и Chromium desktop/mobile по существующему M8 fixture.
- GitHub CI `frontend` + `pytest` обязателен до слияния.
- `npm run test:backend`: 427 PASS, 13 предсуществующих M6 FAIL
  (`DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED` / `INPUT_NOT_READY`), REP01 не затронут.
- Chromium G10.7: NOT_RUN — локально отсутствует обязательный изолированный
  `STAND_ADMIN_URL`; sandbox-only запуск отдельно подтвердил невозможность старта браузера.
- Safari/Яндекс/Android/Windows и 200%: NOT_RUN локально, внешняя приёмка.

## Риски и откат

Изменение только presentation-кода и собранного frontend; миграций и новых данных
нет. Откат — revert squash-коммита PR; сохранённые Results/Reports/PDF не изменять.
