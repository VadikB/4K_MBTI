# Controlled shadow batch

## Outcome

A superadmin can preview and explicitly run a small paid shadow sample over completed sessions without changing official assessment results.

## Scope

- Included: superadmin-only dry-run/execute endpoint, newest-first eligible target selection, stored official summary comparison, maximum four competency runs.
- Excluded: UI, recurring jobs, bulk backfill, official result recalculation, session state changes, automatic feature-flag activation.

## Constraints and risks

- Compatibility: additive API; no schema migration.
- Security: response contains session ID and competency code only; no user text or evaluation payload.
- External services: execution may make paid DeepSeek calls and requires explicit confirmation plus both universal/shadow flags.
- Operations: synchronous and intentionally capped at four competency runs; failed shadow calls are recorded and do not affect official data.

## Acceptance criteria

- [x] Dry-run makes no LLM call or database write and reports targets and maximum attempts.
- [x] Execution is rejected without confirmation or either feature flag.
- [x] Existing shadow versions are skipped idempotently.
- [x] Official results and session state are not updated.
- [x] Success/failure is stored only in `assessment_shadow_evaluation_runs`.
- [x] Only superadmin can call the endpoint.

## Verification plan

- Unit: selection, cap, dry-run, confirmation and kill switches, stored summary.
- HTTP: authentication, authorization and conflict contract.
- Integration: idempotent selection against isolated pytest database.
- LLM: excluded from automated suite; controlled real execution remains an explicit operator action.

## Rollback

Remove the batch endpoint and service. Existing sanitized shadow comparison rows can remain or be removed separately by an explicit data operation.

## Verification result

- Default backend: 123 passed.
- HTTP contracts: 8 passed.
- Isolated PostgreSQL integration: 20 passed.
- JS lint, web build and whitespace check: passed.
- Operational dry-run on the configured local environment: 0 eligible runs and 0 maximum LLM attempts. Existing completed sessions predate frozen shadow configuration and were intentionally not retrofitted.
