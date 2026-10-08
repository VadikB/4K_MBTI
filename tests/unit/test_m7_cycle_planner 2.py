import hashlib
import json
from pathlib import Path

import pytest

from Api.m7_planning_package import PACKAGE, load_rules, methodology_targets

pytestmark=pytest.mark.unit


def test_planning_artifact_and_full_m2_target_selection():
    rules=load_rules()
    assert rules["algorithm_version"]=="m7-greedy-coverage/1"
    assert rules["duration_estimate"]=="planned_max_minutes"
    all_targets=methodology_targets(["K1","K2","K3","K4"])
    assert {x["skill_id"].split('.')[0] for x in all_targets}=={"K1","K2","K3","K4"}
    assert len(all_targets)==len({x["indicator_id"] for x in all_targets})
    k1=methodology_targets(["K1"])
    assert k1 and all(x["indicator_id"].startswith("K1.") for x in k1)
    manifest=json.loads((PACKAGE/"manifest.json").read_text())
    assert manifest["artifacts"][0]["sha256"]==hashlib.sha256((PACKAGE/"rules.json").read_bytes()).hexdigest()
