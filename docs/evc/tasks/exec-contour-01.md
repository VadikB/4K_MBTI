# EXEC-CONTOUR-01 Профиль прохождения до доступного отчёта

## Результат

Существующий синтетический AC18 сохраняет самостоятельный запуск, а новый составной
режим продолжает тот же owned stand, Cycle и стартовую AS штатными действиями участника
до доступного и явно открытого Report. Итог подтверждает отдельный offline validator;
milestone первой AS не объявляет итоговый PASS.

## Область

- Включено: profile/coordinator, stage receipts, offline validation, бесплатный
  controlled-gateway прогон, матрица H1–H12, команда и оценка paid provider run.
- Не входит: реализация EXEC-FIX-01/02/03, новые предметные нормы, изменение
  опубликованных артефактов, provider run без отдельного прямого допуска.

## Контекст

- Основание: прямое поручение владельца от 10.11.2026 и пакет
  `P4K_EXEC_CONTOUR_01_2026-11-09.zip`, редакция 2.1.
- База: `origin/main@0c2412012209cfa92adafa803183852a2c231c5e`, включающая
  EXEC-FIX-01 `60234f2a` и EXEC-FIX-02/03 `0c241201`.
- Точки входа: `scripts/assessment_first_case.py`, `scripts/test_stand.py`,
  `tests/browser/path29-participant.spec.mjs`, `tests/browser/runtime.spec.mjs`,
  `tests/browser/fixtures/preparation-receipt.mjs`.
- Архитектурный адрес: PM-04 исполняет Cycle/Session/AS/Dialogue; PM-05 формирует
  факты/IA; PM-06 рассчитывает Results; PM-07 представляет Report. UI не подменяет
  предметную логику, harness не исправляет продукт ради PASS.
- Прослеживаемость: M5 v1.1 §§5.3.4, 5.5–5.6 → ADR-002 C-45/C-54/C-46/C-56/C-67
  → M7 clarification/completion contracts → runner/receipts/validators → H1–H12.

## Источники и решения

- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, EVC workflow/matrix/
  artifact recipe, Product Architecture context/Registry, Change 01 README/source,
  SourceSet manifest, M1 v1.4 §§1.6–1.10 (FROZEN, CURRENT=NO), M5 v1.1
  (FROZEN, CURRENT=NO), M6 v1.8 §§6.6.6–6.6.9, M7 v1.3 §§3–8, M8 v1.2
  Results/Report, ADR-002, clarification/completion contracts, поздние R1/pilot
  решения и профиль `assessment-first-case/1.1`.
- Архивный glossary WORKING используется адресно; статус runtime не переключает.
- Принято: standalone AC18 и `first-case-receipt.json` сохраняются; composite
  продолжает lifecycle внутри того же browser test, а не вторым spec/process.
- Стоп-условия: предметная неоднозначность — нет; миграция/публичный API — нет;
  секреты/production data — не используются; paid provider — отдельный стоп до
  прямого допуска; обязательный CI/human review остаются внешними gate.
- Требуется решение владельца: только отдельный допуск на подготовленную paid-команду.

## План и состояние

- Завершено: source route, checkpoint, сверка EXEC-FIX-01/02/03 в `origin/main`.
- Активный шаг: coordinator/profile/validator и бесплатные регрессии.
- Следующий шаг: локальная матрица, review, release candidate, отдельный PR/CI.
- Ветка: `codex/exec-contour-01-assessment`.

## Действия выпуска

- `branch_push=true`, `pr=true`, `merge=true`, `deploy=true` в пределах прямого
  поручения владельца; merge только после обязательных CI и human review.
- `version_bump=true` только штатной `npm run ready:prepare` перед Ready for review.
- `artifact_publish=false`; `paid_llm=false` до отдельного прямого допуска.

## Ограничения и риски

- Один coordinator владеет DB/server/browser/evidence/cleanup.
- Composite запрещает смену `run_id`, DB, Cycle и стартовой AS между этапами.
- Controlled gateway доказывает технический путь, не качество семантики.
- Provider trace может не содержать usage предыдущего malformed JSON retry;
  неполная сумма не выдаётся за полную.
- Ошибка terminal export/неизвестное состояние оставляет cleanup deferred.

## Критерии приёмки

- [ ] H1–H12 отражены в отдельной матрице с PASS/FAIL/NOT_RUN и evidence.
- [ ] Standalone AC18 сохраняет selector, 0 ответов, итог и cleanup.
- [ ] Composite использует одну owned DB, один Cycle и стартовую AS AC18.
- [ ] First-case milestone и terminal composite verdict разделены.
- [ ] Report готов, owner-authorized и явно открыт через UI.
- [ ] Offline validator fail-closed для чужого run, неполного этапа и cleanup error.
- [ ] Новое предметное содержание не встроено в код.

## План проверки

- `git diff --check`; Python compile/unit; JS unit; controlled browser на изолированной
  БД; применимые EXEC-FIX регрессии; `npm run test:backend`; CI `frontend`, `pytest`,
  `full-verification` на точном PR head.
- Paid provider: NOT_RUN до отдельного прямого допуска.

## Откат

Удалить новый composite/profile/validator и вернуть runner к единственному режиму
first-case. Продуктовые данные/схема не меняются; старые receipts остаются читаемыми.
