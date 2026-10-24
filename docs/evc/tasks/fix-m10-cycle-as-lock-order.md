# FIX-M10-LOCK — единый порядок блокировок Cycle → AS

## Результат

Worker M10 больше не захватывает Assessment Situation перед Cycle. Это устраняет
воспроизведённый deadlock между обработкой interim/final M10 и одновременным
participant runtime/закрытием Cycle.

## Область

- Включено: claim запросов `_queue_outbox`, `_queue_assessment`,
  `_clarify_interim`; регрессия порядка блокировок; повтор двух упавших browser
  сценариев.
- Не входит: полное закрытие ARCH-A03 (transaction phases вокруг provider,
  heartbeat/fencing lease, crash recovery и вся матрица конкурентной приёмки),
  ARCH-A04/A07 и предметное поведение оценки.

## Контекст, источники и решения

- Основание: пакет `P4K_Case_AS_Cycle_Plan_2026-10-23`, редакция 2.0,
  `06_A03_A04_A07_Dependencies.txt`; подтверждённый владельцем порядок работ.
- База: PR #103, commit `3ef79f1`; воспроизведение GitHub Actions run
  `40033783842`, где browser сценарии зависали на взаимной блокировке
  `m5_cycles` и `m5_assessment_situations`.
- Прочитано: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
  `docs/evc/review-checklist.md`, `Api/m10_orchestration.py`,
  `Api/m5_scenario_runtime.py`, `Api/m7_clarification.py`, относящиеся integration
  и browser тесты. Архитектурные источники и Change 01 повторно использованы из
  разведки серии A/B; предметная норма не меняется.
- Правило: существующий канонический порядок продуктовой мутации — сначала Cycle,
  затем AS. M10 claim должен соблюдать тот же порядок.
- Не найдено/противоречит: пробелов для данного ограниченного исправления нет.
  Полные критерии ARCH-A03 остаются открыты и этим изменением не закрываются.
- Стоп-условия: все «нет» — публичный контракт, схема, данные, PM/LU, права,
  артефактный контур и смысл оценки не меняются; откат — revert коммита.
- Решение владельца: продолжать по списку задач и самостоятельно устранять
  локальные блокеры; сообщение пользователя в текущей работе. Human review и
  обязательный CI остаются необходимыми.

## Прослеживаемость

`ARCH-A03: конкурентное завершение` → единый порядок `Cycle → AS` →
`Api/m10_orchestration.py` → unit фиксация SQL claim + реальные browser сценарии
S10-A/T11-10 на изолированном PostgreSQL.

## Критерии приёмки

- [x] Все три M10 claim запроса блокируют строку Cycle, а не AS.
- [x] Два ранее зависавших browser сценария проходят без timeout/deadlock.
- [x] Исторические данные, FROZEN пакеты и публичный API не изменены.
- [ ] Обязательные CI jobs актуального head/base успешны.
- [ ] Human review выполнен.

## Проверки

- `git diff --check` — PASS.
- `python -m py_compile Api/m10_orchestration.py` — PASS.
- `pytest tests/unit/test_m10_orchestration_lock_order.py` — PASS, 1/1.
- `STAND_ADMIN_URL=<isolated pytest maintenance> npx playwright test
  tests/browser/runtime.spec.mjs --grep 'S10-A and T11-10 positive|S10-A character branch'
  --workers=1` — PASS, 2/2, 1.7 min.
- `pytest -m 'not integration and not e2e and not llm'` — PASS, 538/538.
- `pytest -m e2e tests/e2e` — PASS, 68/68.
- `TEST_DATABASE_URL=<isolated pytest DB> STAND_ADMIN_URL=<isolated maintenance>
  pytest --run-integration -m integration` — PASS, 149; 1 real-provider test
  штатно пропущен. Предыдущие два запуска были ошибками окружения: отсутствующая
  БД, затем отсутствующий отдельный maintenance URL; PASS им не приписывается.
- `npm run lint:js` — PASS; `node --test tests/frontend/*.test.mjs` — PASS,
  74/74; `npm run build:web` — PASS.
- Кандидат приложения: `2.0.18`, подготовлен `prepare_release.py`; проверка
  относительно `codex/fix-preparation-api-security` — PASS.

## Риски и откат

- Совместимость/схема/данные/безопасность: изменений нет.
- Эксплуатация: M10 работы одного Cycle теперь намеренно сериализованы на Cycle;
  независимые Cycle сохраняют параллельность через `SKIP LOCKED`.
- Откат: revert коммита возвращает прежние claim locks, но также возвращает
  воспроизведённый риск deadlock.

## План и состояние

- Завершено: локализация, код, unit-регрессия, адресный browser PASS.
- Активный шаг: полный локальный минимум и выпуск кандидата.
- Следующий шаг: PR поверх #103, CI, human review; затем продолжение A01.
- Открытые вопросы: нет для данного ограниченного исправления.
