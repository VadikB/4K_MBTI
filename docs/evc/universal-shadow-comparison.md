# EVC task brief: universal evaluator shadow comparison

## Outcome

An explicitly configured frozen universal agent may run after the official legacy
evaluator; its sanitized metrics are stored separately for comparison and never
change the official assessment, report or analysis completion.

## Scope

- Included: methodology `shadow_evaluation` contract; frozen shadow definition;
  disabled-by-default kill switch; additive idempotent storage; sanitized level,
  red-flag/evidence counts and case references; non-blocking failure handling;
  unit and isolated PostgreSQL integration tests.
- Excluded: production enablement, sampling, UI, raw shadow rationale/evidence
  persistence, automatic promotion, report changes and new methodology content.

## Constraints and risks

- Compatibility: official evaluator must remain `legacy_adapter`; shadow must be
  `universal_llm`; configurations without shadow are unchanged.
- Data: additive table only; no raw user text or LLM output is stored.
- External LLM: default/integration tests use fake gateway; no paid batch run.
- Operations: both universal and shadow environment switches default to false.

## Acceptance criteria

- [x] Shadow definition/version/checksum is frozen in the prompt bundle.
- [x] Shadow is disabled unless both kill switches are true.
- [x] Official output is persisted before shadow execution.
- [x] Shadow success stores only sanitized, idempotent comparison metrics.
- [x] Shadow failure is observable but cannot fail the official analysis job.
- [x] No-shadow and legacy execution remain unchanged.

## Verification plan

- Unit: contract validation, metric comparison and non-blocking queue behavior.
- Integration: schema/upsert and queue completion on shadow success/failure.
- Regression: full backend, HTTP, isolated DB, lint/build and diff gates.

## Rollback

Set `ASSESSMENT_UNIVERSAL_LLM_SHADOW_ENABLED=false`. The additive table may remain
unused; no destructive rollback is required.

## Agent handoff

- Decisions made: explicit frozen shadow reference; official legacy only; shadow
  universal only; separate code/version; no sampling in v1; no raw text storage.
- Schema: additive `assessment_shadow_evaluation_runs`, idempotent on session,
  competency and shadow agent version.
- Configuration: both universal switches default false; local `.env` synchronized
  without reading or changing credentials.
- Security: stored summaries exclude rationale, excerpts, prompts and raw output.
- Checks completed: 116 default backend tests, 3 HTTP tests, 18 isolated
  PostgreSQL integration tests, JS lint, web build, Python compile and diff check.
- Unverified: full `ensure_core_schema` was not run on a fresh production-shaped
  clone; the additive DDL and repository lifecycle are covered by isolated schema
  integration tests.
- Deployment: apply normal additive core-schema startup, keep shadow false.
- Rollback: disable `ASSESSMENT_UNIVERSAL_LLM_SHADOW_ENABLED`; table may remain.
- Follow-up completed: admin-only aggregate comparison API and capped controlled
  batch API with dry-run and explicit paid-call confirmation are implemented.
- Operational dry-run found no eligible historical sessions because their immutable
  execution snapshots predate `shadow_evaluation`; those snapshots were not modified.
