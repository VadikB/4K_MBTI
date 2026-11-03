from Api.routes import _project_admin_assessment_stage


def row(**changes):
    value = {
        "assignment_id": 41,
        "assignment_status": "active",
        "revoked_at": None,
        "cycle_id": "11111111-1111-1111-1111-111111111111",
        "cycle_status": "prepared",
        "plan_status": "READY",
        "planned_positions": 3,
        "completed_positions": 0,
        "preparation_status": "completed",
        "acquaintance_status": "completed",
        "report_ready": False,
        "pipeline_status": None,
        "results_payload": None,
    }
    value.update(changes)
    return value


def test_start_requires_exact_cycle_and_ready_non_empty_plan():
    assert _project_admin_assessment_stage(row())["code"] == "ready_to_start"
    assert _project_admin_assessment_stage(row(plan_status=None, planned_positions=0))["code"] == "start_blocked"
    assert _project_admin_assessment_stage(row(plan_status="NO_ROUTE", planned_positions=0))["blocker"] == {
        "reason": "Для Cycle не найден допустимый маршрут.",
        "responsible": "Организатор оценки",
    }
    prepared_job_only = _project_admin_assessment_stage(row(cycle_id=None, cycle_status=None, plan_status=None, planned_positions=0))
    assert prepared_job_only["code"] == "preparation_complete"
    assert prepared_job_only["action"] is None


def test_runtime_states_stay_distinct_and_keep_progress():
    active = _project_admin_assessment_stage(row(cycle_status="active", completed_positions=1))
    paused = _project_admin_assessment_stage(row(cycle_status="paused", completed_positions=2))
    interrupted = _project_admin_assessment_stage(row(cycle_status="interrupted", completed_positions=2))
    assert [active["code"], paused["code"], interrupted["code"]] == ["active", "paused", "interrupted"]
    assert active["progress"] == {"completed": 1, "planned": 3}
    assert paused["blocker"]["responsible"] == "Участник"
    assert interrupted["cycle_id"] == "11111111-1111-1111-1111-111111111111"


def test_m8_result_meaning_is_separate_from_technical_failure():
    full = _project_admin_assessment_stage(row(
        cycle_status="calculated", report_ready=True,
        results_payload={"assessed_skill_profile": [{"outcome": "full_score"}],
                         "partial_result": {"is_incomplete": False}, "processing": {"status": "completed"}},
    ))
    partial = _project_admin_assessment_stage(row(
        cycle_status="calculated", report_ready=True,
        results_payload={"assessed_skill_profile": [{"outcome": "partial_score"}, {"outcome": "no_result"}],
                         "partial_result": {"is_incomplete": True}, "processing": {"status": "failed"}},
    ))
    insufficient = _project_admin_assessment_stage(row(
        cycle_status="calculated", report_ready=True,
        results_payload={"assessed_skill_profile": [{"outcome": "no_result"}],
                         "partial_result": {"is_incomplete": True}, "processing": {"status": "completed"}},
    ))
    assert full["result_summary"] == {"kind": "full", "label": "Полный результат", "technical_failure": False}
    assert partial["result_summary"]["kind"] == "partial"
    assert partial["result_summary"]["technical_failure"] is True
    assert insufficient["result_summary"]["kind"] == "insufficient"
    assert "score" not in insufficient["result_summary"]


def test_processing_failed_and_report_ready_keep_precedence():
    assert _project_admin_assessment_stage(row(cycle_status="calculation_pending"))["code"] == "processing"
    assert _project_admin_assessment_stage(row(cycle_status="calculated", pipeline_status="failed"))["code"] == "failed"
    assert _project_admin_assessment_stage(row(cycle_status="failed", report_ready=True))["code"] == "report_ready"
