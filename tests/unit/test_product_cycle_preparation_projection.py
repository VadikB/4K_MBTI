from Api.product_cycle_preparation_queue import public_operation


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
