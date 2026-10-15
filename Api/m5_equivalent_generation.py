"""Версионированная генерация эквивалентной AS без изменения Case/маршрута."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from Api.m5_case_runtime import checksum


PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "assessment_definitions/cases/competencies_4k/qa_equivalent_generation/v1"
TERMINAL_CYCLE = {"collection_closed", "calculation_pending", "calculated", "failed"}
runtime_provider = None


class EquivalentGenerationProvider(Protocol):
    def generate(self, *, input_snapshot: dict) -> dict: ...


class VariabilityContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(ge=1)
    id: str
    version: str
    status: str
    usage_scope: str
    case_id: str
    case_version: str
    allowed_paths: list[str]
    immutable_paths: list[str]
    linked_equal_paths: list[list[str]] = Field(default_factory=list)
    substantive_paths: list[str]
    min_substantive_changes: int = Field(ge=1)
    content_admission: str

    @model_validator(mode="after")
    def validate_scope(self):
        if self.status not in {"draft", "published"} or self.usage_scope not in {"qa", "assessment"}:
            raise ValueError("M5_VARIABILITY_CONTRACT_INVALID")
        if not self.allowed_paths or not self.substantive_paths:
            raise ValueError("M5_VARIABILITY_CONTRACT_INCOMPLETE")
        return self


@dataclass(frozen=True)
class ControlledEquivalentProvider:
    """Детерминированный provider только для изолированной технической приёмки."""
    candidate: dict
    provider_id: str = "controlled-equivalent-fixture"
    provider_version: str = "1"

    def generate(self, *, input_snapshot: dict) -> dict:
        return deepcopy(self.candidate)


def load_variability_package(root: Path = PACKAGE_ROOT) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    contract_bytes = (root / "contract.json").read_bytes()
    if checksum(json.loads(contract_bytes)) != manifest["artifacts"][0]["checksum"]:
        raise ValueError("M5_VARIABILITY_PACKAGE_CHECKSUM_MISMATCH")
    contract = VariabilityContract.model_validate_json(contract_bytes).model_dump()
    if (manifest["id"], manifest["version"], manifest["status"]) != (
        contract["id"], contract["version"], contract["status"]
    ):
        raise ValueError("M5_VARIABILITY_PACKAGE_REF_MISMATCH")
    return {"manifest": manifest, "contract": contract,
            "contract_checksum": checksum(contract)}


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS m5_equivalent_generation_operations (
        id UUID PRIMARY KEY,
        request_key TEXT NOT NULL,
        request_checksum TEXT NOT NULL,
        cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),
        position_id UUID NOT NULL REFERENCES m7_route_positions(id),
        expected_as_db_id BIGINT NOT NULL REFERENCES m5_assessment_situations(id),
        requested_by BIGINT NOT NULL REFERENCES users(id),
        variability_ref_json JSONB NOT NULL,
        input_json JSONB NOT NULL,
        input_checksum TEXT NOT NULL,
        provider_config_json JSONB NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending','leased','completed','failed','rejected_late')),
        lease_token UUID,
        attempt_no INTEGER NOT NULL DEFAULT 0,
        output_json JSONB,
        output_checksum TEXT,
        validation_json JSONB,
        candidate_as_db_id BIGINT REFERENCES m5_assessment_situations(id),
        error_code TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ,
        UNIQUE(cycle_db_id,request_key))""")


def _pointer(value: dict, path: str):
    current = value
    for part in path.removeprefix("/").split("/"):
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[part]
    return current


def _safe_profile(profile: dict) -> dict:
    content = profile.get("content") if isinstance(profile.get("content"), dict) else profile
    return {
        "organization_context": deepcopy(content.get("organization_context", {})),
        "role_profile": deepcopy(content.get("role_profile", profile.get("role_profile", {}))),
        "user_context": deepcopy(content.get("user_context", {})),
    }


def _changed_leaf_paths(old, new, prefix="") -> set[str]:
    if type(old) is not type(new):
        return {prefix or "/"}
    if isinstance(old, dict):
        paths = set()
        for key in set(old) | set(new):
            path = f"{prefix}/{key}"
            if key not in old or key not in new:
                paths.add(path)
            else:
                paths |= _changed_leaf_paths(old[key], new[key], path)
        return paths
    if isinstance(old, list):
        if len(old) != len(new):
            return {prefix}
        paths = set()
        for index, (left, right) in enumerate(zip(old, new)):
            paths |= _changed_leaf_paths(left, right, f"{prefix}/{index}")
        return paths
    return set() if old == new else {prefix}


