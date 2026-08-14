from Api.assessment.interview import DialogStateMachine


def test_counterpart_role_priority_matches_legacy_rules() -> None:
    machine = DialogStateMachine()

    assert machine.infer_counterpart_role("следующая смена и руководитель") == "peer"
    assert machine.infer_counterpart_role("развивающая беседа с сотрудником") == "employee"
    assert machine.infer_counterpart_role("встреча с заказчиком") == "client"
    assert machine.infer_counterpart_role("рабочая ситуация") == "generic"


def test_stage_plans_depend_on_role_and_development_mode() -> None:
    machine = DialogStateMachine()

    assert machine.stage_plan(counterpart_role="client", is_development_dialog=False)[0] == "next_step"
    assert machine.stage_plan(counterpart_role="manager", is_development_dialog=False) == (
        "criticality",
        "constraints",
        "agreement",
        "closure",
    )
    assert machine.stage_plan(counterpart_role="peer", is_development_dialog=True)[0] == "root_cause"


def test_reply_can_mark_multiple_stages_as_asked() -> None:
    stages = DialogStateMachine().infer_reply_stages(
        "Давайте разберем причину и затем обсудим, какая поддержка нужна."
    )

    assert stages == {"root_cause", "support_need"}


def test_unknown_stage_has_safe_label() -> None:
    assert DialogStateMachine().stage_label("unknown") == "рабочее продолжение разговора"
