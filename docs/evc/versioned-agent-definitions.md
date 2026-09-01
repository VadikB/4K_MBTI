# EVC task brief: versioned competency-agent definitions

## Outcome

Methodologists can create, review, publish, and clone immutable competency-agent
definitions containing Markdown instructions and structured execution metadata;
assessment configuration publication freezes the selected published definitions.

## Scope

- Included:
  - `agent` as a versioned assessment definition type;
  - Markdown instruction, input/output contract, executor and runtime metadata;
  - draft/review/published/retired-compatible storage and immutable published rows;
  - platform permissions and existing generic authoring HTTP workflow;
  - backward-compatible bootstrap from the four active evaluator prompt profiles;
  - frozen `agent_definitions` section in configuration prompt bundle/snapshot.
- Excluded:
  - admin UI editor;
  - rewriting current scoring algorithms around Markdown;
  - changing current 4K methodology content;
  - arbitrary tools or executable code in definitions.

## Context

- Relevant entry points: core schema, assessment authoring service/routes,
  configuration publication, execution snapshot.
- Architecture: ADR-001 versioning and immutable snapshot invariants.
- Existing behavior: evaluator prompts are active-table records frozen into a
  configuration bundle, but agents have no independently versioned definition.

## Constraints and risks

- Compatibility: current methodology resolves definition code from evaluator
  component suffix; future methodologies may specify definition code/version.
- Data: additive tables and permissions only; no destructive migration.
- Security: Markdown is data, never executable Python/SQL/template code.
- Operations: configuration publication fails when no published compatible agent
  definition exists.

## Acceptance criteria

- [x] Agent definitions use the standard draft/review/publish/clone lifecycle.
- [x] Published versions are immutable at service and database levels.
- [x] Validation requires non-empty Markdown and registered executor metadata.
- [x] Current four evaluator definitions can be bootstrapped without changing
      methodology v1.
- [x] Published configuration freezes exact agent definition versions/checksums.
- [x] Running session snapshot does not resolve mutable agent definitions.

## Verification plan

- Unit: agent definition validation and lifecycle service contracts.
- Integration: schema/lifecycle/configuration freeze against isolated PostgreSQL.
- HTTP: generic authoring endpoints with `entity_type=agent`.
- Manual: deferred to baseline acceptance.

## Rollback

Stop resolving agent definitions during configuration publication and leave the
additive tables unused. Existing prompt bundles and session data remain readable.

## Agent handoff

- Decisions made: reuse generic definition JSON lifecycle; resolve legacy code from
  evaluator suffix and freeze the exact published version in configuration.
- Files changed: additive schema/permissions, agent definition bootstrap and bundle
  resolver, generic authoring validation/API, snapshot publication, architecture
  docs, unit/integration/HTTP tests, and this brief.
- Checks completed: 98 backend tests, 3 HTTP contract tests, 12 isolated PostgreSQL
  integration tests, Python compilation, JS lint, web build, and diff validation.
- Known gaps: current legacy evaluator algorithm does not yet interpret Markdown.
- Next safe step: make the generic executor consume the frozen definition.
