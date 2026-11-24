"""Catalog release and immutable generation bindings in an isolated database."""
import json

import pytest

from Api.cycle_execution_manifest import M5_BATTERY_PILOT_REVIEW_PACKAGE, ROOT
from Api.m5_battery_contract import RULE_PACKAGE, load_scenario
from Api.m5_case_runtime import checksum
from Api.m5_catalog_integrity import case_admission
from Api.m5_functional_generation_service import build_passport_snapshot, prepare
from Api.m5_passport_generation import read_as_package
from scripts.plan_specialist_program_release import (
    ADMISSION_EVIDENCE, BATTERY_PACKAGE, BATTERY_RUNTIME, build_trace, publish_admitted_catalog,
)
from tests.integration.test_m5_battery_bank_db import install_battery
from tests.integration.test_m10_product_path_db import product_db
from tests.unit.test_m5_pilot_review import PilotGateway

pytestmark = pytest.mark.integration


def test_approved_battery_releases_all_nine_without_changing_qa_sources(product_db, monkeypatch, tmp_path):
    monkeypatch.setattr("Api.database.get_connection", product_db)
    with product_db() as connection:
        old_qa = install_battery(connection)
        connection.commit()
    bank = json.loads((BATTERY_PACKAGE / "case-package.json").read_text())
    review_path = ROOT / M5_BATTERY_PILOT_REVIEW_PACKAGE
    _, contract_ref, review_refs = read_as_package(review_path)
    source = build_trace(BATTERY_PACKAGE, BATTERY_RUNTIME)
    proof_path = tmp_path / "synthetic-reviewed-evidence.json"
    proof = {
        "human_review_ref": "SYNTHETIC test boundary only",
        "as_contract_ref": bank["as_contract_ref"],
        "prepared_as_contract_ref": contract_ref,
        "review_package": review_refs["protocol_package"],
        "scenario_ref": load_scenario(bank["cases"][0], ROOT / RULE_PACKAGE)["ref"],
        "runtime_rule_ref": {key: source["runtime"][key] for key in ("id", "version", "manifest_checksum")},
        "scopes": dict.fromkeys(ADMISSION_EVIDENCE, "PASS"),
        "cases": {case["case_id"]: checksum(case) for case in bank["cases"]},
    }

    def publish(evidence_path):
        return publish_admitted_catalog(
            source, published_by=99, decision_basis="Isolated release contract test",
            catalog_id="synthetic-battery", catalog_version="1.3", idempotency_key="battery-pilot-05",
            organization_id=10, package_dir=BATTERY_PACKAGE, runtime_dir=BATTERY_RUNTIME,
            evidence_path=evidence_path,
        )

    with pytest.raises(ValueError, match="ASSESSMENT_EVIDENCE_REQUIRED"):
        publish(None)
    proof_path.write_text(json.dumps({**proof, "review_package": {"version": "wrong"}}))
    with pytest.raises(ValueError, match="PILOT_REVIEW_EVIDENCE_MISMATCH"):
        publish(proof_path)
    proof_path.write_text(json.dumps(proof))
    released = publish(proof_path)
    replay = publish(proof_path)
    assert replay["catalog_readback"] == released["catalog_readback"]
    assert not replay["import"]["created"] and not replay["runtime"]["created"] and replay["catalog"]["idempotent"]
    assert released["catalog_readback"]["manifest"]["battery_pilot"] is True
    assert {row["status"] for row in old_qa["readback"]["cases"]} == {"WORKING"}
    assert {row["status"] for row in released["readback"]["cases"]} == {"FROZEN"}
    assert released["readback"]["package"]["package_json"]["source_status"] == "WORKING"
    assert len(released["readback"]["cases"]) == 9
    with product_db() as connection:
        catalog_db_id = released["catalog"]["catalog_db_id"]
        for source_case, released_case in zip(bank["cases"], released["readback"]["cases"], strict=True):
            admission = case_admission(connection, case_version_id=released_case["id"],
                                       usage_scope="assessment", catalog_db_id=catalog_db_id)
            value = admission["case"]["content_json"]
            assert admission["admitted"]
            assert value["passport_source"] == source_case["passport_source"]
            assert value["version"] == source_case["version"] + "-pilot.1"
            frozen = build_passport_snapshot(
                case_version=value, profile={"user_context": {"regular_tasks": ["Рабочая аналитика"],
                    "additional_information": {"professional_recommendation": {"confirmed": True, "basis": "Тест"}}}},
                operation_id=f"pilot-05-{value['case_id']}", battery_pilot=True, as_package=review_path,
                battery_scenario_package=ROOT / RULE_PACKAGE, case_version_checksum=released_case["content_checksum"],
            )
            assert frozen["applicability_plan"]["case_ref"]["case_version"] == value["version"]
            prepared = prepare(frozen, PilotGateway())
            assert prepared["admitted_for_participant"]
            assert prepared["compiled_case"]["version"] == value["version"]
        assert install_battery(connection)["catalog_readback"] == old_qa["catalog_readback"]
