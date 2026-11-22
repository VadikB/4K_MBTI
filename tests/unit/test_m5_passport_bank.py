import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from Api import m5_functional_generation_service as service
from Api.cycle_execution_manifest import PROJECT_ROLE_PROMPT, ROOT
from Api.m5_passport_generation import BANK_PACKAGE, provider_basis
from Api.m5_package import digest
from scripts.build_m5_passport_bank import build_bank
from tests.passport_as_fixture import synthetic_as


def _raw_cases():
    return json.loads((BANK_PACKAGE / "case-package.json").read_bytes())["cases"]


@pytest.fixture
def passport_source(tmp_path):
    index = json.loads((BANK_PACKAGE / "passport-index.json").read_bytes())
    root = tmp_path / "input"
    (root / "sources").mkdir(parents=True)
    for row in index["cases"]:
        (root / row["path"]).write_bytes((BANK_PACKAGE / row["path"]).read_bytes())
    (root / "passport-index.json").write_text(json.dumps(index))
    return root


def test_bank_build_ignores_present_old_catalog_and_diagnoses_missing_passport_link(passport_source, tmp_path):
    bank, rules = tmp_path / "bank", tmp_path / "rules"
    initial = build_bank(passport_source, bank, rules)
    assert initial["case_count"] == 9 and initial["target_count"] == 55
    assert (bank / "case-package.json").read_bytes() == (BANK_PACKAGE / "case-package.json").read_bytes()
    (passport_source / "04_as").mkdir()
    (passport_source / "04_as/AS_SPEC_02_FUNCTIONAL_DONT_READ.json").write_text("old sentinel")
    assert build_bank(passport_source, bank, rules) == initial
    index_file = passport_source / "passport-index.json"
    index = json.loads(index_file.read_text())
    entry = index["cases"][1]
    path = passport_source / entry["path"]
    case = json.loads(path.read_bytes())
    case["Паспорт"]["22 IndicatorIDs"]["Проектные условия"].pop()
    path.write_text(json.dumps(case))
    entry["sha256"] = digest(path.read_bytes())
    index_file.write_text(json.dumps(index))
    with pytest.raises(ValueError, match=r"CASE\.SPEC\.02:v0\.6:22/Точный перечень→Проектные условия"):
        build_bank(passport_source, tmp_path / "invalid", tmp_path / "invalid-rules")


class CaptureGateway:
    def __init__(self, mode):
        self.mode = mode
        self.calls = []

    def chat_with_trace(self, messages, **kwargs):
        payload = json.loads(messages[-1]["content"])
        routing = kwargs["routing_key"]
        self.calls.append((routing, deepcopy(messages), payload))
        if ":generation:" in routing:
            result = synthetic_as(payload)
            if self.mode == "repair" and ":repair:" not in routing:
                result["IndicatorObservability"][0]["material_refs"] = ["unavailable"]
        else:
            checks = (payload.get("applicability_plan") or {}).get("required_checks") or payload["protected_checks"]
            result = {"candidate_checksum": payload["candidate_checksum"], "checks": [{
                "check_id": check["check_id"], "status": "PASS", "reason": "isolated fixture",
                "evidence_paths": [], "findings": [],
                "adversarial_review": {"candidate_conflicts": [], "resolution": "fixture"},
            } for check in checks]}
            if self.mode == "protocol" and ":challenger:" in routing:
                result["candidate_checksum"] = "wrong-candidate"
        return SimpleNamespace(content=json.dumps(result, ensure_ascii=False), sent={}, provider={"finish_reason": "stop"})


