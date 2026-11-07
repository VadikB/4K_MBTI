import pytest

from Api.product_cycle_preparation_queue import latest_scope_operation, needs_functional_generation, public_operation


def test_latest_scope_operation_keeps_safe_terminal_reason_after_reload() -> None:
    class Result:
        def __init__(self, row):
            self.row = row

        def fetchone(self):
            return self.row

    class Connection:
        def execute(self, query, params=None):
            if "to_regclass" in query:
                return Result({"relation": "product_cycle_preparation_operations"})
            row = {"operation_id": "operation-specialist", "status": "failed"}
            if "error_message" in query.split("FROM product_cycle_preparation_operations")[0]:
                row["error_message"] = "M7_NO_ADMISSIBLE_CASE: private diagnostic"
            return Result(row)

    operation = latest_scope_operation(
        Connection(), user_id=7, profile_id=12, assignment_ref="synthetic-assignment",
        questionnaire_revision_id=1,
    )
    assert operation["error"]["code"] == "ASSESSMENT_CATALOG_NO_ADMISSIBLE_SPECIALIST_CASE"
    assert "private diagnostic" not in str(operation)


def test_public_operation_whitelists_each_status() -> None:
    common = {
        "operation_id": "operation-01",
        "attempts": 2,
        "user_id": 7,
        "result_json": {"generated": {"candidate_as": "closed"}},
        "error_code": "ValueError",
        "error_message": "provider secret",
    }

    assert public_operation({**common, "status": "queued"}) == {
        "operation_id": "operation-01",
        "status": "queued",
    }
    assert public_operation({**common, "status": "running"}) == {
        "operation_id": "operation-01",
        "status": "running",
    }
    assert public_operation({**common, "status": "failed"}) == {
        "operation_id": "operation-01",
        "status": "failed",
        "error": {
            "code": "ASSESSMENT_CYCLE_PREPARATION_FAILED",
            "message": "Не удалось подготовить оценочный цикл. Повторите попытку.",
        },
    }


def test_public_operation_keeps_only_committed_participant_result() -> None:
    result = {"plan": {"cycle_id": "cycle-01"}, "runtime": {"status": "prepared"}}
    assert public_operation({
        "operation_id": "operation-02",
        "status": "completed",
        "result_json": result,
        "error_message": "must not be exposed",
    }) == {
        "operation_id": "operation-02",
        "status": "completed",
        "result": result,
    }


def test_public_operation_explains_missing_admitted_specialist_case_without_internal_details() -> None:
    value = public_operation({
        "operation_id": "operation-specialist",
        "status": "failed",
        "error_message": "M7_NO_ADMISSIBLE_CASE: internal diagnostic",
    })
    assert value["error"]["code"] == "ASSESSMENT_CATALOG_NO_ADMISSIBLE_SPECIALIST_CASE"
    assert "Специалист" in value["error"]["message"]
    assert "internal diagnostic" not in value["error"]["message"]


@pytest.mark.parametrize(
    "status",
    ["WAITING_CURRENT_AS", "OUT_OF_TIME", "COLLECTION_CLOSED", "NO_ADMISSIBLE_CASE"],
)
def test_functional_generation_is_skipped_for_normal_nonselected_decisions(status: str) -> None:
    assert needs_functional_generation(
        functional=True,
        decision={"status": status, "explanation": {"code": f"M7_{status}"}},
    ) is False


def test_functional_generation_runs_only_for_unassigned_selected_decision() -> None:
    selected = {"status": "SELECTED", "assigned_as_db_id": None}
    assert needs_functional_generation(functional=True, decision=selected) is True
    assert needs_functional_generation(
        functional=True,
        decision={**selected, "assigned_as_db_id": 42},
    ) is False
    assert needs_functional_generation(functional=False, decision=selected) is False