def build_input_snapshot(connection, *, position: dict, old_as: dict, contract: dict,
                         operation_id: str, provider_config: dict) -> dict:
    case = connection.execute("SELECT content_json,content_checksum FROM m5_case_versions WHERE id=%s",
                              (old_as["case_version_id"],)).fetchone()
    profile = connection.execute("SELECT content_json,checksum FROM assessment_personalized_profiles WHERE id=%s",
                                 (old_as["personalized_profile_id"],)).fetchone()
    snapshot = dict(old_as["snapshot_json"])
    return {
        "schema_version": 1, "operation_id": operation_id,
        "cycle": {"id": str(old_as["cycle_db_id"]), "position_id": str(position["id"]),
                  "position_no": position["position_no"]},
        "case": deepcopy(case["content_json"]),
        "case_ref": {**snapshot["case_ref"], "content_checksum": case["content_checksum"]},
        "profile_ref": snapshot["profile_ref"], "profile_content": _safe_profile(dict(profile["content_json"])),
        "base_role": snapshot["base_role"], "indicator_targets": snapshot["indicator_targets"],
        "old_content": {"participant_payload": snapshot["participant_payload"],
                        "execution_payload": deepcopy(old_as["execution_payload_json"])},
        "variability_contract": deepcopy(contract), "provider_config": deepcopy(provider_config),
    }


def begin_generation(connection, *, cycle_id: str, position_no: int, expected_as_id: str,
                     request_key: str, requested_by: int, package: dict,
                     provider_config: dict) -> dict:
    contract = VariabilityContract.model_validate(package["contract"]).model_dump()
    if set(provider_config) - {"id", "version", "checksum", "prompt_ref"} or not all(
        provider_config.get(key) for key in ("id", "version", "checksum")
    ):
        raise ValueError("M5_EQUIVALENT_PROVIDER_CONFIG_REF_INVALID")
    cycle = connection.execute("SELECT * FROM m5_cycles WHERE cycle_id=%s FOR UPDATE", (UUID(cycle_id),)).fetchone()
    if not cycle or int(cycle["owner_user_id"]) != int(requested_by):
        raise ValueError("M7_CYCLE_NOT_FOUND")
    if cycle["status"] in TERMINAL_CYCLE:
        raise ValueError("M5_EQUIVALENT_OPERATION_NOT_APPLICABLE")
    position = connection.execute("SELECT * FROM m7_route_positions WHERE cycle_db_id=%s AND position_no=%s FOR UPDATE",
                                  (cycle["id"], position_no)).fetchone()
    if not position:
        raise ValueError("M7_ROUTE_POSITION_NOT_FOUND")
    old = connection.execute("SELECT * FROM m5_assessment_situations WHERE id=%s FOR UPDATE",
                             (position["current_as_db_id"],)).fetchone()
    if str(old["assessment_situation_id"]) != expected_as_id or old["status"] not in {"active", "paused"}:
        raise ValueError("M7_REPLACEMENT_STALE_CURRENT_AS")
    if (contract["case_id"], contract["case_version"], contract["usage_scope"]) != (
        position["case_id"], position["case_version"], cycle["usage_scope"]
    ):
        raise ValueError("M5_VARIABILITY_CONTRACT_NOT_APPLICABLE")
    variability_ref = {"id": contract["id"], "version": contract["version"],
                       "checksum": package["contract_checksum"]}
    request = {"position_no": position_no, "expected_as_id": expected_as_id,
               "variability_ref": variability_ref, "provider_config": provider_config}
    request_checksum = checksum(request)
    prior = connection.execute("SELECT * FROM m5_equivalent_generation_operations WHERE cycle_db_id=%s AND request_key=%s",
                               (cycle["id"], request_key)).fetchone()
    if prior:
        if prior["request_checksum"] != request_checksum:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return dict(prior)
    operation_id = str(uuid4())
    input_snapshot = build_input_snapshot(connection, position=dict(position), old_as=dict(old), contract=contract,
                                          operation_id=operation_id, provider_config=provider_config)
    row = connection.execute("""INSERT INTO m5_equivalent_generation_operations
        (id,request_key,request_checksum,cycle_db_id,position_id,expected_as_db_id,requested_by,
         variability_ref_json,input_json,input_checksum,provider_config_json,status)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb,'pending') RETURNING *""",
        (UUID(operation_id), request_key, request_checksum, cycle["id"], position["id"], old["id"], requested_by,
         json.dumps(variability_ref), json.dumps(input_snapshot, ensure_ascii=False), checksum(input_snapshot),
         json.dumps(provider_config))).fetchone()
    return dict(row)


