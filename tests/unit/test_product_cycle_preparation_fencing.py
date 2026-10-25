from __future__ import annotations

from uuid import uuid4

import pytest

from Api.product_cycle_preparation_queue import ProductCyclePreparationQueue


class _Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Connection:
    def __init__(self, row):
        self.row = row
        self.sql = []

    def execute(self, sql, params):
        self.sql.append((" ".join(sql.split()), params))
        return _Result(self.row)


@pytest.mark.unit
def test_current_attempt_accepts_matching_fence_and_locks_when_requested():
    token = uuid4()
    connection = _Connection({"status": "running", "attempt_token": token})

    ProductCyclePreparationQueue._assert_current_attempt(
        connection,
        {"id": 7, "attempt_token": token},
        lock=True,
    )

    assert connection.sql == [(
        "SELECT status,attempt_token FROM product_cycle_preparation_operations WHERE id=%s FOR UPDATE",
        (7,),
    )]


@pytest.mark.unit
@pytest.mark.parametrize(
    "row",
    [
        None,
        {"status": "queued", "attempt_token": None},
        {"status": "running", "attempt_token": uuid4()},
    ],
)
def test_stale_attempt_is_rejected_before_subject_commit(row):
    with pytest.raises(RuntimeError, match="ATTEMPT_STALE"):
        ProductCyclePreparationQueue._assert_current_attempt(
            _Connection(row),
            {"id": 7, "attempt_token": uuid4()},
        )
