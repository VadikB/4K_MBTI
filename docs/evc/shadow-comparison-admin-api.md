# Shadow comparison admin API

## Outcome

A superadmin can read aggregate official-versus-shadow evaluation statistics without receiving assessment payloads or session identifiers.

## Scope

- Included: read-only aggregate repository query, typed HTTP response, superadmin-only endpoint, authorization and database tests.
- Excluded: UI, batch execution, methodology changes, raw run export, user/session drill-down, feature-flag changes.

## Context

- Relevant entry points: `Api/routes.py`, `Api/assessment_shadow_repository.py`.
- Architecture: `docs/architecture/assessment-platform.md`, `docs/evc/universal-shadow-comparison.md`.
- Existing contract: `assessment_shadow_evaluation_runs` stores sanitized summaries and comparisons.

## Constraints and risks

- Compatibility: additive HTTP endpoint; no existing API changes.
- Data and migrations: no schema change.
- Security and personal data: superadmin only; response excludes session IDs, error details, evidence, rationale, excerpts, and user text.
- External services/LLM: none.
- Performance and operations: one totals aggregation and one grouped aggregation over the shadow-run table.

## Acceptance criteria

- [x] Missing session returns 401 and non-superadmin returns 403.
- [x] Superadmin receives totals and groups by competency and official/shadow agent version.
- [x] Agreement percent is derived from aggregate matched and compared skill counts.
- [x] Response contains no assessment payload or session identifier.

## Verification plan

- Unit: aggregate percentage and empty result behavior.
- Integration/HTTP: SQL aggregation against isolated pytest database; endpoint authentication and authorization contract.
- Manual/test environment: not required.
- Observability: read-only endpoint; existing HTTP logging applies.

## Rollback

Remove the route, response schemas, and aggregate repository method. No stored data is changed.

## Agent handoff

- Decisions made: superadmin-only access instead of adding a broader platform permission.
- Files changed: repository aggregate query, response schemas, route, unit/HTTP/integration tests, this task brief.
- Checks completed: lint, web build, backend unit suite, HTTP suite, isolated database integration suite, diff whitespace check.
- Known gaps: no pagination is needed because rows are grouped by finite agent-version combinations.
- Next safe step: controlled shadow batch after the aggregate endpoint is verified.
