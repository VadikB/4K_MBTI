# AC18-FIX-02 — локальные evidence

Основание: `65c1f4c04466b60d4c6ce4611346fc92c617ed74` + рабочий diff ветки
`codex/ac18-fix02-preparation-start`. Дата: 07.11.2026. Данные синтетические;
реальный provider/LLM не вызывался.

## Матрица

| AC | Сценарий | Статус | Evidence / ограничение | Владелец |
|---|---|---|---|---|
| P2-AC01 | invalid JSON, отсутствующий/неполный/корректный/чужой protected review | PASS | `test_m5_functional_generation_service.py`, `test_assessment_start_readiness.py`; synthetic gateway | не просмотрено |
| P2-AC02 | admission закрыт при INCOMPLETE; AS не стартует | PASS | unit + HTTP + `test_pilot_start_admission_db.py`; первичный provider-инцидент не переписан | не просмотрено |
| P2-AC03 | queued/running/failed/network/service/ready и reload | PASS | frontend 150; browser readiness matrix на main; новый lost-start browser | не просмотрено |
| P2-AC04 | readback/idempotency/concurrent explicit start | PASS | SQL test `test_two_concurrent_explicit_starts_present_once_without_resetting_time`; существующие queue/fencing tests | не просмотрено |
| P2-AC05 | POST start commit + потеря ответа → GET того же runtime, одна AS, исходное время | PASS | новый frontend contract/unit/browser test; SQL concurrent start; 0 ответов в SQL gate suite | не просмотрено |
| P2-AC06 | revoked/stale scope и чужая область fail closed | PASS | `test_pilot_start_admission_db.py`, 7/7 | не просмотрено |
| P2-AC07 | работающий browser: first AS после lost response; 1440/768/390/320; horizontal overflow guard | PASS | `visual/*.png`; Chromium emulator, не физические устройства | не просмотрено |
| P2-AC08 | технический комплект передан; deploy/readback/owner acceptance | PARTIAL | PR #182 создан; CI повторно запущен после release bump; deploy/readback/owner acceptance не выполнены | не просмотрено |

## Кадры

- `visual/ac18-fix02-lost-start-1440.png` — SHA-256 `60449612d1a9f3b992deeac99b66c461a996e3fb3b6ae2a788d4ccb3a67c0b76`.
- `visual/ac18-fix02-lost-start-768.png` — SHA-256 `16baa3aa09fcc7c4722464afd13caf619ebca8925c556be1eea006542a6e41f1`.
- `visual/ac18-fix02-lost-start-390.png` — SHA-256 `4df64108ad9215aeade339d1bf4815c82f9b4543a63a538c8284fdd68d7df6bd`.
- `visual/ac18-fix02-lost-start-320.png` — SHA-256 `9e17c660782cbe3e6491af020f2ca6f09dc396c664a4709325e74307cf4f4d9f`.

Кадры показывают фактический frontend сборки рабочего diff после серверного readback
первой сохранённой AS. «До» не приложено: достоверного пользовательского кадра
исходного состояния в пакете нет; вымышленное состояние не создавалось.

## Команды и результаты

- Backend без integration/e2e/llm: `956 passed`, `354 deselected`, PASS.
- HTTP e2e: `108 passed`, `12 deselected`, PASS.
- SQL/HTTP PostgreSQL: `7 passed`, PASS; отдельный `postgres:16`, БД
  `f22_integration_pytest`, контейнер после теста остановлен.
- Frontend: `150 passed`, PASS.
- Новый browser lost-start: `1 passed`, PASS.
- `npm run lint:js`, `npm run build:web`, `git diff --check`: PASS.
- Release candidate: 2.0.76; первый CI release gate корректно отклонил 2.0.75,
  после штатного patch bump локальные build/lint/frontend 150/diff-check прошли.

Первая попытка SQL была `NOT_RUN_ENV`: sandbox запретил localhost до соединения;
повтор той же команды с разрешённым localhost завершился PASS. Первая попытка browser
была `NOT_RUN_ENV` из-за запрета локального listen; последующая тестовая ошибка strict
locator исправлена без изменения продукта, финальные два прогона PASS.

## Непроверенное

- real-provider M5 на текущем diff — NOT_RUN, отдельного разрешения нет;
- физический телефон и Safari/Firefox — NOT_RUN;
- PR #182 — создан; повторный CI после release bump — IN_PROGRESS;
- merge, test deploy и опубликованный readback — NOT_RUN;
- визуальное решение владельца — не просмотрено.
