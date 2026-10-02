# M6 Task 08 — агрегация Cycle и C-56

Дата: 2026-10-02. Статус: **IMPLEMENTED — local technical QA**.
Ветка: `codex/m6-task08-cycle-aggregation`. База: Task 07 commit `93596e7`.

## Результат и граница

Реализованы PM-05/LU-05.4, неизменяемые редакции расчёта и C-56: final IA одного
Cycle, явные решения допуска, трёхступенчатая арифметика, четыре исхода Skill,
пять покрытий в plan/full-M2 разрезах и атомарная сверка с C-46. Результат хранит
точные дроби, состав, версии, IA/confidence и статус Reliability `not_verified`.

Не входят Results/C-67/Report задачи 9, Skill Level/Gap/Recommendations, утверждение
GC, эмпирическая проверка Reliability и product UI. Содержательный допуск передаётся
явным QA-решением версии `m6-admission-manual/1.0`; свободный LLM не считает Scores.

## Источники и трассировка

Прочитаны AGENTS, README, CONTRIBUTING, EVC workflow/matrix/recipe; задачи 1–8;
Change 01, ADR-002, Registry, M1 v1.4 и M6 v1.8 SHA-256
`2e5f60a5f1c430458a253ec0bb4638555de1bec704ea02f1e5c2127a3abd39b4`.

- M6.7.1–7.2 → адресный допуск всего набора IA и вклад Indicator;
- M6.7.3 → равные веса внутри Component и между Components, partial без округления;
- M6.7.4 → четыре исхода Skill, число 0 отличается от отсутствия результата;
- M6.8.2 → разброс сохраняется, универсальный порог и удобное подмножество запрещены;
- M7.7.5/Change 01 И-4–И-5 → общий состав C-46/C-56 и `COMPOSITION_MISMATCH`;
- M6.8.3 → воспроизводимый C-56, qualitative Confidence и явный Reliability status.

Правила вынесены в versioned draft package
`assessment_definitions/aggregation/m6_cycle_aggregation/v1`; IA/EB не дублируются.

## Проверки

- unit E8-A–E8-E и запрет удобного подмножества: PASS, 6 tests;
- PostgreSQL end-to-end final IA → C-56 → C-46: PASS, 1 test;
- `npm run test:backend`: PASS, 310 passed, 95 deselected;
- `npm run test:backend:http`: PASS, 27 passed;
- полный PostgreSQL integration на изолированной `pytest` БД: PASS, 64 passed,
  341 deselected;
- frontend CI-equivalent: `npm audit` — 0 vulnerabilities, lint PASS,
  3 frontend tests PASS, build PASS и `web/dist` без содержательного изменения;
- `py_compile`, package/source checksum и `git diff --check`: PASS;
- реальные LLM, утверждённые GC и Reliability: NOT_RUN, не входят в technical QA.

## Риски и откат

Решения содержательного допуска пока создаёт уполномоченный QA-контур; это не
автоматическая методологическая приёмка. Откат: отключить два admin endpoint и
producer; неизменяемые IA, расчёты, C-46/C-56 сохранять для аудита, закрытый Cycle
не открывать и не удалять историю.
