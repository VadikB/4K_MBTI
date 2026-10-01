import json
from pathlib import Path

import pytest

from Api.m5_scenario_runtime import model_check_case03

pytestmark = pytest.mark.unit
RULES = json.loads((Path(__file__).parents[2] / "assessment_definitions/cases/competencies_4k/m5-1.1-v0.1-authoring/execution-rules.json").read_text())["model_checks"]["CASE-TDISC-03"]


def test_case03_model_check_is_deterministic_and_preserves_authorship():
    scheme = {"routes": {"A": "catalog", "B": "defer", "C": "unique", "D": "defer", "E": "reject_for_input", "F": "catalog"}}
    first = model_check_case03(scheme, rules=RULES, initiated_by="assessee", scheme_authored_by="assessee")
    second = model_check_case03(scheme, rules=RULES, initiated_by="assessee", scheme_authored_by="assessee")
    assert first == second
    assert first["status"] == "COMPLETED"
    assert first["results"]["A"]["finish"] == "2026-01-01T09:30"
    assert first["results"]["C"]["finish"] == "2026-01-01T11:30"
    assert first["initiated_by"] == first["scheme_authored_by"] == "assessee"


def test_case03_model_check_does_not_invent_missing_route():
    result = model_check_case03({"routes": {"A": "catalog"}}, rules=RULES, initiated_by="sergey", scheme_authored_by="assessee")
    assert result == {"status": "INDETERMINATE", "reason": "ROUTE_OR_CONDITION_NOT_SPECIFIED",
                      "initiated_by": "sergey", "scheme_authored_by": "assessee", "rules_version": "0.1"}
