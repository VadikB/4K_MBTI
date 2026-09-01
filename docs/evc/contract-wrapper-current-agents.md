# EVC task brief: contract wrapper for current competency agents

## Outcome

The assessment analysis runtime invokes the four existing 4K competency evaluators
through one explicit, versioned input/output boundary while preserving the current
methodology, scoring behavior, persistence, and reports.

## Scope

- Included:
  - versioned orchestration input and normalized output models;
  - an input builder based only on the frozen session snapshot;
  - a legacy adapter around the existing `evaluate_session` implementations;
  - runtime wiring and regression tests for the boundary.
- Excluded:
  - new methodology content or changes to `competencies_4k v1`;
  - Markdown agent definitions and agent-definition database tables;
  - moving legacy SQL reads or result persistence out of the agents;
  - aggregation, report, LLM prompt, rubric, or scoring changes.

## Context

- Ticket: not provided.
- Relevant entry points:
  - `Api/assessment_analysis_queue.py`;
  - `Api/communication_agent.py`;
  - `Api/assessment_runtime.py`.
- Architecture/ADR:
  - `docs/adr/001-assessment-platform-architecture.md`;
  - `docs/architecture/assessment-runtime.md`.
- Existing tests and contracts:
  - `tests/unit/test_assessment_analysis_queue.py`;
  - `tests/integration/test_assessment_analysis_queue_db.py`;
  - `SkillEvaluation` is the current internal result shape.

## Constraints and risks

- Compatibility: existing evaluator classes, methodology v1, database writes, and
  report reads must remain compatible.
- Data and migrations: no schema or stored-data changes.
- Security and personal data: contracts contain identifiers and normalized
  evaluation results; they must not be logged with dialogue or personal data.
- External services/LLM: no provider, prompt, or retry behavior changes.
- Performance and operations: validation is in-process and must not add database
  or network calls.

## Acceptance criteria

- [x] Every methodology evaluator invocation receives a validated contract input
      built from the frozen execution snapshot.
- [x] Existing agents run through a common adapter without changing their
      `evaluate_session` implementation.
- [x] Returned legacy evaluations are normalized and validated before the stage is
      reported complete.
- [x] Existing queue retry and completion behavior remains unchanged.
- [x] The current methodology definition and persistence schema are unchanged.

## Verification plan

- Unit: contract construction, legacy result normalization, invalid-result
  rejection, and queue invocation behavior.
- Integration/HTTP: existing analysis queue database contract tests.
- Manual/test environment: not required for the contract-only change; covered by
  the later baseline acceptance run.
- Observability: existing stage-run and queue failure records remain the source of
  operational status.

## Rollback

Revert the queue wiring and remove the contract/adapter module. Existing agent
implementations and stored results remain intact; no data rollback is required.

## Agent handoff

- Decisions made: use a transitional orchestration contract and a legacy adapter;
  defer extraction of all evaluator SQL reads and writes.
- Files changed: contract/adapter module, analysis queue wiring, unit and integration
  snapshot fixtures, unit contract tests, and this task brief.
- Checks completed: focused unit tests, full non-integration backend suite, JS lint,
  web build, Python compilation, and diff whitespace validation.
- Known gaps: input is not yet a self-contained evidence package.
- Next safe step: extract a snapshot-aware evaluation input builder without
  changing scoring behavior.
