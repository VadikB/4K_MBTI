# Task 10 — remediation и сквозная приёмка

## База и цель

База: `8d2dd4ea76585baa570cec3e4fdb915d0585dc1b`, ветка
`codex/task10-remediation-acceptance`, чистое дерево на старте. В базу входят задачи
1–9 и интегрированный аудит на историческом `c1bdd8d`.

Цель — соединить существующие M5–M8 services в owner-scoped product path без
ручного superadmin запуска: подготовка Cycle/AS → Dialogue → M6 Evidence/IA → M7
уточнение/закрытие → содержательный допуск/расчёт → C-46/C-56 → Results/C-67 →
экран/PDF. Нормативное утверждение GC, CURRENT и выпуск не входят.

## Прочитано и исходная диагностика

AGENTS, README, CONTRIBUTING, EVC workflow/matrix/recipe; Change 01, ADR-002,
Registry, M1 v1.4; постановки 08, 09 и Task 10 v2; аудит задач 1–8; M6 v1.8,
M7 v1.3, M8 v1.2 и текущие реализации M5–M8.

- AUD-01 открыт: owner routes управляют только заранее созданным Cycle; legacy
  `/assessment/start` не связывает M7/M8 и не проверяет session owner на старте.
- содержательный допуск открыт: расчет принимает решения из admin payload.
- outbox закрытия не исполняется completion worker; M6 worker обрабатывает только
  уже созданные Evidence/IA requests.
- M6 input resolver и M7 planner помечены `qa` и блокируют assessment scope.
- AUD-03 открыт: continuation проверен отдельно, цельной трассы до C-67 нет.
- AUD-04 открыт: E8-F и история двух расчетных/Report revisions отсутствуют.
- AUD-02 частично реализован: versioned Evidence/IA mechanisms используют текущий
  DeepSeek gateway; provider smoke и approved GC отсутствуют.

## Рабочие шаги

1. Реализованы контракты product orchestration, assessment-scope M5/M7 и durable
   pipeline state/outbox без второго источника истины.
2. Реализован автоматический Evidence → final IA → versioned admission → расчет →
   Results/C-67; ошибки Evidence/IA не преобразуются в предметный результат.
3. Добавлены owner start/resume/next/turn/transition/clarification/control/completion/
   status/results/report/PDF API. Для legacy start и preparation status закрыт IDOR.
4. Добавлены цельные PostgreSQL S10-A, S10-B и S10-D; S10-C подтвержден
   существующей регрессией закрытия по deadline, E8-F — точным unit-вектором.
5. Выполнены локальные unit/e2e/PostgreSQL проверки и проверка PDF через Typst.

## Решения и границы

Использовать существующие таблицы M5–M8 и snapshots. Новый orchestrator хранит
только durable состояние исполнения и ссылки на существующие revisions. Вход можно
отключить конфигурацией; сохраненная история остается читаемой. Содержательный
механизм получает полный versioned manifest и сохраняет решения/trace; арифметика
остается в `m6_cycle_aggregation`.

Approved GC и независимые заключения — внешняя зависимость. До их появления
Reliability остается `not_verified`; provider smoke подтверждает транспорт, а не
нормативную точность.

## Проверки и передача

Исходные постановки и SHA-256:

- Task 10 v2 — `f14057e58aab71b058109d37d710656f09b209e3e3cc4cca8d1a36dbb6fcd23c`;
- Task 08 — `3e5b507ca95cfafb14403d9bc1917936b755a319eb76efa2fede45411f425ade`;
- Task 09 — `9f0b0a10a359f191eab6a3531322e30b04f44588e760ba3c2d8bacfdade32567`.
- Task 10.1 — `5a31c5760e1055cf5fa33156a7dca973e2c1a7fd40a8851307c77e32b7ee4cbf`.

## Task 10.1 — Runtime UI

Основной interview UI переключен на единственный маршрут Cycle runtime. По решению
владельца от 02.10.2026 продолжение legacy assessment через UI не сохраняется:
новый и повторный вход используют `POST /users/assessment/cycles/start`, который
возвращает существующий owner Cycle либо создает новый. Исторические записи и
старые отчеты из БД не удаляются.

Сохраненные идентификаторы UI: `productCycleId`,
`productAssessmentSituationId`; восстановление выполняет
`GET /users/assessment/cycles/{cycle_id}/runtime`. Read-model возвращает только
серверные Plan/Cycle/AS, Dialogue trace, последнее clarification decision и
pipeline state. Клиент не генерирует Dialogue и не вычисляет admission.

Подключенные переходы:

