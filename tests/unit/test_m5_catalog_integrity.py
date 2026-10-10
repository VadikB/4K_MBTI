from __future__ import annotations

import copy

import pytest

from Api.m5_case_runtime import checksum
from Api.m5_catalog_integrity import _validate_evidence, case_admission, load_policy


CASE = {
    "id": 7,
    "package_id": 3,
    "case_id": "CASE-01",
    "case_version": "1.0",
    "status": "FROZEN",
    "base_role": "team_lead",
    "content_checksum": "a" * 64,
    "content_json": {"unresolved_decisions": []},
}


def evidence(scope: str, *, result: str = "PASS", origin: str = "human_review") -> dict:
    payload = {
        "schema_version": 1,
        "eligibility": "user_admission",
        "scope": scope,
        "result": result,
        "case_ref": {"id": "CASE-01", "version": "1.0", "checksum": "a" * 64},
        "base_role": "team_lead",
        "usage_scopes": ["assessment", "qa"],
        "origin": {"type": origin, "actor_ref": "review:synthetic-owner"},
    }
    return {"id": 1, "scope": scope, "result": result, "evidence_json": payload,
            "evidence_checksum": checksum(payload)}


def test_exact_evidence_passes_and_each_foreign_dimension_is_rejected():
    policy = load_policy()
    valid = evidence("case_format")
    assert _validate_evidence(row=valid, case=CASE, usage_scope="assessment", policy=policy) == []

    mutations = [
        ("id", "FOREIGN"),
        ("version", "2.0"),
        ("checksum", "b" * 64),
    ]
    for key, value in mutations:
        changed = copy.deepcopy(valid)
        changed["evidence_json"]["case_ref"][key] = value
        changed["evidence_checksum"] = checksum(changed["evidence_json"])
        assert any("CASE_REF_MISMATCH" in item for item in _validate_evidence(
            row=changed, case=CASE, usage_scope="assessment", policy=policy
        ))

    changed = copy.deepcopy(valid)
    changed["evidence_json"]["base_role"] = "specialist_expert"
    changed["evidence_checksum"] = checksum(changed["evidence_json"])
    assert any("BASE_ROLE_MISMATCH" in item for item in _validate_evidence(
        row=changed, case=CASE, usage_scope="assessment", policy=policy
    ))

    changed = copy.deepcopy(valid)
    changed["evidence_json"]["usage_scopes"] = ["qa"]
    changed["evidence_checksum"] = checksum(changed["evidence_json"])
    assert any("USAGE_SCOPE_MISMATCH" in item for item in _validate_evidence(
        row=changed, case=CASE, usage_scope="assessment", policy=policy
    ))

    changed = copy.deepcopy(valid)
    changed["evidence_json"]["origin"]["type"] = "fixture"
    changed["evidence_checksum"] = checksum(changed["evidence_json"])
    assert any("ORIGIN_NOT_ALLOWED" in item for item in _validate_evidence(
        row=changed, case=CASE, usage_scope="assessment", policy=policy
    ))
    assert not any("ORIGIN_NOT_ALLOWED" in item for item in _validate_evidence(
        row=changed, case=CASE, usage_scope="qa", policy=policy
    ))

    changed = copy.deepcopy(valid)
    changed["evidence_json"]["origin"]["actor_ref"] = "tampered"
    assert any("CHECKSUM_MISMATCH" in item for item in _validate_evidence(
        row=changed, case=CASE, usage_scope="assessment", policy=policy
    ))


class Result:
    def __init__(self, *, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class AdmissionConnection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params):
        if "FROM m5_case_versions WHERE id=" in sql:
            return Result(one=CASE)
        if "FROM m5_catalog_case_versions" in sql:
            return Result(one={"present": True})
        if "FROM m5_qa_evidence" in sql:
            return Result(many=self.rows)
        raise AssertionError(sql)


