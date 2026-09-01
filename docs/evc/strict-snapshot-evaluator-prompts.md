# EVC task brief: strict snapshotted evaluator prompts

## Outcome

Running assessment sessions resolve every competency evaluator configuration only
from their frozen execution snapshot, and incomplete configurations cannot be
published.

## Scope

- Included:
  - explicit missing-snapshot configuration error;
  - no active-table fallback when an execution snapshot is supplied;
  - publication validation for all methodology evaluator prompt profiles;
  - unit and PostgreSQL integration contracts.
- Excluded:
  - interviewer and case-generation fallback policy;
  - Markdown definitions and new agent version tables;
  - methodology content changes.

## Context

- Relevant entry points: prompt resolver, competency agent material loader,
  assessment configuration publication.
- Architecture: ADR-001 requires running sessions to use only their snapshot.
- Existing behavior: missing evaluator snapshot configuration silently reads the
  mutable active prompt tables.

## Constraints and risks

- Compatibility: legacy calls that genuinely have no snapshot retain fallback.
- Data: no migration; configuration publication fails if active evaluator profiles
  are incomplete.
- Security: errors contain component codes only, never prompt or evidence text.
- Operations: already-created incomplete snapshots fail explicitly rather than
  changing behavior retrospectively.

## Acceptance criteria

- [x] Supplied snapshot never triggers evaluator prompt-table reads.
- [x] Missing snapshotted evaluator configuration raises an explicit error.
- [x] No-snapshot legacy facade retains active-table fallback.
- [x] Configuration publication requires a prompt profile for every methodology
      evaluator.
- [x] Published bundle remains immutable and is copied into session snapshot.

## Verification plan

- Unit: resolver/agent strictness and publication bundle validation.
- Integration: authoring publication and frozen snapshot workflow in isolated DB.
- HTTP: existing authoring boundary; no route shape changes.
- Manual: deferred to baseline acceptance.

## Rollback

Restore mutable fallback and remove publish-time completeness validation. No schema
or stored-data rollback is required.

## Agent handoff

- Decisions made: strictness applies whenever a snapshot object is supplied.
- Files changed: prompt resolver, competency material loader, configuration
  publication validation, unit/integration fixtures and tests, and this brief.
- Checks completed: 95 backend tests, 11 isolated PostgreSQL integration tests,
  Python compilation, JS lint, web build, and diff whitespace validation.
- Known gaps: interviewer and case-generation fallbacks remain separate work.
- Next safe step: versioned Markdown agent definitions.
