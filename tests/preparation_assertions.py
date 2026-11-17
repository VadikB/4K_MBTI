"""Operation replay checks keep persisted facts strict and validate each read time."""
from datetime import datetime
import re


def assert_same_operation_readback(current, previous):
    observation = current.get("preparation")
    earlier = previous.get("preparation")
    if observation is None or earlier is None:
        assert current == previous
        return
    read_at = datetime.fromisoformat(observation["read_at"])
    previous_read_at = datetime.fromisoformat(earlier["read_at"])
    assert read_at.tzinfo is not None and previous_read_at.tzinfo is not None
    assert read_at >= previous_read_at
    # Only a new read timestamp may differ; stages, references, results and guards stay exact.
    assert current == {**previous, "preparation": {**earlier, "read_at": observation["read_at"]}}


def assert_queued_operation(payload, operation_id, kind):
    observation = payload["preparation"]
    assert payload == {"operation_id": operation_id, "status": "queued", "preparation": observation}
    assert observation["operation_id"] == operation_id
    assert observation["kind"] == kind and observation["status"] == "queued"
    assert observation["allowed_actions"] == ["check"]
    assert re.fullmatch(r"P4K-[0-9A-F]{24}", observation["reference"])
    assert datetime.fromisoformat(observation["read_at"]).tzinfo is not None
