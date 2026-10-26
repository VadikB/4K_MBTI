from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pytest

from Api.m5_case_runtime import checksum
from Api.m5_functional_generation_service import checksum as functional_checksum
from Api.m5_scenario_runtime import _as_row
from Api.snapshot_integrity import SNAPSHOT_COMPOSITION_MISMATCH, SnapshotIntegrityError


pytestmark = pytest.mark.unit


class _Connection:
    def __init__(self, situation, dependencies):
        self.situation = situation
        self.dependencies = dependencies

    def execute(self, query, params):
        return self

    def fetchone(self):
        if not hasattr(self, "_fetched"):
            self._fetched = True
            return self.situation
        return self.dependencies


def _situation():
    as_id = uuid4()
    cycle_id = uuid4()
    session_id = uuid4()
    layers = {"author": {"checksum": "author"}, "adapted": {"checksum": "adapted"}}
    assert checksum(layers) != functional_checksum(layers)
    trace = {
        "schema_version": 3,
        "source_snapshot": {"refs": {"case": {"case_version_checksum": "source-case"}}},
        "compiled_case_checksum": "compiled-case",
        "accepted_as": {"IndicatorTargetLayers": layers},
        "indicator_target_layers": layers,
        "indicator_target_layers_checksum": functional_checksum(layers),
    }
    execution = {"ai_operations": {"functional_personalization": trace}}
    snapshot = {
        "assessment_situation_id": str(as_id),
        "cycle_ref": {"id": str(cycle_id)},
        "session_ref": {"id": str(session_id)},
        "execution_payload_ref": {"checksum": checksum(execution)},
        "case_ref": {"id": "CASE.SPEC.01", "version": "1.0", "checksum": "compiled-case"},
        "profile_ref": {"id": "assessment_personalized_profiles:1", "checksum": "profile"},
    }
    row = {
        "assessment_situation_id": as_id,
        "cycle_db_id": cycle_id,
        "session_db_id": session_id,
        "personalized_profile_id": 1,
        "case_version_id": 1,
        "snapshot_json": snapshot,
        "snapshot_checksum": checksum(snapshot),
        "execution_payload_json": execution,
    }
    dependencies = {"case_id": "CASE.SPEC.01", "case_version": "1.0", "content_checksum": "source-case", "profile_checksum": "profile"}
    return row, dependencies


def test_schema_3_functional_case_accepts_bound_layers():
    row, dependencies = _situation()
    assert _as_row(_Connection(row, dependencies), str(row["assessment_situation_id"])) is row


@pytest.mark.parametrize("tamper", ["accepted_layers", "layers_checksum", "source_case_checksum"])
def test_schema_3_functional_case_rejects_broken_binding(tamper):
    row, dependencies = _situation()
    row = deepcopy(row)
    trace = row["execution_payload_json"]["ai_operations"]["functional_personalization"]
    if tamper == "accepted_layers":
        trace["accepted_as"]["IndicatorTargetLayers"] = {"other": True}
    elif tamper == "layers_checksum":
        trace["indicator_target_layers_checksum"] = "wrong"
    else:
        trace["source_snapshot"]["refs"]["case"]["case_version_checksum"] = "wrong"
    row["snapshot_json"]["execution_payload_ref"]["checksum"] = checksum(row["execution_payload_json"])
    row["snapshot_checksum"] = checksum(row["snapshot_json"])
    with pytest.raises(SnapshotIntegrityError) as caught:
        _as_row(_Connection(row, dependencies), str(row["assessment_situation_id"]))
    assert caught.value.code == SNAPSHOT_COMPOSITION_MISMATCH
