# UX-E02 — завершение оценки и ожидание результата

## Результат

Cycle-путь после подтверждённого закрытия сбора показывает единый экран E02:
подтверждение, ожидание, истечение времени, готовность полного/ограниченного
Report, техническую ошибку и потерю связи. Готовый Report открывается только по
явному действию участника. Внутренние этапы orchestration и условные проценты в
Cycle-пути не показываются.

## Границы

- Не меняются критерии закрытия Cycle, admission, агрегация, содержание Report и recovery-права.
- Legacy session analysis сохраняет существующий механизм; новый E02 применяется к Cycle runtime.
- `scenario_ended`, закрытая отдельная AS и `between_situations` остаются состояниями E01.
- Новый persistence-контур и таблицы UI-статусов не вводятся.

## Источники и решения

- Постановка владельца: `UX-E02_Completion_and_Result_Waiting_2026-10-16.txt`, редакция 1.0.
- `AGENTS.md`, `README.md`, `CONTRIBUTING.md`.
- `docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`, `review-checklist.md`.
- `docs/architecture/product-4k/1.0/context.md`, `registry.md`, Change 01 и task SourceSet.
- `docs/adr/002-cycle-as-dialogue-contracts.md`, `docs/evc/change01-traceability.md`.
- Фактические контракты: `Api/m7_completion.py`, `Api/m10_orchestration.py`,
  `Api/m8_results.py`, `Api/routes.py`, `Api/user_journey.py`.

Принятое решение владельца из постановки: рассчитанный Cycle не равен готовому
Report; failure имеет приоритет над ранее созданным limited Report. Статус
строится по одному owner-scoped Cycle и его assessee Report.

Пробел: нормативный CURRENT не присваивается; draft QA-контракты не объявляются
методологическим допуском. Это не блокирует согласованную проекцию существующих
runtime-фактов.

## Изменения

- `Api/routes.py`, `Api/user_journey.py`: journey различает Results ready,
  Report ready и processing failure.
- `Api/m7_completion.py`: подтверждённый прогресс по позициям сохранённого route.
- `web/index.html`, `web/js/screens/processing.js`, `web/styles/screens/processing.css`:
  состояния E02, polling, offline/access handling, явные действия и адаптивность.
- `web/js/main.js`: разрешённая прямая ссылка на готовый owner Report.
- Тесты frontend/unit/browser/integration обновлены в границе изменения.

## Проверки

- `git diff --check` — PASS.
- `npm run lint:js` — PASS.
- `node --test tests/frontend/*.test.mjs` — PASS, 34/34.
- `python -m pytest -q tests/unit/test_user_journey.py tests/e2e/test_m10_processing_recovery_http.py tests/e2e/test_m5_runtime_http.py` — PASS, 17/17.
- `npm run build:web` — PASS.
- `npx playwright test tests/browser/auth-r03.spec.mjs --grep "processing deep link|Cycle failure|E02 shows ready"` — PASS, 3/3 после разрешения loopback; первичный sandbox-запуск — EPERM до выполнения тестов.
- `npm run test:backend` — 423 PASS, 13 FAIL в существующих M6 provider/admission fixtures (`DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED` / `INPUT_NOT_READY`); затронутые UX-E02 unit/e2e — PASS, а изолированный обязательный backend проверяет CI.
- Полный backend/CI и post-merge deploy-test фиксируются перед слиянием и после него.

## Непроверенное

- Реальные iOS Safari, Android Chrome/Яндекс, Windows Chrome/Яндекс,
  macOS Safari/Яндекс — NOT_RUN; локальная автоматизация использует Chromium.
- Реальные Cases/provider и содержательная корректность результата — NOT_RUN и не входят в UI-задачу.
- Письма людям и production/test персональные данные не использовались.

## Риски и откат

- Схема БД и публичные mutating API не меняются.
- Read model выполняет два дополнительных owner-scoped чтения для текущего Cycle.
- Откат: revert squash-коммита UX-E02; история Cycle/Results/Report не изменяется.
- Пользовательский незакоммиченный `docs/evc/timer-and-configuration-storage.md` не включать в commit.

## Состояние передачи

- Ветка: `codex/ux-e02-completion-waiting`.
- PR/SHA/CI: заполняются после локальных обязательных проверок.
- Открытые блокеры: нет.
