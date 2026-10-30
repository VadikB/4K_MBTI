from scripts.plan_specialist_program_release import EXPECTED_CASE_IDS, build_trace


def test_add01_trace_identifies_exact_nine_cases_and_fails_closed_before_admission():
    trace = build_trace()
    assert [item["case_id"] for item in trace["cases"]] == EXPECTED_CASE_IDS
    assert {item["base_role"] for item in trace["cases"]} == {"specialist_expert"}
    assert all(len(item["db_content_checksum"]) == 64 for item in trace["cases"])
    assert trace["sales_semantics"] == "professional_example_not_base_role"
    assert trace["assessment_admitted"] is False
    assert trace["release_gate"]["code"] == "SPECIALIST_NINE_CASE_ASSESSMENT_ADMISSION_REQUIRED"
