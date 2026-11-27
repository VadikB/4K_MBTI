import pytest

from Api.assessment_configuration import definition_checksum
from Api.m6_evidence_service_v2 import evaluate, validate_current_analysis
from Api.m6_package_v2 import load_mechanism
from tests.m6_bundle_repair_fixture import ANSWER, TARGETS, RecordedEvidenceGateway, complete_reply, partial_reply

pytestmark = pytest.mark.unit


def synthetic_material(targets):
    return {
        "turns": [{"turn_id": "synthetic-turn", "speaker_type": "assessee", "sequence_no": 1, "content": ANSWER}],
        "events": [], "materials": [],
        "indicator_targets": [{"indicator_id": key, "m2_version": "v1.1"} for key in targets],
        "criteria": [{"id": key, "m2_version": "v1.1", "function": f"Функция {key}", "product": "Результат",
                      "evidence_pattern": "Наблюдаемое проявление", "boundary": "Исходная ситуация"} for key in targets],
    }


@pytest.fixture(params=["m6_evidence/1.0.1", "m6_evidence/1.0.2"])
def mechanism(request):
    return load_mechanism(request.param)


@pytest.mark.parametrize("targets", [TARGETS, TARGETS[:3]], ids=["nine-targets", "three-targets"])
def test_partial_reply_preserves_unaffected_records_and_only_lists_missing_ids(mechanism, targets):
    material = synthetic_material(targets)
    gateway = RecordedEvidenceGateway(partial_reply, complete_reply)
    analysis, trace = evaluate(material, mechanism, definition_checksum(mechanism), gateway=gateway)

    assert len(gateway.calls) == 2
    assert f"Недостающие indicator_id в bundles: {', '.join(targets[1:])}." in gateway.calls[1][-1]["content"]
    assert '"fragments[1]": "synthetic-turn"' in gateway.calls[1][-1]["content"]
    assert '"fragments[0]":' not in gateway.calls[1][-1]["content"]
    assert "Сохрани корректные bundles, fragments, signals, evidence, их ID и связи." in gateway.calls[1][-1]["content"]
    assert trace["validation_attempts"][0]["missing_indicator_ids"] == list(targets[1:])

    original, repaired = gateway.responses
    for field in ("signals", "evidence"):
        assert analysis[field] == repaired[field] == original[field]
    assert analysis["bundles"][0] == repaired["bundles"][0] == original["bundles"][0]
    for field, value in original["fragments"][0].items():
        assert analysis["fragments"][0][field] == value
    assert analysis["fragments"][1]["turn_id"] == "synthetic-turn"
    assert analysis["fragments"][1]["quote"] == "Уточню цену"
    assert [bundle["indicator_id"] for bundle in analysis["bundles"]] == list(targets)
    assert validate_current_analysis(analysis, material) == analysis


@pytest.mark.parametrize("invalid_json", [True, False], ids=["invalid-json", "unreadable-bundles"])
def test_retry_uses_full_response_path_when_bundle_ids_cannot_be_read(mechanism, invalid_json):
    def unreadable(material):
        return '{"fragments":' if invalid_json else {**complete_reply(material), "bundles": None}

    gateway = RecordedEvidenceGateway(unreadable, complete_reply)
    material = synthetic_material(TARGETS[:3])
    analysis, trace = evaluate(material, mechanism, definition_checksum(mechanism), gateway=gateway)

    assert len(gateway.calls) == 2
    assert len(analysis["bundles"]) == 3
    assert "Верни заново только полный JSON" in gateway.calls[1][-1]["content"]
    assert "Недостающие indicator_id" not in gateway.calls[1][-1]["content"]
    rejected, accepted = trace["validation_attempts"]
    assert rejected["error_code"] == ("M6_INVALID_JSON" if invalid_json else "M6_SCHEMA_VALIDATION")
    assert "missing_indicator_ids" not in rejected
    assert accepted["status"] == "accepted"
