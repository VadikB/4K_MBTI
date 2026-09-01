# EVC task brief: evaluator result repository

## Outcome

Current competency evaluators calculate validated outputs without writing to the
database; orchestration persists those outputs through one result repository while
preserving existing rows and report behavior.

## Scope

- Included:
  - case-level analysis output contract;
  - pure calculation result containing case analyses and skill assessments;
  - repository UPSERTs for `session_case_skill_analysis` and
    `session_skill_assessments`;
  - queue orchestration and backward-compatible `evaluate_session` facade;
  - regression tests for calculation/persistence separation.
- Excluded:
  - schema migrations, methodology or scoring changes;
  - transaction redesign across all four evaluators;
  - Markdown definitions and agent version authoring.

## Context

- Ticket: not provided.
- Relevant entry points: `Api/communication_agent.py`, evaluator contracts,
  analysis queue, report reads of the two result tables.
- Architecture: ADR-001 and assessment runtime.
- Existing behavior: both result tables use idempotent UPSERTs.

## Constraints and risks

- Compatibility: stored columns and values must remain identical.
- Data and migrations: none.
- Security and personal data: outputs contain evidence excerpts and must not be
  logged or exposed in stage output.
- External services/LLM: unchanged.
- Reliability: retries remain safe through the same UPSERT conflict keys.

## Acceptance criteria

- [x] Contract-aware evaluator calculation executes no database writes.
- [x] Both output collections are validated before persistence.
- [x] Repository uses the existing conflict keys and stored JSON formats.
- [x] Queue persists only after successful contract validation.
- [x] Legacy `evaluate_session` produces and persists the same result shape.

## Verification plan

- Unit: pure calculation boundary, repository SQL/parameters, invalid output
  rejection, queue behavior, and legacy facade compatibility.
- Integration: existing isolated PostgreSQL analysis queue suite when configured.
- Manual: deferred to baseline acceptance.
- Observability: queue/stage failures remain unchanged; evidence is not logged.

## Rollback

Restore evaluator-local UPSERT calls and remove repository orchestration. No schema
or stored-data rollback is required.

## Agent handoff

- Decisions made: preserve current UPSERTs exactly and validate before writing.
- Files changed: evaluator output contracts, pure legacy calculation path, result
  repository, queue orchestration, repository/contract tests, and this task brief.
- Checks completed: focused and full backend unit suites, isolated PostgreSQL
  integration suite (11 passed), Python compilation, JS lint, web build, and diff
  whitespace validation.
- Known gaps: transaction scope remains the existing per-job connection.
- Next safe step: remove active-prompt fallback for snapshotted sessions.
