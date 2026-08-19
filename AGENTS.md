# Enterprise Vibe Coding contract

These instructions apply to the whole repository.

## Before changing code

1. Read `README.md`, `CONTRIBUTING.md`, and the architecture document relevant to the task.
2. Restate the intended outcome, scope, exclusions, constraints, acceptance criteria, and rollback path.
3. Inspect existing contracts and tests before proposing new abstractions.
4. For work spanning more than one component, write a short implementation plan and keep only one step in progress.

Use `docs/evc/task-template.md` for non-trivial work. Do not start implementation while a material product, data, security, or migration decision is unresolved.

## Change boundaries

- One task and one independently reviewable user or operational outcome per pull request.
- Keep refactoring separate from behavior changes unless it is strictly required for the outcome.
- Preserve public API and stored-data compatibility unless the task explicitly authorizes a migration.
- Never edit a published assessment methodology, scenario, configuration, or prompt bundle in place. Clone it to a new draft version.
- A running assessment must use its stored execution snapshot; it must not resolve mutable "current" methodology settings.
- Do not add MBTI to the versioned 4K methodology/runtime defined by ADR-001.
- Do not read, print, commit, or transmit secrets or production/test personal data.
- Do not use a developer or production database for automated tests.

## Required verification

Run the smallest relevant checks during implementation. Before pull request handoff run:

```bash
npm run lint:js
npm run build:web
npm run test:backend
git diff --check
```

When database behavior changes, also run the integration suite against an isolated database whose name contains `test` or `pytest`:

```bash
TEST_DATABASE_URL=postgresql://... npm run test:backend:integration
```

Bug fixes require a regression test. Changes to authoring, session creation, execution snapshots, queues, authentication, permissions, or report completion require an integration or HTTP contract test. Real LLM calls must be explicitly marked `llm` and are never part of the default test command.

## Review and handoff

Review the finished diff using `docs/evc/review-checklist.md`. Report:

- outcome and files changed;
- checks run and their exact result;
- unverified behavior and why it remains unverified;
- configuration, schema, deployment, security, and rollback considerations;
- the smallest safe next step.

Never describe a branch as the baseline until all gates in `docs/evc/baseline-v1.md` are recorded as passed for an immutable commit/tag.
