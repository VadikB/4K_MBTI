"""Bind the observed late-material omission to both independent reviews."""
import json

import pytest

from Api import m5_functional_generation_service as service
from Api.cycle_execution_manifest import M5_BATTERY_PILOT_REVIEW_PACKAGES, ROOT
from tests.unit.test_m5_battery_v06_profile_fit import PROFILE, RULES, cases
from tests.unit.test_m5_pilot_review import PilotGateway


pytestmark = pytest.mark.unit
CHECK = "invariant:CASE.SPEC.03.I05"
M04_PATH = "candidate_as/Материалы/M04/Текст"
PROVIDER_M04 = ("Уточнение влияет на первую профильную часть C1 (пересчёт в новой единице) и на актуальность свода C2. "
                "Для проверки C3 уточнение не требуется.")


class ArchivedM04Gateway(PilotGateway):
    def chat_with_trace(self, messages, **kwargs):
        response = super().chat_with_trace(messages, **kwargs)
        if ":generation:" in kwargs["routing_key"]:
            candidate = json.loads(response.content)
            next(row for row in candidate["Материалы"] if row["MaterialID"] == "M04")["Текст"] = PROVIDER_M04
            response.content = json.dumps(candidate, ensure_ascii=False)
        return response

    def review_response(self, routing, payload, checks):
        definitions = ((payload.get("applicability_plan") or {}).get("required_checks") or payload["protected_checks"])
        criterion = next((row for row in definitions if row["check_id"] == CHECK), None)
        if criterion and criterion["requirement"].get("case_content"):
            assert "отдельно для проверки C1 и отдельно для независимой проверки C3" in criterion["requirement"]["case_content"]
            assert any(row["pointer"].endswith("17.2 Материалы и исходная доступность/4")
                       for row in criterion["source_ref"]["supplemental_locations"])
            assert next(row for row in payload["candidate_as"]["Материалы"] if row["MaterialID"] == "M04")["Текст"] == PROVIDER_M04
            row = next(item for item in checks if item["check_id"] == CHECK)
            reason = "M04 явно оставляет проверку C3 без зависимости от изменившегося входа."
            row.update(status="FAIL", reason=reason, evidence_paths=[M04_PATH], findings=[{
                "code": "M04_C3_DEPENDENCY_MISSING", "severity": "blocking", "paths": [M04_PATH],
                "reason": reason, "requirement_ref": CHECK,
            }])
        return super().review_response(routing, payload, checks)


@pytest.mark.parametrize("version,status", [("1.10.2", "PASS"), ("1.10.3", "FAIL")])
def test_late_material_dependency_is_protected_without_early_delivery(version, status):
    snapshot = service.build_passport_snapshot(
        case_version=cases()["CASE.SPEC.03"], profile=PROFILE, operation_id="late-material-regression", synthetic=True,
        as_package=ROOT / M5_BATTERY_PILOT_REVIEW_PACKAGES["7.0.0"], battery_scenario_package=RULES.with_name(version),
    )
    design = snapshot["battery_scenario"]
    assert "M04" not in design["start_ids"]
    assert all("M04" not in role["known_material_ids"] for role in design["roles"].values())
    update = next(rule for rule in design["events"] if rule["id"] == "E01_UPDATE")
    assert (update["delivery_id"], update["speaker_ids"], update["audience"]) == ("M04", ["C2"], "assessee")
    gateway = ArchivedM04Gateway()
    generation = service.generate(snapshot, gateway)
    reviewed = service.test_candidate(snapshot, generation, gateway)
    assert reviewed["aggregation"]["status"] == status
    for role in ("tester", "challenger"):
        result = next(item for item in reviewed["independent_checks"][role] if item["check_id"] == CHECK)
        assert result["status"] == status
        if status == "FAIL":
            assert result["findings"][0]["code"] == "M04_C3_DEPENDENCY_MISSING"
