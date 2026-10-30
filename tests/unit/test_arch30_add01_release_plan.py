import json

from Api.m5_case_runtime import checksum
from scripts import plan_specialist_program_release as release
from scripts.plan_specialist_program_release import (
    EXPECTED_CASE_IDS,
    build_admitted_materials,
    build_trace,
)


def test_add01_trace_identifies_exact_nine_cases_and_fails_closed_before_admission():
    trace = build_trace()
    assert [item["case_id"] for item in trace["cases"]] == EXPECTED_CASE_IDS
    assert {item["base_role"] for item in trace["cases"]} == {"specialist_expert"}
    assert all(len(item["db_content_checksum"]) == 64 for item in trace["cases"])
    assert trace["sales_semantics"] == "professional_example_not_base_role"
    assert trace["assessment_admitted"] is False
    assert trace["release_gate"]["code"] == "SPECIALIST_NINE_CASE_ASSESSMENT_ADMISSION_REQUIRED"


def test_owner_decision_builds_frozen_release_snapshot_from_existing_pass_evidence():
    package, runtime, evidence = build_admitted_materials(
        "owner_decision_2026-10-30_specialist_cases"
    )
    assert {case["status"] for case in package["cases"]} == {"FROZEN"}
    assert {case["author_case"]["Status"] for case in package["cases"]} == {"FROZEN"}
    assert set(evidence) == {"case_format", "case_dialogue", "assessment_situation"}
    for case in package["cases"]:
        binding = runtime["bindings"]["case_bindings"][case["case_id"]]
        assert binding["case_checksum"] == checksum(case)


def test_publish_cli_result_has_no_circular_source_trace(monkeypatch, capsys):
    def fake_publish(trace, **_kwargs):
        return {"source_trace": trace, "catalog": {"catalog_db_id": 7}}

    monkeypatch.setattr(release, "publish_admitted_catalog", fake_publish)
    monkeypatch.setattr(
        "sys.argv",
        [
            "plan_specialist_program_release.py",
            "--publish-admitted-catalog",
            "--published-by",
            "4",
            "--decision-basis",
            "owner-approved",
        ],
    )

    assert release.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["database"]["catalog"]["catalog_db_id"] == 7
    assert result["database"]["source_trace"]["package"] == result["package"]
