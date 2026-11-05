"""Offline verification of a read-only publication preflight, not publication."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[4]
if not __debug__:
    raise RuntimeError("EVIDENCE_CHECK_REQUIRES_ASSERTIONS")
os.environ.clear()
os.environ.update(
    AGENT4K_ISOLATED_STAND="1",
    AGENT4K_STAND_MARKER="stand-10.2:publication-preflight-offline",
    DB_HOST="127.0.0.1",
    DB_NAME="product4k_pytest_preflight_offline",
    DB_USER="offline",
    DB_POOL_MIN_SIZE="0",
)
attempts = []

class NoSocket(socket.socket):
    def __new__(cls, *args, **kwargs):
        attempts.append(True)
        raise AssertionError("OFFLINE_NETWORK_FORBIDDEN")

socket.socket = NoSocket
sys.path.insert(0, str(ROOT))
from tests.path_start_release_source import validate_release
from Api.pilot_plan_admission import build_snapshot, validate_program
from Api.assessment_programs import definition_checksum

directory = Path(__file__).parent
value = json.loads((directory / "readback.json").read_bytes())
assert value["status"] == "READ_ONLY_PREFLIGHT_PASS_DECISIONS_PENDING"
assert value["runtime_sha"] == "e63eba67d77fb73f7fb9bb219bc3fe5d3807a909"
assert value["transaction_read_only"] == "on" and value["transaction_rolled_back"]
assert value["schema_or_data_writes"] is False and value["publication_performed"] is False
assert value["provider_calls"] == 0 and value["candidate_1_2_free"] is True
assert not any(row["version"] == "1.2" for row in value["program_versions"])
def object_checksum(item):
    return hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), default=str).encode()).hexdigest()
baseline_path = ROOT / "tests/browser/fixtures/path-start-release.json"
assert hashlib.sha256(baseline_path.read_bytes()).hexdigest() == value["historical_source_file_sha256"]
baseline = json.loads(baseline_path.read_bytes())
for key in ("program", "configuration", "catalog", "roles", "cases", "artifact_readback"):
    row = value["source_comparison"][key]
    assert row["match"] is True
    assert row["historical_sha256"] == object_checksum(baseline[key])
    assert row["actual_sha256"] == object_checksum(value["legacy_1_1_source"][key])
    assert row["historical_sha256"] == row["actual_sha256"]
schema = ROOT / "docs/evc/evidence/path-pilot-schema-readback"
expected = json.loads((schema / "expected-schema.json").read_bytes())
for filename, field in [
    ("READ_SCHEMA.py", "read_schema_source_sha256"),
    ("expected-schema.json", "expected_schema_file_sha256"),
]:
    assert hashlib.sha256((schema / filename).read_bytes()).hexdigest() == value[field]
assert value["schema_comparison"]["actual_metadata_checksum"] == expected["metadata_checksum"]
assert all(not value["schema_comparison"][key] for key in ("missing", "changed", "extra", "missing_tables"))
source = value["legacy_1_1_source"]
assert source["source_code_sha"] == value["runtime_sha"]
assert source["contains_user_history"] is False and source["new_methodology_approval"] is False
assert source["target"]["read_only"] is True and source["target"]["database"] == "agent4k_test"
validate_release(source)
assert len(source["cases"]) == 9
assert sum(len(case["qa_evidence"]) for case in source["cases"]) == 27
assert len(source["artifact_readback"]) == 15
recipe = json.loads((ROOT / "docs/evc/evidence/pilot-program-release-plan/program-1.2.proposed.json").read_bytes())
snapshot = build_snapshot(ROOT / recipe["pilot_plan_snapshot_build"]["package"])
program = deepcopy(recipe["program_fields"])
program["source_refs_json"] = {
    **recipe["source_refs_without_pilot_plan_admission"],
    "pilot_plan_admission": snapshot,
}
design = validate_program(program, recipe["role_profile_version_ids"], snapshot)
calculated = definition_checksum(
    code=program["code"], version=program["version"], name=program["name"],
    assignment_ref=program["assignment_ref"], mode=program["mode"],
    configuration_id=program["assessment_configuration_id"],
    catalog_version_id=program["catalog_version_id"],
    role_version_ids=recipe["role_profile_version_ids"],
    source_refs=program["source_refs_json"],
)
assert calculated == recipe["definition_checksum_when_materialized"] == value["candidate"]["definition_checksum"]
assert len(design["full_m2_matrix"]) == 61 and len(design["observation_occurrences"]) == 55
operation = json.loads((directory / "operations-proposal.json").read_bytes())
assert operation["publication"]["not_executed"]
assert operation["retirement"]["execution_now"] is False
assert "NOT_RUN" in operation["retirement"]["free_guard_regression"]
assert value["publisher_owner_authorization"] == "PENDING_NOT_INFERRED_FROM_DB_ROLE"
links = []
for filename in [
    "docs/evc/tasks/pilot-program-release/STATE.md",
    "docs/evc/tasks/pilot-program-release-preparation.md",
]:
    path = ROOT / filename
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" in target:
            continue
        assert (path.parent / target.split("#")[0]).exists(), (filename, target)
        links.append(target)
assert not attempts
assert not any(key in sys.modules for key in ("Api.config", "Api.database", "Api.llm"))
print(json.dumps({
    "result": "PASS_OFFLINE_PREFLIGHT_EVIDENCE",
    "source_objects_compared": 6,
    "cases": 9,
    "original_qa": 27,
    "recomputed_artifacts": 15,
    "schema_tables": 32,
    "candidate_checksum": calculated,
    "docs_local_links_checked": len(links),
    "socket_attempts": 0,
    "db_connections": 0,
    "provider_calls": 0,
    "publication": False,
    "retirement_guard_execution_test": "NOT_RUN_OWNER_OPERATIONAL_CHOICE_PENDING",
}))
