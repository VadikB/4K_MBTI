"""SLS06 review package preserves review boundaries and exact Sales source refs."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "build_sls06_review_package", ROOT / "scripts/build_sls06_review_package.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_collects_nine_unreviewed_case_as_pairs() -> None:
    data = module.collect()
    assert data["package"]["runtime_enabled"] is False
    assert len(data["cases"]) == 9
    assert [case["case_id"] for case in data["cases"]] == [
        f"CASE.SPEC.{index:02d}" for index in range(1, 10)
    ]
    for case in data["cases"]:
        assert case["review_status"] == "NOT_REVIEWED"
        assert case["methodologist_decision"] == ""
        assert case["expert_decision"] == ""
        assert case["case_source"]["sha256"]
        assert case["as_source"]["sha256"]
        assert case["indicators"]


def test_case06_provenance_and_case09_versions_remain_explicit() -> None:
    cases = {case["case_id"]: case for case in module.collect()["cases"]}
    assert cases["CASE.SPEC.06"]["case_version"] == "v0.2"
    assert cases["CASE.SPEC.06"]["as_version"] == "v0.2"
    assert cases["CASE.SPEC.09"]["case_version"] == "v0.2"
    assert cases["CASE.SPEC.09"]["as_version"] == "v0.2"


def test_blind_review_inputs_do_not_contain_draft_analysis_or_conclusions() -> None:
    for path in module.M6_BLIND.glob("*.json"):
        if path.name == "manifest.json":
            continue
        payload = module.json.loads(path.read_text())
        assert "draft_analysis" not in payload
        assert "expert_card" not in payload
        assert payload["review_instructions"]["independent_first_opinion_required"] is True