def claim_generation(connection, operation_id: str) -> dict:
    row = connection.execute("SELECT * FROM m5_equivalent_generation_operations WHERE id=%s FOR UPDATE",
                             (UUID(operation_id),)).fetchone()
    if not row:
        raise ValueError("M5_EQUIVALENT_OPERATION_NOT_FOUND")
    if row["status"] == "completed":
        return dict(row)
    if row["status"] != "pending":
        raise ValueError("M5_EQUIVALENT_OPERATION_ALREADY_CLAIMED")
    token = uuid4()
    return dict(connection.execute("""UPDATE m5_equivalent_generation_operations
        SET status='leased',lease_token=%s,attempt_no=attempt_no+1 WHERE id=%s RETURNING *""",
        (token, row["id"])).fetchone())


def validate_candidate(input_snapshot: dict, candidate: dict) -> dict:
    contract = VariabilityContract.model_validate(input_snapshot["variability_contract"])
    old = input_snapshot["old_content"]
    checks = []
    def check(code: str, passed: bool):
        checks.append({"code": code, "result": "PASS" if passed else "FAIL"})
    check("case_identity", candidate.get("case_id") == contract.case_id and candidate.get("case_version") == contract.case_version)
    check("role_and_targets", candidate.get("base_role") == input_snapshot["base_role"] and
          candidate.get("indicator_targets") == input_snapshot["indicator_targets"])
    new_content = {"participant_payload": candidate.get("participant_payload"),
                   "execution_payload": candidate.get("execution_payload")}
    actual_changes = _changed_leaf_paths(old, new_content)
    allowed_mutations = all(any(path == allowed or path.startswith(allowed + "/")
                                for allowed in contract.allowed_paths) for path in actual_changes)
    check("allowed_mutations_only", allowed_mutations)
    changed = []
    for path in contract.allowed_paths:
        try:
            if _pointer(old, path) != _pointer(new_content, path):
                changed.append(path)
        except (KeyError, IndexError, TypeError, ValueError):
            check("allowed_path_integrity", False)
            break
    else:
        check("allowed_path_integrity", True)
    immutable_ok = True
    for path in contract.immutable_paths:
        try:
            immutable_ok &= _pointer(old, path) == _pointer(new_content, path)
        except (KeyError, IndexError, TypeError, ValueError):
            immutable_ok = False
    check("invariants_and_authority", immutable_ok)
    links_ok = True
    for paths in contract.linked_equal_paths:
        try:
            values = [_pointer(new_content, path) for path in paths]
            links_ok &= all(value == values[0] for value in values[1:])
        except (KeyError, IndexError, TypeError, ValueError):
            links_ok = False
    check("participant_execution_consistency", links_ok)
    substantive = sum(path in changed for path in contract.substantive_paths)
    check("substantive_difference", substantive >= contract.min_substantive_changes)
    admitted = all(item["result"] == "PASS" for item in checks) and contract.content_admission == "approved_for_qa"
    if contract.usage_scope == "assessment":
        admitted = admitted and contract.status == "published" and contract.content_admission == "approved"
    return {"checks": checks, "changed_paths": changed, "admitted": admitted,
            "code": "ADMITTED" if admitted else "M5_EQUIVALENT_CANDIDATE_NOT_ADMITTED"}


def fail_generation(connection, *, operation_id: str, lease_token: str, error_code: str,
                    output: dict | None = None, validation: dict | None = None) -> dict:
    row = connection.execute("""UPDATE m5_equivalent_generation_operations SET status='failed',error_code=%s,
        output_json=%s::jsonb,output_checksum=%s,validation_json=%s::jsonb,completed_at=NOW()
        WHERE id=%s AND status='leased' AND lease_token=%s RETURNING *""",
        (error_code, json.dumps(output) if output is not None else None, checksum(output) if output is not None else None,
         json.dumps(validation) if validation is not None else None, UUID(operation_id), UUID(lease_token))).fetchone()
    if not row:
        raise ValueError("M5_EQUIVALENT_LEASE_LOST")
    return dict(row)


