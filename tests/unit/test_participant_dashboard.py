from Api.routes import _participant_cycle_outcome


def test_closed_cycle_waits_for_report() -> None:
    status, label, _, action, button = _participant_cycle_outcome({"status": "processing"})

    assert (status, label, action, button) == (
        "processing", "Отчёт готовится", "open_processing", "Посмотреть состояние",
    )


def test_owned_report_is_an_explicit_result_action() -> None:
    status, label, _, action, button = _participant_cycle_outcome(
        {"status": "report_ready", "report_id": "report-1"},
    )

    assert (status, label, action, button) == (
        "report_ready", "Результат готов", "open_report", "Посмотреть результаты →",
    )


def test_processing_failure_wins_over_previously_created_report() -> None:
    status, label, description, action, _ = _participant_cycle_outcome(
        {"status": "failed", "report_id": "limited-report"},
    )

    assert status == "failed"
    assert label == "Не удалось подготовить отчёт"
    assert "Возвращаться к заданиям не требуется" in description
    assert action == "open_processing"


def test_limited_report_keeps_exact_report_action() -> None:
    status, label, _, action, _ = _participant_cycle_outcome(
        {"status": "report_ready", "report_id": "report-2", "report_limited": True},
    )

    assert (status, label, action) == ("report_limited", "С ограничениями", "open_report")


def test_progress_counts_confirmed_positions_for_saved_plan(monkeypatch) -> None:
    from Api import participant_dashboard

    cycle = {"id": 1, "cycle_id": "saved-cycle", "profile_ref_json": {"revision": 1}}
    reference = {"case_id": "case", "case_version": "v1"}
    saved = {"cycle_db_id": 1, "profile_ref_json": cycle["profile_ref_json"], "revision_id": "saved-plan",
             "content_json": {"route": [reference] * 8, "calendar_window_seconds": 259200}}
    monkeypatch.setattr(participant_dashboard.m7_planning_repository, "read_plan", lambda *_: saved)

    started = {**reference, "started_at": "fixture", "plan_revision_id": "saved-plan"}
    positions = [
        {**started, "position_no": 1, "state": "completed", "as_status": "closed"},
        {**started, "position_no": 3, "state": "in_progress", "as_status": "active"},
    ]

    class Connection:
        def execute(self, *_args):
            return self

        def fetchall(self):
            return positions

    progress = participant_dashboard.cycle_progress(Connection(), cycle)
    assert (progress["completed_positions"], progress["current_position_no"], progress["planned_total"]) == (1, 3, 8)
    assert progress["rules"] == {"calendar_window_seconds": 259200}
    positions[0].update(state="in_progress", scenario_ended_at="fixture")
    current = positions.pop()
    between = participant_dashboard.cycle_progress(Connection(), cycle)
    assert between["completed_positions"] == 1
    assert between["last_completed_position_no"] == 1
    assert between["between_situations"] is True
    positions[0]["state"] = "completed"
    positions.append(current)
    positions[0]["plan_revision_id"] = "unverified-plan"
    assert participant_dashboard.cycle_progress(Connection(), cycle)["completed_positions"] is None
    saved["content_json"].pop("route")
    unknown = participant_dashboard.cycle_progress(Connection(), cycle)
    assert unknown["completed_positions"] is None and unknown["planned_total"] is None
