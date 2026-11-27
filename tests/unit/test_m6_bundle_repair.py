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


@pytest.mark.parametrize("change,path", [
    ("quote", "fragments.0.quote"),
    ("observation", "signals.0.observation"),
    ("indicator", "evidence.0.indicator_id"),
    ("removal", "fragments.0.id"),
])
def test_repair_rejects_changes_to_verified_basis_at_the_field(mechanism, change, path):
    def changed_reply(material):
        result = complete_reply(material)
        fragment, price = result["fragments"]
        if change == "quote":
            fragment.update({key: price[key] for key in ("quote", "start", "end") if key in price})
        elif change == "observation":
            result["signals"][0]["observation"] = "Запросил цену."
        elif change == "indicator":
            criterion = material["criteria"][2]
            evidence = result["evidence"][0]
            evidence["indicator_id"] = criterion["id"]
            evidence["attribution"]["function"] = criterion["function"]
            result["bundles"][0]["evidence_ids"] = []
            result["bundles"][2]["evidence_ids"] = [evidence["id"]]
        else:
            for field in ("fragments", "signals", "evidence"):
                result[field].pop(0)
            result["bundles"][0]["evidence_ids"] = []
        return result

    def other_record_error(material):
        result = complete_reply(material)
        result["evidence"][1]["m2_version"] = "invalid-version"
        return result

    gateway = RecordedEvidenceGateway(other_record_error, changed_reply)
    with pytest.raises(ValueError, match="M6_REPAIR_BASIS_") as failure:
        evaluate(synthetic_material(TARGETS[:3]), mechanism, definition_checksum(mechanism), gateway=gateway)

    assert len(gateway.calls) == 2
    rejected, final = failure.value.ai_trace["validation_attempts"]
    assert rejected["validation_errors"] == [{"code": "TARGET_SET_MISMATCH", "path": "evidence.1.m2_version"}]
    assert final["status"] == "rejected"
    code = "M6_REPAIR_BASIS_MISSING" if change == "removal" else "M6_REPAIR_BASIS_CHANGED"
    assert {"code": code, "path": path} in final["validation_errors"]


@pytest.mark.parametrize("reason,correct_turn,keep_observation", [
    ("irrelevant", True, False),
    ("unclear", True, True),
    ("irrelevant", False, False),
    ("unclear", True, False),
], ids=["irrelevant-with-source", "unclear-with-observation", "wrong-source", "unclear-without-observation"])
def test_repair_allows_only_grounded_reassessment(mechanism, reason, correct_turn, keep_observation):
    def reassess(material):
        result = complete_reply(material)
        turn_id = result["fragments"][0]["turn_id"]
        result["evidence"].pop(0)
        result["bundles"][0]["evidence_ids"] = []
        result["bundles"][0]["opportunity_basis"] = "Ход показывает намерение, но не обосновывает свидетельство."
        if not keep_observation:
            result["fragments"].pop(0)
            result["signals"].pop(0)
        result["attribution_notes"] = [{
            "indicator_id": "K1.I06", "reason": reason,
            "explanation": "Намерение сверить сроки не показывает, какие сведения были отобраны для сообщения.",
            "context_refs": [{"kind": "turn", "id": turn_id if correct_turn else "other-turn",
                              "meaning": "Ход с намерением сверить сроки"}],
        }]
        return result

    material = synthetic_material(TARGETS[:3])
    material["turns"].append({"turn_id": "other-turn", "speaker_type": "system", "sequence_no": 2,
                              "content": "Следующий вопрос ведущего."})
    gateway = RecordedEvidenceGateway(partial_reply, reassess)
    if correct_turn and (keep_observation or reason == "irrelevant"):
        analysis, trace = evaluate(material, mechanism, definition_checksum(mechanism), gateway=gateway)
        assert analysis["bundles"][0]["evidence_ids"] == []
        assert analysis["bundles"][0]["opportunity_basis"] == gateway.responses[1]["bundles"][0]["opportunity_basis"]
        assert analysis["attribution_notes"][0]["context_refs"][0]["id"] == "synthetic-turn"
        assert trace["validation_attempts"][-1]["status"] == "accepted"
        assert any(signal["id"] == "signal-schedule" for signal in analysis["signals"]) == keep_observation
    else:
        with pytest.raises(ValueError, match="M6_REPAIR_BASIS_MISSING") as failure:
            evaluate(material, mechanism, definition_checksum(mechanism), gateway=gateway)
        assert {"code": "M6_REPAIR_BASIS_MISSING", "path": "fragments.0.id"} in (
            failure.value.ai_trace["validation_attempts"][-1]["validation_errors"]
        )
    assert len(gateway.calls) == 2
