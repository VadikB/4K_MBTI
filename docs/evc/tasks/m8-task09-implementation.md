# M8 Task 09 — Results и базовый Report

## Результат и границы

На базе `c1bdd8dcecb0dc5d70b32969d384869c7ab602e3` реализованы один логический
Results на Cycle, неизменяемые расчётные revisions, versioned C-67 для трёх
аудиторий, owner screen и PDF из одного сохранённого C-67. Recommendations,
Skill Level и Competency aggregate не создаются.

Интегрированный аудит задач 1–8 выявил, что утверждённые GC и проверенная область
Reliability отсутствуют, а основной orchestration от закрытия Cycle до выпуска
Report ещё не подключён. Поэтому технический QA использует синтетический контур;
полный реальный T9-18 и методологическая приёмка остаются для Task 10.

## Источники и трассировка

Прочитаны AGENTS, README, CONTRIBUTING, EVC workflow/matrix/recipe, Change 01,
ADR-002, Registry, M1 v1.4, постановки 04/07/08/09 и M8 v1.2 SHA-256
`a61909c996f66e88668c4cf713fb91129f3ab778ed843d0e796c7d4e226b73fa`.

| Правило | PM/LU и контракт | Реализация/данные | Проверка |
|---|---|---|---|
| один Results, история revisions | PM-06, LU-06.1, C-56→Results | `m8_results`, `m8_result_revisions`, keys | T9-02/03/14 integration |
| четыре исхода, точные Score и пять покрытий | PM-06, LU-06.2 | frozen C-56 projection | T9-04–07 unit/integration |
| без Skill Level и CompetencyScore | PM-06 | comparison policy, competency `score=null` | T9-07/08 unit |
| три аудитории одной revision | PM-06/07, C-67 | immutable `m8_reports` | T9-12–14 unit/integration |
| экран и PDF одного C-67 | PM-07, LU-07.1–07.2 | owner routes, report screen, PDF | T9-13/16 HTTP/integration |
| права по прямой ссылке | PM-07 | owner/admin server checks | T9-12 HTTP |

## T9 и R9

| Проверка | Статус | Доказательство/ограничение |
|---|---|---|
| T9-01–08 | PASS | unit + PostgreSQL: ready gate, consistency, idempotency, исходы, zero/null, покрытия, Level/Gap |
| T9-09–11 | PASS на сохранённом C-56 | provenance, Confidence/Reliability, Sessions/AS/time передаются без пересчёта |
| T9-12–14 | PASS | три аудитории, immutable revisions, owner PDF и один C-67 для UI/export |
| T9-15–17 | PASS технически | пустые outcomes, Unicode PDF, renderer failure не меняет Results; recovery worker не входит |
| T9-18 | NOT_RUN | нет принятого реального контура 1–8, approved GC и автоматической orchestration |

R9-A–R9-F покрыты unit/aggregation fixtures; R9-G — status gate; R9-H — история
Results/Report revisions и три аудитории. Это TECH fixtures, не GC и не вывод о
содержательной правильности IA.

## Изменённые контуры

- `Api/m8_results*.py`, `Api/m8_report_package.py`: schema, producer, C-67 и PDF;
- `Api/routes.py`: admin creation/read/export и owner read/export;
- `assessment_definitions/reports/m8_basic_report/v1`: versioned draft template;
- `web`: состояния M8 Report, точные значения, покрытия и ограничения;
- unit, HTTP и PostgreSQL integration tests.

## Проверки

- `py_compile` и `node --check`: PASS;
- M8 unit + HTTP: PASS, 8 tests;
- PostgreSQL integration `tests/integration/test_m6_evidence_db.py`: PASS для всех
  выбранных integration cases;
- полная локальная регрессия: 313 backend и 28 HTTP tests PASS; frontend lint и
  production build PASS;
- реальный LLM, approved GC, Reliability protocol, product path T9-18: NOT_RUN.

Откат: убрать M8 routes и UI-entry, не удаляя immutable Results/C-67. Следующая
задача должна подключить transaction/outbox orchestration после расчёта, retry и
полный пользовательский переход, затем выполнить T9-18 на принятом контуре.
