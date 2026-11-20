from Api import telegram_channel as channel
import pytest


@pytest.mark.parametrize("field", ["email", "phone", "contacts", "agent4k_user_id"])
def test_project_context_rejects_contact_fields_before_database(field):
    value = {"schema_version": 1, "kind": "educational_project_assessment_context",
             "participant": {field: "synthetic-forbidden"}}
    with pytest.raises(ValueError, match="CONTACT_IDENTITY_FORBIDDEN"):
        channel.prepare(None, snapshot=value, snapshot_checksum=channel.checksum(value),
                        organization_id=17)


def test_changed_project_preview_cannot_be_confirmed(monkeypatch):
    monkeypatch.setattr(channel, "context", lambda *args: {
        "organization_id": 17, "runtime_assignment_ref": "canonical", "snapshot_checksum": "a" * 64})
    old = {"C02a": {"participant_text": "Synthetic reviewed purpose"}}
    changed = {"C02a": {"participant_text": "Synthetic changed purpose"}}

    class Connection:
        def execute(self, sql, params):
            assert params == (21, 17, "canonical", "project-snapshot:" + "a" * 64)
            return self

        def fetchone(self):
            return {"answers_json": changed}

    def forbidden(*args, **kwargs):
        raise AssertionError("Changed preview must never be published")

    monkeypatch.setattr(channel.questionnaire_sources, "confirm", forbidden)
    monkeypatch.setattr(channel, "service_actor", forbidden)
    with pytest.raises(ValueError, match="PROJECT_CONTEXT_PREVIEW_MISMATCH"):
        channel.confirm_project_context(Connection(), assignment_ref="external", revision_id=21,
                                        preview_checksum=channel.checksum(old))


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
        return {"id": 21, "answers_json": kwargs["answers"]}

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