def complete_generation(connection, *, operation_id: str, lease_token: str, candidate: dict,
                        policy: dict) -> dict:
    operation = connection.execute("SELECT * FROM m5_equivalent_generation_operations WHERE id=%s FOR UPDATE",
                                   (UUID(operation_id),)).fetchone()
    if not operation or operation["status"] != "leased" or str(operation["lease_token"]) != lease_token:
        raise ValueError("M5_EQUIVALENT_LEASE_LOST")
    position = connection.execute("SELECT * FROM m7_route_positions WHERE id=%s FOR UPDATE",
                                  (operation["position_id"],)).fetchone()
    cycle = connection.execute("SELECT * FROM m5_cycles WHERE id=%s FOR UPDATE", (operation["cycle_db_id"],)).fetchone()
    old = connection.execute("SELECT * FROM m5_assessment_situations WHERE id=%s FOR UPDATE",
                             (operation["expected_as_db_id"],)).fetchone()
    if cycle["status"] in TERMINAL_CYCLE or position["current_as_db_id"] != old["id"] or old["status"] not in {"active", "paused"}:
        connection.execute("UPDATE m5_equivalent_generation_operations SET status='rejected_late',error_code='M5_EQUIVALENT_OPERATION_EXPIRED',output_json=%s::jsonb,output_checksum=%s,completed_at=NOW() WHERE id=%s",
                           (json.dumps(candidate), checksum(candidate), operation["id"]))
        return {"status": "rejected_late", "error_code": "M5_EQUIVALENT_OPERATION_EXPIRED"}
    from Api.m7_completion import _effective_limit
    if _effective_limit(connection, dict(cycle)) != (None, None):
        connection.execute("UPDATE m5_equivalent_generation_operations SET status='rejected_late',error_code='M5_EQUIVALENT_OPERATION_EXPIRED',output_json=%s::jsonb,output_checksum=%s,completed_at=NOW() WHERE id=%s",
                           (json.dumps(candidate), checksum(candidate), operation["id"]))
        return {"status": "rejected_late", "error_code": "M5_EQUIVALENT_OPERATION_EXPIRED"}
    validation = validate_candidate(dict(operation["input_json"]), candidate)
    if not validation["admitted"]:
        return fail_generation(connection, operation_id=operation_id, lease_token=lease_token,
                               error_code=validation["code"], output=candidate, validation=validation)
    old_snapshot = deepcopy(old["snapshot_json"])
    new_id = str(uuid4())
    old_snapshot["assessment_situation_id"] = new_id
    old_snapshot["participant_payload"] = deepcopy(candidate["participant_payload"])
    execution = deepcopy(candidate["execution_payload"])
    old_snapshot["execution_payload_ref"] = {"id": f"{new_id}:execution", "version": "1", "checksum": checksum(execution)}
    old_snapshot["generation_ref"] = {"operation_id": operation_id,
                                      "input_checksum": operation["input_checksum"],
                                      "output_checksum": checksum(candidate),
                                      "variability_ref": operation["variability_ref_json"]}
    saved = connection.execute("""INSERT INTO m5_assessment_situations
        (assessment_situation_id,case_version_id,personalized_profile_id,cycle_db_id,session_db_id,usage_scope,
         status,snapshot_json,execution_payload_json,snapshot_checksum)
        VALUES(%s,%s,%s,%s,%s,%s,'admitted',%s::jsonb,%s::jsonb,%s) RETURNING id""",
        (UUID(new_id), old["case_version_id"], old["personalized_profile_id"], old["cycle_db_id"], old["session_db_id"],
         old["usage_scope"], json.dumps(old_snapshot, ensure_ascii=False), json.dumps(execution, ensure_ascii=False),
         checksum(old_snapshot))).fetchone()
    connection.execute("""INSERT INTO m5_admission_decisions
        (assessment_situation_db_id,policy_id,policy_version,policy_checksum,admitted,code,reasons_json,evidence_ids_json)
        VALUES(%s,%s,%s,%s,TRUE,'ADMITTED','[]'::jsonb,'[]'::jsonb)""",
        (saved["id"], policy["id"], policy["version"], checksum(policy)))
    connection.execute("""UPDATE m5_equivalent_generation_operations SET status='completed',output_json=%s::jsonb,
        output_checksum=%s,validation_json=%s::jsonb,candidate_as_db_id=%s,completed_at=NOW() WHERE id=%s""",
        (json.dumps(candidate, ensure_ascii=False), checksum(candidate), json.dumps(validation), saved["id"], operation["id"]))
    return {"status": "completed", "operation_id": operation_id, "candidate_as_db_id": int(saved["id"]),
            "assessment_situation_id": new_id, "validation": validation}


def run_provider(provider: EquivalentGenerationProvider, claimed: dict) -> dict:
    """Сетевой/LLM вызов: намеренно не принимает DB connection."""
    return provider.generate(input_snapshot=deepcopy(claimed["input_json"]))
