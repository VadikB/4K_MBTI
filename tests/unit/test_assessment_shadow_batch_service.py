from __future__ import annotations

from types import SimpleNamespace

import pytest

from Api.assessment_shadow_batch_service import AssessmentShadowBatchService


def target() -> dict:
    return {
        "session_id": 42,
        "user_id": 7,
        "competency": {
            "code": "communication",
            "shadow_evaluation": {
                "agent_definition": {"code": "communication_shadow", "version": 2},
            },
        },
        "snapshot": {
            "prompts": {
                "agent_definitions": {
                    "communication_shadow": {
                        "definition": {"runtime": {"max_attempts": 2}},
                    }
                }
            }
        },
    }


@pytest.mark.unit
def test_shadow_batch_preview_is_read_only_and_reports_maximum_attempts(monkeypatch) -> None:
    service = AssessmentShadowBatchService()
    monkeypatch.setattr(service, "_select_targets", lambda **_kwargs: [target()])

    result = service.preview(connection=object(), max_competency_runs=1)

    assert result["dry_run"] is True
    assert result["planned_competency_runs"] == 1
    assert result["maximum_llm_attempts"] == 2
    assert result["completed_runs"] == 0


@pytest.mark.unit
def test_shadow_batch_execute_requires_paid_confirmation_before_selection(monkeypatch) -> None:
    service = AssessmentShadowBatchService()
    monkeypatch.setattr(
        service,
        "_select_targets",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not select")),
    )

    with pytest.raises(ValueError, match="confirm_paid_calls"):
        service.execute(connection=object(), max_competency_runs=1, confirm_paid_calls=False)


@pytest.mark.unit
def test_shadow_batch_execute_requires_both_kill_switches(monkeypatch) -> None:
    service = AssessmentShadowBatchService()
    monkeypatch.setattr("Api.assessment_shadow_batch_service.settings", SimpleNamespace(
        assessment_universal_llm_enabled=True,
        assessment_universal_llm_shadow_enabled=False,
    ))

    with pytest.raises(RuntimeError, match="feature flags"):
        service.execute(connection=object(), max_competency_runs=1, confirm_paid_calls=True)


@pytest.mark.unit
def test_shadow_batch_execute_stores_shadow_only(monkeypatch) -> None:
    import Api.assessment_shadow_batch_service as module

    service = AssessmentShadowBatchService()
    saved: list[dict] = []
    monkeypatch.setattr(module.settings, "assessment_universal_llm_enabled", True)
    monkeypatch.setattr(module.settings, "assessment_universal_llm_shadow_enabled", True)
    monkeypatch.setattr(service, "_select_targets", lambda **_kwargs: [target()])
    monkeypatch.setattr(
        service,
        "_build_input",
        lambda **kwargs: SimpleNamespace(kind="shadow" if kwargs["shadow"] else "official"),
    )
    monkeypatch.setattr(service, "_load_official_summary", lambda **_kwargs: {"status": "evaluated", "skills": []})

    class Executor:
        def __init__(self, _strategies):
            pass

        def execute(self, **_kwargs):
            return SimpleNamespace(status="evaluated", assessments=[])

    class Repository:
        def save_success_with_summary(self, **kwargs):
            saved.append(kwargs)

    monkeypatch.setattr(module, "CompetencyEvaluatorExecutor", Executor)
    monkeypatch.setattr(module, "assessment_shadow_repository", Repository())

    result = service.execute(connection=object(), max_competency_runs=1, confirm_paid_calls=True)

    assert result["completed_runs"] == 1
    assert result["failed_runs"] == 0
    assert saved[0]["official_input"].kind == "official"
    assert saved[0]["shadow_input"].kind == "shadow"


@pytest.mark.unit
@pytest.mark.parametrize("limit", [0, 5])
def test_shadow_batch_limit_is_hard_capped(limit: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 4"):
        AssessmentShadowBatchService().preview(connection=object(), max_competency_runs=limit)
