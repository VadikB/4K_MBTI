from Api import telegram_channel as channel


def test_project_preview_uses_frozen_project_and_explicit_owner_terms(monkeypatch):
    project = {
        "code": "SYNTH-1",
        "name": "Synthetic project",
        "business_problem": "Synthetic task",
        "expected_result": "Synthetic outcome",
        "description": "Synthetic description",
        "stages": [],
    }
    snapshot = {
        "project": project,
        "course": {"name": "Synthetic course", "cohort": "pytest"},
    }
    row = {
        "organization_id": 17,
        "runtime_assignment_ref": "canonical",
        "snapshot_json": snapshot,
        "snapshot_checksum": "a" * 64,
    }
    monkeypatch.setattr(channel, "context", lambda *args: row)
    monkeypatch.setattr(channel, "service_actor", lambda *args: 42)
    calls = []

    def save(c, **kwargs):
        calls.append(kwargs)
        return {"id": 21, "source_checksum": "b" * 64}

    monkeypatch.setattr(channel.questionnaire_sources, "save_preview", save)
    monkeypatch.setattr(
        channel.questionnaire_sources, "public_revision", lambda row: {"id": row["id"]}
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Preview must never publish/confirm context")

    monkeypatch.setattr(channel.questionnaire_sources, "confirm", forbidden)
    terms = {
        "context_type": "Synthetic project",
        "purpose": "Owner purpose",
        "results_usage": "Owner usage",
        "case_reality_level": "Owner reality",
        "name_usage_rules": "Owner rule",
    }
    value = channel.preview_project_context(
        None, assignment_ref="external", terms=terms
    )
    assert value["project_snapshot_checksum"] == "a" * 64
    assert calls[0]["assignment_ref"] == "canonical"
    assert calls[0]["channel"] == "external_form"
    answers = calls[0]["answers"]
    assert answers["C01"]["name"] == project["name"]
    assert answers["C01"]["industry"] == snapshot["course"]["name"]
    import json

    activity = json.loads(answers["C01"]["activity_description"])
    assert activity["business_problem"] == project["business_problem"]
    assert activity["expected_result"] == project["expected_result"]
    assert answers["C02a"]["participant_text"] == terms["purpose"]
    assert answers["C03"]["participant_text"] == terms["results_usage"]
    assert answers["C17"]["organization_name_usage_rules"] == terms["name_usage_rules"]
    assert snapshot == {
        "project": project,
        "course": {"name": "Synthetic course", "cohort": "pytest"},
    }
