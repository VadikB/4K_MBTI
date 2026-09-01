# EVC task brief: agent-definition scheme smoke verification

## Outcome

An isolated PostgreSQL smoke test proves that an explicitly versioned agent
definition is published, frozen into a configuration snapshot, resolved by the
input contract, and routed to the expected evaluator implementation.

## Scope

- Included: authoring lifecycle, explicit methodology reference, configuration
  publication, snapshot freeze, checksum validation and executor routing.
- Excluded: real LLM calls, production data, new methodology content, default
  production configuration changes and UI testing.

## Constraints and risks

- Only a database whose name contains `test` or `pytest` may be used.
- The smoke definition uses the current `legacy_adapter`; its Markdown contains a
  unique marker so the resolved version can be proven without changing scoring.

## Acceptance criteria

- [x] Agent v2 passes draft/review/publish lifecycle.
- [x] A draft methodology explicitly selects agent v2.
- [x] Published configuration freezes v2 and its checksum.
- [x] Contract builder returns the unique v2 Markdown marker.
- [x] Executor routes the input to `evaluation.communication` v1.
- [x] No real LLM call is made.

## Result

- Dedicated smoke test: 1 passed.
- Full isolated PostgreSQL integration suite: 13 passed.
- Production/default database and real LLM were not used.

## Verification plan

- Integration: isolated PostgreSQL authoring-to-execution smoke test.
- Regression: standard backend, HTTP and integration gates.

## Rollback

The change adds only a test and documentation; removing them has no data impact.
