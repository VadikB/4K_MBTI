# EVC context map

Load only the context needed for the task. Start with the common files, then add one relevant slice.

## Common

- `AGENTS.md` — development contract and safety boundaries.
- `README.md` — runtime, setup, and operational behavior.
- `CONTRIBUTING.md` — branches, CI, environments, and acceptance.
- `.github/PULL_REQUEST_TEMPLATE.md` — required handoff evidence.

## Assessment architecture and authoring

- `docs/adr/001-assessment-platform-architecture.md`
- `docs/architecture/assessment-runtime.md`
- `Api/assessment_configuration.py`
- `Api/assessment_runtime.py`
- `Api/assessment_authoring_service.py`
- `assessment_definitions/`
- `tests/unit/test_assessment_configuration.py`
- `tests/integration/test_assessment_authoring_workflow_db.py`

## Session execution and queues

- `Api/assessment_service.py`
- `Api/assessment_preparation_queue.py`
- `Api/assessment_analysis_queue.py`
- `Api/assessment_prompt_resolver.py`
- the matching unit and integration queue tests

## Interview and case generation

- `Api/assessment/interview/`
- `Api/assessment/case_generation/`
- relevant contract/unit tests only; avoid loading the legacy facade unless a compatibility path is involved

## HTTP and access control

- the targeted section of `Api/routes.py`
- related models in `Api/schemas.py`
- `Api/auth_service.py`, `Api/platform_access.py`, or `Api/org_access.py` as applicable
- HTTP contract and authorization tests

## Frontend

- the target entry or screen in `web/js/`
- shared modules actually imported by that screen
- matching CSS and preview assets
- `web/index.html` only when entry loading or static contracts change

Do not pass `.env`, database dumps, logs, production data, the full generated `web/dist`, or unrelated large legacy modules into agent context.