def test_latest_relevant_fail_wins_and_fixture_is_qa_only():
    rows = []
    for index, scope in enumerate(("case_format", "case_dialogue", "assessment_situation"), 1):
        item = evidence(scope)
        item["id"] = index
        rows.append(item)
    newer_fail = evidence("case_dialogue", result="FAIL")
    newer_fail["id"] = 99
    rows.insert(1, newer_fail)
    result = case_admission(AdmissionConnection(rows), case_version_id=7,
                            usage_scope="assessment", catalog_db_id=5)
    assert not result["admitted"]
    assert "QA_EVIDENCE_FAIL:case_dialogue" in result["reasons"]

    fixture_rows = []
    for index, scope in enumerate(("case_format", "case_dialogue", "assessment_situation"), 1):
        item = evidence(scope, origin="fixture")
        item["id"] = index
        fixture_rows.append(item)
    assert not case_admission(AdmissionConnection(fixture_rows), case_version_id=7,
                              usage_scope="assessment", catalog_db_id=5)["admitted"]
    assert case_admission(AdmissionConnection(fixture_rows), case_version_id=7,
                          usage_scope="qa", catalog_db_id=5)["admitted"]


def _complete_rows() -> list[dict]:
    rows = []
    for index, scope in enumerate(("case_format", "case_dialogue", "assessment_situation"), 1):
        item = evidence(scope)
        item["id"] = index
        rows.append(item)
    return rows


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ({"result": "FAIL"}, "QA_EVIDENCE_FAIL:case_dialogue"),
        ({"result": "NOT_RUN"}, "QA_EVIDENCE_NOT_RUN:case_dialogue"),
        ({"eligibility": "laboratory_only"}, "QA_EVIDENCE_ELIGIBILITY_MISMATCH:case_dialogue"),
        ({"version": "2.0"}, "QA_EVIDENCE_CASE_REF_MISMATCH:case_dialogue"),
        ({"checksum": "b" * 64}, "QA_EVIDENCE_CASE_REF_MISMATCH:case_dialogue"),
        ({"base_role": "specialist_expert"}, "QA_EVIDENCE_BASE_ROLE_MISMATCH:case_dialogue"),
        ({"usage_scopes": ["qa"]}, "QA_EVIDENCE_USAGE_SCOPE_MISMATCH:case_dialogue"),
        ({"origin": "fixture"}, "QA_EVIDENCE_ORIGIN_NOT_ALLOWED:case_dialogue"),
    ],
)
def test_latest_row_is_selected_before_eligibility_and_binding_validation(mutation, reason):
    rows = _complete_rows()
    newer = evidence("case_dialogue", result=mutation.get("result", "PASS"))
    newer["id"] = 99
    payload = newer["evidence_json"]
    if "eligibility" in mutation:
        payload["eligibility"] = mutation["eligibility"]
    if "version" in mutation:
        payload["case_ref"]["version"] = mutation["version"]
    if "checksum" in mutation:
        payload["case_ref"]["checksum"] = mutation["checksum"]
    if "base_role" in mutation:
        payload["base_role"] = mutation["base_role"]
    if "usage_scopes" in mutation:
        payload["usage_scopes"] = mutation["usage_scopes"]
    if "origin" in mutation:
        payload["origin"]["type"] = mutation["origin"]
    newer["evidence_checksum"] = checksum(payload)
    rows.insert(0, newer)

    result = case_admission(AdmissionConnection(rows), case_version_id=7,
                            usage_scope="assessment", catalog_db_id=5)
    assert not result["admitted"]
    assert reason in result["reasons"]
    selected = next(item for item in result["evidence_considered"]
                    if item["scope"] == "case_dialogue")
    assert selected["id"] == 99


def test_latest_valid_pass_is_admitted():
    rows = _complete_rows()
    newer = evidence("case_dialogue")
    newer["id"] = 99
    rows.insert(0, newer)
    result = case_admission(AdmissionConnection(rows), case_version_id=7,
                            usage_scope="assessment", catalog_db_id=5)
    assert result["admitted"]
    assert {item["id"] for item in result["evidence_considered"]} == {1, 3, 99}
