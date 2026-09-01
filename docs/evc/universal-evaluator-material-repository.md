# EVC task brief: universal evaluator material repository

## Outcome

`runtime.mode=universal_llm` loads skills, rubrics, cases and evidence through a
generic repository selected by frozen methodology `skill_codes`; it no longer
requires a competency-specific Python agent or legacy evaluator prompt profile.

## Scope

- Included: generic read-only material repository; explicit methodology
  `skill_codes`; queue/provider routing; publication compatibility validation;
  unit and isolated PostgreSQL tests.
- Excluded: changing published 4K v1, schema migration, new methodology content,
  legacy loader removal, shadow persistence and production enablement.

## Constraints and risks

- Compatibility: legacy definitions keep their existing agents/loaders/prompts.
- Data: repository reads current session/skill/rubric/case tables; no writes.
- Security: only the current session and explicitly frozen skill codes are read.
- LLM: no real provider call is required for this slice.

## Acceptance criteria

- [x] Universal queue execution does not resolve a legacy strategy.
- [x] Universal materials are restricted to frozen `skill_codes`.
- [x] Universal configuration publication does not require a legacy prompt profile.
- [x] Universal publication fails without explicit non-empty `skill_codes`.
- [x] Legacy methodology and execution remain unchanged.
- [x] Repository output passes the existing self-contained input contract.

## Verification plan

- Unit: routing and publication validation.
- Integration: repository SQL and authoring-to-universal execution in isolated DB.
- Regression: standard backend, HTTP, integration, lint/build and diff gates.

## Rollback

Revert universal provider routing; keep the kill switch false. No data rollback is
needed because this change is read-only and additive.

## Agent handoff

- Decisions made: skill membership remains methodology content and is frozen as
  `competency.skill_codes`; AgentDefinition remains behavior/runtime content.
- Files changed: generic material repository, queue routing, configuration
  publication validation, runtime architecture, unit/integration tests and brief.
- Checks completed: 112 default backend tests, 3 HTTP tests, 15 isolated
  PostgreSQL integration tests, JS lint, web build, Python compile and
  `git diff --check`.
- Schema/config/deployment: no schema or environment change; universal kill switch
  remains false.
- Security: repository reads only one session and explicitly frozen skill codes;
  no secrets or external calls.
- Rollback: revert provider routing or keep universal runtime disabled.
- Next safe step: add shadow result persistence and comparison gates without
  changing official assessment results.