- Turn: `POST /users/assessment/m5/situations/{as_id}/turns`;
- scenario end: `POST .../{as_id}/transitions` с `scenario_end`;
- clarification answer: `POST /users/assessment/m7/clarifications/{id}/answers`;
- pause/resume: `POST /users/assessment/m7/cycles/{cycle_id}/control`;
- interruption/Additional Session: completion с `interrupt_for_continuation`,
  `additional-sessions`, затем `next`;
- close: completion с `complete`;
- processing/report: `GET /users/assessment/m8/cycles/{cycle_id}/status`, затем
  существующий M8 экран и `/users/assessment/m8/reports/{report_id}/pdf`.

После возврата вкладки UI повторно читает runtime. Idempotency keys и Turn UUID
создаются один раз на запрос; не принятый HTTP-ответ остается в состоянии ошибки.
Серверный deadline не останавливается при смене вкладки.

Для изолированной проверки добавлен opt-in
`AGENT4K_BROWSER_TEST_GATEWAY=1`. Он подменяет только AI-адаптеры M5/M6
детерминированным test gateway; обычный runtime и БД остаются настоящими. Флаг по
умолчанию выключен и не является fallback при ошибке provider.

Фактическая матрица на рабочем дереве от
`8d2dd4ea76585baa570cec3e4fdb915d0585dc1b`:

| Область | Свидетельство | Статус |
|---|---|---|
| S10-A | `test_s10_a_owner_path_reaches_versioned_report_without_admin_finalization` | PASS |
| S10-B / AUD-03 | `test_s10_b_additional_session_preserves_boundary_and_reaches_report` | PASS |
| S10-C | `test_background_calendar_expiry_closes_paused_cycle`; owner control/status API | PASS backend; UI browser trace NOT_RUN |
| S10-D | `test_s10_d_closed_cycle_without_presented_material_has_no_result_report` | PASS |
| S10-E | `test_s10_e_recalculation_preserves_old_results_and_report` | PASS |
| E8-F | `test_e8_f_exact_vector`; Score `4/3`, покрытия `4/5`, `3/5`, `3/5`, `3/3`, `1/3` | PASS unit |
| FROZEN GC integrity | `test_m6_gc_package.py` после выделения product adapters | PASS |
| M6/M7/M10 PostgreSQL | 33-test full regression PASS; M10 suite after S10-E — 4 PASS | PASS |
| Unit | `tests/unit` | PASS, 314 tests |
| HTTP e2e | `npm run test:backend:http` | PASS, 28 tests |
| Frontend | `npm run lint:js`; `npm run build:web` | PASS |
| PDF | S10-A/B и M8 integration, Typst, `%PDF` и размер | PASS |
| Diff | `git diff --check` | PASS |
| Runtime UI contracts | Cycle start/read-back/Turn/clarification/pause/Additional Session/processing/M8 wiring | PASS code/build |
| Browser S10-A/B/C | отдельная `product4k_browser_pytest` создана; репозиторий не поднимает базовую схему с нуля (`users`, `user_sessions`, `roles`, `organizations`, `user_role_profiles`, затем `session_cases` отсутствуют до EVC migrations) | NOT_RUN |
| Provider smoke | `DEEPSEEK_API_KEY*` отсутствуют в среде | NOT_RUN |
| Нормативный GC / Reliability | нет утвержденного эталона и независимых заключений | NOT_VERIFIED |

T10-01–06 покрыты immutable snapshots/checksums, трассами A/B/D и регрессией
M6/M7. T10-07–10 покрыты автоматическим versioned admission, точным E8-F и пятью
разрезами. T10-11–14 покрыты C-46/C-56/Results/C-67, owner API и PDF. T10-15
проверен mock-gateway и failure/retry регрессиями; реальный provider NOT_RUN.
T10-16: техническая готовность подтверждена, нормативная пригодность остается
`not_verified`.

UI-переключение реализовано, но U10-08 и browser S10-A/B/C не объявляются PASS.
Изолированный браузерный стенд нельзя поднять с нуля текущими средствами репозитория:
базовая схема до EVC-миграций не поставляется, а `ensure_core_schema()` является
набором ALTER/добавочных миграций. Рабочую БД с пользовательскими данными
для обхода не использовали. Влияние: связанный код, API и PostgreSQL path проверены,
но клики, скриншоты, browser network trace и PDF из браузера остаются NOT_RUN.

Откат: выключить product orchestration entrypoint/worker, сохранив immutable
C-45/C-54/C-46/C-56/Results/C-67 и прежние legacy/admin routes.
