# EVC task brief: self-contained evaluator input

## Outcome

Each current 4K competency evaluator receives all prompt configuration, skills,
rubrics, cases, and user evidence in its validated input contract and performs no
methodological reads while calculating the result.

## Scope

- Included:
  - typed skill, rubric, case-evidence, and prompt-config input structures;
  - loading current database material before the evaluator boundary;
  - evaluation of the supplied material by the existing algorithm;
  - backward-compatible `evaluate_session` facade and regression tests.
- Excluded:
  - moving result persistence out of the legacy evaluator;
  - changing SQL sources, prompts, scoring, methodology, or database schema;
  - Markdown agent definitions or new agent version tables.

## Context

- Ticket: not provided.
- Relevant entry points: `Api/communication_agent.py`,
  `Api/assessment_evaluator_contracts.py`, `Api/assessment_analysis_queue.py`.
- Architecture/ADR: ADR-001 and `docs/architecture/assessment-runtime.md`.
- Existing contracts: `SkillEvaluation`, evaluator contract v1, analysis queue
  unit and integration tests.

## Constraints and risks

- Compatibility: `evaluate_session` and stored result formats remain supported.
- Data and migrations: none.
- Security and personal data: evidence remains in process memory and must not be
  added to logs or stage output.
- External services/LLM: unchanged.
- Performance and operations: do not add database or network calls; material is
  loaded before evaluator calculation rather than incrementally per skill.

## Acceptance criteria

- [x] Contract input contains agent prompts, skills, rubrics, cases, and evidence.
- [x] The queue's real evaluators calculate from the validated contract material.
- [x] No scoring or persistence behavior changes.
- [x] The legacy direct `evaluate_session` entry point remains compatible.
- [x] Invalid nested input is rejected before evaluator calculation.

## Verification plan

- Unit: nested contract validation, material loading/adaptation, legacy fallback,
  and existing queue behavior.
- Integration/HTTP: existing PostgreSQL queue test when isolated database access
  is available.
- Manual/test environment: deferred to baseline acceptance.
- Observability: do not place evidence in stage output or logs.

## Rollback

Revert the material-loading path and restore the contract v1 orchestration-only
input. No stored data migration or cleanup is required.

## Agent handoff

- Decisions made: persistence separation is deferred to slice 1c.
- Files changed: evaluator contracts, legacy competency agent facade/material path,
  queue wiring, contract tests, and this task brief.
- Checks completed: focused unit tests and complete non-integration backend suite;
  final repository gates recorded in the task handoff.
- Known gaps: evaluator still persists results.
- Next safe step: introduce an evaluation result repository outside the evaluator.
