import json
from pathlib import Path
from types import SimpleNamespace

from Api import m5_functional_generation_service as functional_service
from scripts.build_arch_a06_acceptance_manifest import build_manifest
from scripts.run_functional_personalization_matrix import deterministic_checks, load_inputs


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "tests/fixtures/arch_a06/acceptance-matrix-v1.json"


def test_a06_matrix_is_exact_case_function_cartesian_product():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    rows = matrix["rows"]
    cases = {f"CASE.SPEC.{number:02d}" for number in range(1, 10)}
    functions = {"sales", "hr", "it_ops"}

    assert matrix["synthetic_test_data"] is True
    assert matrix["default_status"] == "NOT_RUN"
    assert len(rows) == 27
    assert len({row["id"] for row in rows}) == 27
    assert {(row["case_id"], row["function"]) for row in rows} == {
        (case_id, function) for case_id in cases for function in functions
    }
    assert set(matrix["functions"]) == functions


def test_a06_matrix_does_not_promote_historical_or_controlled_evidence():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))

    assert matrix["required_evidence"] == [
        "generation", "tester", "admission", "http_runtime", "m6", "m8",
    ]
    assert {"historical_27_profile_matrix", "controlled_adapter", "document_qa"} <= set(
        matrix["not_proved_by"]
    )


def test_a06_manifest_keeps_new_cartesian_rows_not_run():
    manifest = build_manifest(commit="a" * 40, application_version="2.0.23")

    assert manifest["counts"] == {"total": 27, "PASS": 0, "NOT_RUN": 27}
    assert all(row["status"] == "NOT_RUN" for row in manifest["rows"])
    assert all(all(value is None for value in row["evidence"].values()) for row in manifest["rows"])
    assert all(row["historical_comparison"] for row in manifest["rows"])
    assert {item["scope"] for row in manifest["rows"]
            for item in row["historical_comparison"]} == {"historical_profile_matrix_only"}
    assert {row["contract_checks"]["http_preparation_safe_projection"]["status"]
            for row in manifest["rows"]} == {"PASS"}
    assert all(row["evidence"]["http_runtime"] is None for row in manifest["rows"])


def test_a06_all_case_function_profiles_build_valid_author_snapshots():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))

    for row in matrix["rows"]:
        function = matrix["functions"][row["function"]]
        source_row = {
            "TestID": row["id"],
            "CaseID": row["case_id"],
            "BaseRole": "specialist_expert",
            "Профессиональный контекст": function["label"],
            "Подтверждённая для учебного теста деятельность": function["activity"],
            "Возможное отображение": function["authority"],
            "Данные": "SYNTHETIC_TEST_PROFILE; ARCH-A06; не реальный пользователь",
        }
        inputs = load_inputs(source_row)
        validation = deterministic_checks(inputs, inputs["author_as_example"])

        assert validation["status"] == "PASS", (row["id"], validation)
        assert inputs["profile"]["synthetic_test_data"] is True
        assert inputs["profile"]["source"]["test_id"] == row["id"]
        assert inputs["profile"]["role_profile"]["position_or_status"] == function["label"]
        assert inputs["author_as_example"]["CaseID"] == row["case_id"]


class _ControlledFunctionalGateway:
    enabled = True

    def chat_with_trace(self, messages, **kwargs):
        payload = json.loads(next(
            item["content"] for item in reversed(messages) if item["role"] == "user"
        ))
        if ":generation:" in kwargs["routing_key"]:
            content = json.dumps(payload["author_as_example"], ensure_ascii=False)
        else:
            required = ((payload.get("applicability_plan") or {}).get("required_checks")
                        or payload["protected_checks"])
            content = json.dumps({"checks": [{
                "check_id": item["check_id"],
                "status": "PASS",
                "reason": "controlled A06 contract fixture",
                "findings": [],
                "adversarial_review": {
                    "candidate_conflicts": [],
                    "resolution": "controlled fixture",
                },
            } for item in required]}, ensure_ascii=False)
        return SimpleNamespace(
            content=content,
            sent={"parameters": kwargs},
            provider={"finish_reason": "stop", "request_id": kwargs["routing_key"]},
        )


def test_a06_controlled_generation_tester_admission_compiles_all_27_rows():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    traces = set()
    candidates = set()

    for row in matrix["rows"]:
        function = matrix["functions"][row["function"]]
        source_row = {
            "TestID": row["id"],
            "CaseID": row["case_id"],
            "BaseRole": "specialist_expert",
            "Профессиональный контекст": function["label"],
            "Подтверждённая для учебного теста деятельность": function["activity"],
            "Возможное отображение": function["authority"],
            "Данные": "SYNTHETIC_TEST_PROFILE; ARCH-A06; controlled",
        }
        inputs = load_inputs(source_row)
        snapshot = functional_service.build_input_snapshot(
            case_id=row["case_id"], profile=inputs["profile"],
            operation_id=row["id"], synthetic=True,
            profile_checksum=inputs["profile"]["checksum"],
        )
        prepared = functional_service.prepare(snapshot, _ControlledFunctionalGateway())
        trace = functional_service.build_persistence_trace(snapshot, prepared)

        assert prepared["admitted_for_participant"] is True, row["id"]
        assert prepared["tester"]["aggregation"]["status"] == "PASS", row["id"]
        assert prepared["compiled_case"]["case_id"] == row["case_id"]
        assert trace["source_snapshot"]["profile_checksum"] == inputs["profile"]["checksum"]
        traces.add(trace["input_snapshot_checksum"])
        candidates.add((row["case_id"], trace["candidate_checksum"]))

    assert len(traces) == 27
    assert len(candidates) == 9
