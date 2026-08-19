# EVC review checklist

## Outcome and scope

- [ ] The diff implements the stated acceptance criteria and no unrelated behavior.
- [ ] Public API, data, configuration, and UI behavior changes are documented.
- [ ] Refactoring is separated from behavior changes or explicitly justified.

## Assessment invariants

- [ ] Published definitions and prompt bundles remain immutable.
- [ ] Running sessions use their stored snapshot and checksum.
- [ ] A draft cannot become the default configuration.
- [ ] Only registered components and predicates can be executed by a scenario.
- [ ] MBTI remains outside the target 4K methodology/runtime.

## Data and security

- [ ] Authorization is enforced server-side for every new operation.
- [ ] Logs and responses contain no secrets or unnecessary personal data.
- [ ] Schema changes are backward compatible or have an explicit migration and rollback.
- [ ] Tests cannot connect to a developer or production database.
- [ ] New environment variables are documented in every relevant `.env.*.example`.

## Reliability and operations

- [ ] Retry, idempotency, timeouts, and partial failures are handled where relevant.
- [ ] Queue jobs can recover from expired leases and do not duplicate active work.
- [ ] Operational failures are observable without exposing sensitive payloads.
- [ ] The change has a safe disable/revert path.

## Verification

- [ ] A regression test covers each fixed defect.
- [ ] Relevant unit and integration/HTTP paths are covered.
- [ ] `npm run lint:js` passes.
- [ ] `npm run build:web` is reproducible and committed output is current.
- [ ] `npm run test:backend` passes.
- [ ] Database integration tests pass when database behavior changed.
- [ ] `git diff --check` passes.

## Handoff

- [ ] PR links the ticket and gives exact verification steps.
- [ ] Risks, unverified behavior, deployment steps, and rollback are explicit.
- [ ] Screenshots, API examples, or logs are attached when they materially aid review.
