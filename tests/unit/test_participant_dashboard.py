from Api.routes import _participant_cycle_outcome


def test_closed_cycle_waits_for_report() -> None:
    status, label, _, action, button = _participant_cycle_outcome({"status": "processing"})

    assert (status, label, action, button) == (
        "processing", "Результат готовится", "open_processing", "Подробнее",
    )


def test_owned_report_is_an_explicit_result_action() -> None:
    status, label, _, action, button = _participant_cycle_outcome(
        {"status": "report_ready", "report_id": "report-1"},
    )

    assert (status, label, action, button) == (
        "report_ready", "Результат готов", "open_report", "Посмотреть результат",
    )


def test_processing_failure_wins_over_previously_created_report() -> None:
    status, label, description, action, _ = _participant_cycle_outcome(
        {"status": "failed", "report_id": "limited-report"},
    )

    assert status == "failed"
    assert label == "Не удалось подготовить результат"
    assert "Повторно проходить" in description
    assert action == "open_processing"
