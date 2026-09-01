# EVC task brief: universal competency evaluator

## Outcome

A competency `AgentDefinition` may select `runtime.mode: universal_llm`; the
runtime then evaluates the self-contained frozen input through one generic LLM
executor and returns the existing validated output contract.

## Scope

- Included: disabled-by-default kill switch; strict runtime configuration;
  Markdown-driven prompt; bounded retries; JSON parsing, identity/reference
  validation and exact executor routing; fake-LLM unit/integration tests; one
  explicitly marked minimal real-LLM smoke test.
- Excluded: changing the production default configuration, new methodology
  content, shadow-result persistence, automatic fallback to legacy scoring,
  production/personal data and batch real-LLM evaluation.

## Context

- Entry points: frozen agent-definition resolver, competency executor, DeepSeek
  gateway, analysis queue and authoring validation.
- Architecture: ADR-001; running sessions must use immutable snapshots.
- Existing contracts: `CompetencyEvaluationInput/Output v1`.

## Constraints and risks

- Compatibility: existing `legacy_adapter` definitions retain current behavior.
- Data/migrations: no schema change.
- Security: secrets are environment-only and never logged; test payloads are
  synthetic; Markdown is prompt data, never executable code.
- External service: real calls are `llm`-marked, bounded and excluded from default
  tests.
- Operations: kill switch defaults to false; failure is explicit after retry and
  never silently changes evaluator type.

## Acceptance criteria

- [x] Legacy definitions execute unchanged.
- [x] Universal execution is rejected while the kill switch is off.
- [x] Universal execution uses frozen Markdown and self-contained input only.
- [x] Invalid JSON, identity or source references never reach persistence.
- [x] Retry count, temperature, timeout and output tokens are bounded.
- [x] No automatic legacy fallback occurs.
- [x] Unit and isolated PostgreSQL tests cover the execution path.
- [x] Real LLM smoke is separately marked and bounded.

## Verification plan

- Unit: routing, kill switch, prompt, parsing, retries and reference validation.
- Integration: publish/freeze/execute universal definition using fake gateway.
- LLM: one synthetic skill/case, at most two provider calls.
- Observability: sanitized exception class/message; no prompt or key logging.

## Rollback

Set `ASSESSMENT_UNIVERSAL_LLM_ENABLED=false` and keep all definitions on
`legacy_adapter`; no stored data or schema rollback is required.

## Agent handoff

- Decisions made: one generic LLM evaluator; exact frozen input/output v1;
  disabled-by-default kill switch; strict `assessment_strict` runtime;
  `fallback=fail`; at most two attempts and 4096 output tokens.
- Files changed: runtime/configuration validation, universal executor, DeepSeek
  output-token limit, environment templates/local flag, architecture/README,
  unit/integration/real-LLM tests and this brief.
- Checks completed: 108 default backend tests, 3 HTTP tests, 13 isolated
  PostgreSQL tests, 1 bounded real-LLM smoke, JS lint, web build, Python compile
  and diff validation.
- Known gap: universal evaluation is generic, but current runtime material loading
  still reuses the legacy competency data loaders. Adding a brand-new competency
  code without a current loader/profile requires a separate generic material
  repository slice.
- Deployment: keep `ASSESSMENT_UNIVERSAL_LLM_ENABLED=false`; no schema migration.
- Security: the real smoke used only synthetic content; credentials stayed in the
  ignored local `.env` and were neither printed nor changed.
- Next safe step: extract the generic competency material repository, then add
  shadow comparison storage before enabling any test configuration for users.
