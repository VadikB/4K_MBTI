# Assessment platform baseline v1

Status: **candidate — not yet ratified**

This document is the evidence record for turning the assessment-platform branch into an immutable baseline. A baseline is a tested commit/tag, not a moving branch.

## Invariants included in the candidate

- Methodology, scenario, and assessment configuration are independently versioned.
- Published definition versions are immutable; changes begin from a cloned draft.
- A session stores an execution snapshot and checksum.
- Prompt resolution for a running session uses the frozen snapshot.
- Methodologist and publisher permissions are separated.
- The test environment deploys only after frontend, unit, and database integration checks.

## Ratification gates

Record links or immutable identifiers rather than free-form assurances.

- [ ] Architecture review against ADR-001 — reviewer/result:
- [ ] Pull request review completed — PR:
- [ ] CI frontend lint/build passed — run:
- [ ] CI unit tests passed — run:
- [ ] CI PostgreSQL integration tests passed — run:
- [ ] Critical HTTP/user-journey smoke passed — run/evidence:
- [ ] Exact commit deployed to `test` — commit/version/URL:
- [ ] Methodologist acceptance completed — tester/date/result:
- [ ] Technical owner acceptance completed — tester/date/result:
- [ ] Rollback rehearsal or verified procedure — evidence:
- [ ] Merge to `main` completed — commit:
- [ ] Annotated baseline tag created — tag:

## Known limitations at candidate stage

- Real-provider LLM checks are opt-in and are not part of the default suite.
- Full browser user-journey coverage is not yet part of CI; critical HTTP and database contracts are the minimum ratification gate.
- Deployment and manual acceptance are external evidence and cannot be satisfied by a source-code commit alone.

## Required tag

After every gate above is complete, create an annotated tag on the accepted `main` commit:

```bash
git tag -a assessment-platform-baseline-v1 -m "Assessment platform baseline v1"
```

Do not reuse or move this tag. Further work starts from short-lived task branches and produces a new baseline/release identifier when needed.