def test_frozen_educational_role_reaches_original_and_repair_generation():
    case = _raw_cases()[1]
    project_role = {
        "code": "training_role", "version": 2, "checksum": "role-checksum",
        "snapshot_checksum": "assignment-snapshot-checksum", "interactions": ["Тестовый куратор", "Тестовый коллега"],
    }
    snapshot = service.build_passport_snapshot(
        case_version=case, profile={}, operation_id="m5-educational",
        project_role=project_role, project_role_prompt=ROOT / PROJECT_ROLE_PROMPT,
    )
    previous = service.build_passport_snapshot(case_version=case, profile={}, operation_id="m5-previous")
    assert "project_role" not in provider_basis(previous)
    expected = {"code": project_role["code"], "interactions": list(project_role["interactions"])}
    project_role["interactions"].append("Позднее изменение")
    gateway = CaptureGateway("repair")
    result = service.prepare(snapshot, gateway)
    calls = [(messages, payload) for routing, messages, payload in gateway.calls if ":generation:" in routing]
    assert len(calls) == 2 and result["admitted_for_participant"]
    for messages, payload in calls:
        assert payload["project_role"] == expected
        assert payload["case"] == previous["case"]
        assert payload["normative_indicator_targets"] == previous["case_version"]["indicator_targets"]
        assert (ROOT / PROJECT_ROLE_PROMPT).read_text() in messages[0]["content"]
    trace = service.build_persistence_trace(snapshot, result)
    assert trace["source_snapshot"]["refs"]["project_role"] == {
        key: project_role[key] for key in ("code", "version", "checksum", "snapshot_checksum")
    }


@pytest.mark.parametrize(("number", "count", "mode"), [(2, 33, "pass"), (3, 31, "repair"), (2, 33, "protocol")])
def test_passport_provider_inputs_bind_exact_checks_and_candidate(number, count, mode):
    case = _raw_cases()[number - 1]
    raw = json.loads((BANK_PACKAGE / case["passport_source"]["file"]).read_bytes())
    # Simulate the historical envelope and verify that only its normative passport is projected.
    legacy = {**case, "schema_version": 3, "author_case_source": case["passport_source"],
              "author_assessment_situation": {"sentinel": "DISALLOWED_OLD_EXAMPLE"}}
    legacy["passport"] = deepcopy(case["passport"])
    legacy["passport"]["18 Правила персонализации и ролевой адаптации"]["Профессиональные примеры"] = "DISALLOWED_ILLUSTRATION"
    profile = {"user_context": {"full_name": "DISALLOWED_IDENTITY", "regular_tasks": "тестовые задачи"},
               "role_profile": {"description": {"examples": "DISALLOWED_ROLE_EXAMPLES"}},
               "organization_context": {"name": "DISALLOWED_ORGANIZATION_NAME", "industry": "тестовая отрасль"}}
    new_snapshot = service.build_passport_snapshot(case_version=case, profile=profile, operation_id="m5-new")
    snapshot = service.build_passport_snapshot(case_version=legacy, profile=profile, operation_id="m5-old")
    assert provider_basis(new_snapshot) == provider_basis(snapshot)
    gateway = CaptureGateway(mode)
    result = service.prepare(snapshot, gateway)
    assert result["tester"]["aggregation"]["status"] == ("INCOMPLETE" if mode == "protocol" else "PASS")
    assert result["admitted_for_participant"] is (mode != "protocol")
    assert bool(result["repair"]) is (mode == "repair")
    expected = service.build_applicability_plan(raw)["required_checks"]
    expected_ids = [item["check_id"] for item in expected]
    assert len(expected_ids) == count
    assert [item["check_id"] for item in result["tester"]["checks"] if item["status"] != "NOT_APPLICABLE"] == expected_ids
    final_checksum = result["candidate_checksum"]
    assert [item["check_id"] for route, _, payload in gateway.calls
            if ":tester:" in route and payload["candidate_checksum"] == final_checksum
            for item in payload["applicability_plan"]["required_checks"]] == expected_ids
    for route, messages, payload in gateway.calls:
        serialized = json.dumps(messages, ensure_ascii=False)
        assert not any(key in serialized for key in (
            "author_as_example", "author_assessment_situation", "04_as", "DISALLOWED_",
        ))
        if ":tester:" in route or ":challenger:" in route:
            assert payload["candidate_checksum"] == service.checksum(payload["candidate_as"])
        if ":repair:" in route:
            assert payload["rejected_candidate_as"]["IndicatorObservability"][0]["material_refs"] == ["unavailable"]
            assert any("/material_refs" in item["path"] for item in payload["validation_errors"])
    if mode != "protocol":
        trace = service.build_persistence_trace(snapshot, result)
        assert trace["source_snapshot"]["refs"]["as_contract"] == case["as_contract_ref"]
        assert "author_as_example" not in json.dumps(trace, ensure_ascii=False)
        assert result["compiled_case"]["indicator_targets"][0]["material_refs"]
