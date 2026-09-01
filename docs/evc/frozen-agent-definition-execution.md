# EVC task brief: frozen agent-definition execution

## Outcome

Every competency evaluation is selected and instructed by the immutable
`AgentDefinition` stored in the session execution snapshot.

## Scope

- Included: strict snapshot resolution and checksum validation; input/output
  contract and executor validation; one executor registry for current legacy
  Python strategies; Markdown instructions and runtime metadata passed into the
  evaluation prompt.
- Excluded: methodology changes, scoring-formula changes, arbitrary executable
  tools in Markdown, UI authoring changes, and removal of legacy strategies.

## Context

- Relevant entry points: evaluator input builder, analysis queue, competency
  evaluator adapter, semantic rubric prompt.
- Architecture: ADR-001 and the immutable execution-snapshot invariant.
- Existing contracts: competency evaluation input/output v1 and published
  agent-definition v1.

## Constraints and risks

- Compatibility: direct legacy facade calls receive an equivalent in-memory
  definition; queued snapshot execution is strict.
- Data and migrations: none.
- Security: Markdown remains prompt data and is never executed.
- External services/LLM: default tests make no real LLM calls.

## Acceptance criteria

- [x] Queue execution fails if its frozen definition is missing or changed.
- [x] Executor selection uses exact component code/version, never list position.
- [x] Contract/executor/runtime metadata is validated before evaluation.
- [x] Frozen Markdown affects the semantic evaluator prompt and cache identity.
- [x] Current scoring behavior remains available through explicit legacy strategies.

## Verification plan

- Unit: definition resolution, tamper/mismatch rejection, exact strategy routing,
  Markdown prompt consumption.
- Integration: existing isolated PostgreSQL suites.
- Observability: execution errors identify the invalid definition or executor.

## Rollback

Revert the executor/input changes. Published definitions and snapshots are
additive data and remain valid for a later rollout.

## Agent handoff

- Decisions made: strict frozen definition for queued and snapshotted legacy
  execution; exact executor registry; only `legacy_adapter` runtime is accepted.
- Files changed: evaluator contracts/executor, analysis queue, legacy strategy
  prompt path, architecture, unit/integration fixtures and tests.
- Checks completed: 101 backend tests, 3 HTTP tests, 12 isolated PostgreSQL
  integration tests, JS lint and web build.
- Known gaps: current deterministic fallback does not interpret free-form Markdown;
  Markdown drives the semantic LLM path while the Python formula stays unchanged.
- Next safe step: define the first non-legacy executor contract or add controlled
  runtime capabilities once the new methodology requirements are approved.
