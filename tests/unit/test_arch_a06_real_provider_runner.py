import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from Api import m5_functional_generation_service as functional_service

from scripts.run_arch_a06_real_provider_matrix import (
    MATRIX, require_external_output, run_row, safe_error_code, select_rows,
)


class ControlledGateway:
    enabled = True

    def chat_with_trace(self, messages, **kwargs):
        payload = json.loads(next(item["content"] for item in reversed(messages) if item["role"] == "user"))
        if ":generation:" in kwargs["routing_key"]:
            candidate = json.loads(json.dumps(payload["author_as_example"], ensure_ascii=False))
            materials = [item["MaterialID"] for item in candidate["Материалы"]]
            events = [item["EventID"] for item in candidate["События"]]
            characters = [item["CharacterID"] for item in candidate["Активные персонажи"]]
            for index, target in enumerate(candidate["IndicatorObservability"]):
                target.update({
                    "material_refs": materials[:1], "event_refs": events[:1],
                    "character_refs": characters[:1], "authority_refs": ["participant"],
                    "author_mapping": {"source_pointer": f"/IndicatorObservability/{index}",
                        "source_checksum": functional_service.checksum(
                            payload["author_as_example"]["IndicatorObservability"][index])},
                })
            content = json.dumps(candidate, ensure_ascii=False)
        else:
            required = ((payload.get("applicability_plan") or {}).get("required_checks")
                        or payload["protected_checks"])
            content = json.dumps({"checks": [{
                "check_id": item["check_id"], "status": "PASS", "reason": "controlled",
                "findings": [], "adversarial_review": {
                    "candidate_conflicts": [], "resolution": "controlled",
                },
            } for item in required]}, ensure_ascii=False)
        return SimpleNamespace(
            content=content,
            sent={"provider": "controlled", "parameters": kwargs},
            provider={"finish_reason": "stop", "request_id": kwargs["routing_key"]},
        )


def test_output_must_be_outside_repository():
    with pytest.raises(ValueError, match="A06_OUTPUT_MUST_BE_OUTSIDE_REPOSITORY"):
        require_external_output(Path(__file__).resolve().parents[2] / "evidence")


def test_default_selection_is_one_row_and_all_is_explicit():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert [row["id"] for row in select_rows(matrix, [], False)] == ["A06.C01.SALES"]
    assert len(select_rows(matrix, [], True)) == 27


def test_provider_error_details_are_not_persisted():
    assert safe_error_code(ValueError("M6_CONTEXT_REFERENCE")) == "M6_CONTEXT_REFERENCE"
    assert safe_error_code(RuntimeError("provider body: synthetic content")) == "DETAILS_REDACTED"


def test_controlled_runner_compiles_all_27_rows():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    for row in matrix["rows"]:
        result = run_row(matrix, row, ControlledGateway())
        assert result["package"]["version"] == "0.5"
        assert result["admission"]["status"] == "PASS", row["id"]
        assert result["generation_operation"]["kind"] == "generation"
        assert result["repair"] is None
        assert result["persistence_trace"] is not None
        assert result["m6"] == "NOT_RUN"
