"""Catalog release and immutable generation bindings in an isolated database."""
import json

import pytest

from Api.cycle_execution_manifest import (
    M5_BATTERY_PILOT_REVIEW_PACKAGE, ROOT, build_manifest, resolve_dependency,
)
from Api.m5_battery_contract import RULE_PACKAGE, load_scenario
from Api.m5_case_runtime import checksum
from Api.m5_catalog_integrity import case_admission, resolve_configuration_catalog
from Api.m5_functional_generation_service import build_passport_snapshot, prepare
from Api.m5_passport_generation import read_as_package
from scripts.plan_specialist_program_release import (
    ADMISSION_EVIDENCE, BATTERY_PACKAGE, BATTERY_RUNTIME, build_trace, publish_admitted_catalog,
)
from tests.integration.test_m5_battery_bank_db import install_battery
from tests.integration.test_m10_product_path_db import product_db
from tests.unit.test_m5_pilot_review import PilotGateway, V6_PACKAGE

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

    def publish(evidence_path, *, version="1.3"):
        return publish_admitted_catalog(
            source, published_by=99, decision_basis="Isolated release contract test",
            catalog_id="synthetic-battery", catalog_version=version, idempotency_key=f"battery-pilot-05-{version}",
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

    _, _, v6_refs = read_as_package(V6_PACKAGE)
    v6_ref = v6_refs["protocol_package"]
    assert "review_package" not in released["catalog_readback"]["manifest"]

    def freeze_config(connection, catalog):
        connection.execute("UPDATE assessment_configurations SET catalog_version_id=%s", (catalog["catalog_db_id"],))
        ref = resolve_configuration_catalog(connection, configuration_id=1, usage_scope="assessment")
        return build_manifest(
            profile_ref={"id": "synthetic", "version": "1", "checksum": "synthetic"},
            selected_role_ref={"id": "specialist_expert", "version": "1", "checksum": "synthetic"},
            target_set_checksum="synthetic", parameter_sources={}, catalog_ref=ref,
        )

    with product_db() as connection:
        connection.execute(
            "ALTER TABLE assessment_configurations ADD COLUMN catalog_version_id BIGINT REFERENCES m5_catalogs(id)"
        )
        old_cycle = freeze_config(connection, released["catalog"])
        connection.commit()

    proof_path.write_text(json.dumps({**proof, "review_package": {**v6_ref, "checksum": "0" * 64}}))
    with pytest.raises(ValueError, match="PILOT_REVIEW_EVIDENCE_MISMATCH"):
        publish(proof_path, version="1.4")
    proof_path.write_text(json.dumps({**proof, "review_package": v6_ref}))
    revised = publish(proof_path, version="1.4")
    assert revised["catalog_readback"]["manifest"]["review_package"] == v6_ref
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        publish(proof_path)
    with product_db() as connection:
        new_cycle = freeze_config(connection, revised["catalog"])
    assert resolve_dependency(*old_cycle, "m5_functional_as") == review_path
    selected = resolve_dependency(*new_cycle, "m5_functional_as")
    assert selected == V6_PACKAGE
    value = next(row for row in revised["readback"]["cases"] if row["case_id"] == "CASE.SPEC.04")
    with product_db() as connection:
        persisted = case_admission(connection, case_version_id=value["id"], usage_scope="assessment",
                                   catalog_db_id=revised["catalog"]["catalog_db_id"])["case"]["content_json"]
    frozen = build_passport_snapshot(
        case_version=persisted, profile={"user_context": {"regular_tasks": ["Рабочая аналитика"]}},
        operation_id="pilot-v6-SPEC04", battery_pilot=True, as_package=selected,
        battery_scenario_package=ROOT / RULE_PACKAGE, case_version_checksum=value["content_checksum"],
    )
    gateway = PilotGateway()
    result = prepare(frozen, gateway)
    assert result["admitted_for_participant"]
    assert result["tester"]["protocol"]["version"] == "3.2.0"
    assert all(payload["review_dispatch"]["check_ids"] for _, _, payload in gateway.calls
               if "review_dispatch" in payload)
