"""Offline audit of a release proposal, never a publisher or PATH runner.

Only repository files and git metadata are read. All socket creation is blocked;
dotenv loading is suppressed by isolated configuration. No database is created.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
BASE = "3385145201d5d365e08e9e8a6a6fb7e12a0aa258"


def require(condition, code):
    if not condition:
        raise AssertionError(code)


def main():
    # Do not load the workstation .env, use its DB or inherit provider secrets.
    executable_path = os.environ.get("PATH", "")
    os.environ.clear()
    os.environ.update(PATH=executable_path, AGENT4K_ISOLATED_STAND="1",
        AGENT4K_STAND_MARKER="stand-10.2:offline-release-proposal",
        DB_HOST="127.0.0.1", DB_NAME="product4k_pytest_offline_release_proposal",
        DB_USER="offline", DB_PASSWORD="unused", DB_POOL_MIN_SIZE="0",
        LOG_TO_FILE="false", AUDIT_LOGS_TO_DB="false", RUNTIME_LOGS_TO_DB="false")

    network_attempts = []

    class NoSocket(socket.socket):
        def __new__(cls, *args, **kwargs):
            network_attempts.append(True)
            raise AssertionError("OFFLINE_AUDIT_NETWORK_FORBIDDEN")

    socket.socket = NoSocket
    sys.path.insert(0, str(ROOT))
    from Api.assessment_programs import definition_checksum
    from Api.pilot_plan_admission import build_snapshot, project_plan, validate_program
    from tests.path_start_release_source import validate_release
    from tests.path_start_release_inputs import reserve_release_ids

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True,
                                       stderr=subprocess.PIPE).strip()

    require(not git("diff", BASE, "--", "Api", "scripts", "tests", "assessment_definitions"),
            "RUNTIME_DIFF_OUTSIDE_PREPARATION_SCOPE")
    recipe = json.loads((Path(__file__).parent / "program-1.2.proposed.json").read_bytes())
    require(recipe["source_code_sha"] == BASE and recipe["runtime_activation"] is False
            and recipe["database_id_assigned"] is False and recipe["published_at"] is None,
            "PROPOSAL_IS_NOT_PUBLICATION")
    receipt_ref = recipe["baseline_receipt"]
    data = (ROOT / receipt_ref["path"]).read_bytes()
    require(hashlib.sha256(data).hexdigest() == receipt_ref["sha256"], "BASELINE_RECEIPT_BYTES")
    source = json.loads(data)
    validate_release(source)
    ref = recipe["pilot_plan_snapshot_build"]
    snapshot = build_snapshot(ROOT / ref["package"])
    require(all(snapshot[key] == ref[key] for key in
                ("contract", "source_manifest_sha256", "snapshot_checksum")), "SNAPSHOT_IDENTITY")
    require(snapshot["review"]["proposal_payload_checksum"] == ref["proposal_payload_checksum"],
            "PROPOSAL_IDENTITY")
    program = deepcopy(recipe["program_fields"])
    require(program["status"] == "draft" and "id" not in program and "published_at" not in program,
            "NO_INHERITED_PUBLISHED_IDENTITY")
    program["source_refs_json"] = {
        **recipe["source_refs_without_pilot_plan_admission"], "pilot_plan_admission": snapshot}
    roles = recipe["role_profile_version_ids"]
    design = validate_program(program, roles, snapshot)
    checksum = definition_checksum(code=program["code"], version=program["version"], name=program["name"],
        assignment_ref=program["assignment_ref"], mode=program["mode"],
        configuration_id=program["assessment_configuration_id"], role_version_ids=roles,
        catalog_version_id=program["catalog_version_id"], source_refs=program["source_refs_json"])
    require(checksum == recipe["definition_checksum_when_materialized"], "PROGRAM_DEFINITION_CHECKSUM")
    projected = project_plan(snapshot, targets=design["full_m2_matrix"], catalog=[{
        "case_id": row["case_id"], "case_version": row["version"], "eligible": True,
        "target_ids": row["target_ids"], "reasons": []} for row in design["cases"]],
        catalog_ref={"id": design["catalog_ref"]["catalog_id"],
            "version": design["catalog_ref"]["catalog_version"],
            "checksum": design["catalog_ref"]["manifest_checksum"], "m2_checksum": design["m2_checksum"]},
        role_ref=design["role_refs"][0])
    # Eligibility=True above is explicit offline contract input, not new Case QA.
    require((len(design["full_m2_matrix"]), len(projected["planned_targets"]),
             len(projected["outside_plan_target_ids"]), len(design["observation_occurrences"]))
            == (61, 39, 22, 55), "COVERAGE_AND_CONDITIONS")

    statements = []

    class NeverSQL:
        def execute(self, *args, **kwargs):
            statements.append(args)
            raise AssertionError("OFFLINE_AUDIT_SQL_FORBIDDEN")

    try:
        reserve_release_ids(NeverSQL(), "assessment_program_definitions", 1)
    except AssertionError:
        require(not statements, "RESERVATION_REACHED_SQL")
    else:
        raise AssertionError("EXPECTED_SEED_BLOCKER_NOT_REPRODUCED")

    seed_tree = ast.parse((ROOT / "tests/path_start_release_inputs.py").read_text())
    calls = [node for node in ast.walk(seed_tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "reserve_release_ids"]
    require(any(len(node.args) > 1 and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "assessment_program_definitions" for node in calls),
            "SEED_PROGRAM_RESERVATION_CALL_MISSING")
    browser = (ROOT / "tests/browser/path29-participant.spec.mjs").read_text()
    require("expect(receipt.program_definition.version).toBe('1.1')" in browser,
            "EXPECTED_BROWSER_VERSION_PIN_NOT_FOUND")
    require(source["program"]["version"] == "1.1", "EXPECTED_CURRENT_SOURCE_PIN_NOT_FOUND")
    source_paths = [receipt_ref["path"], ref["package"] + "/manifest.json",
        "Api/pilot_plan_admission.py", "Api/pilot_plan_binding.py", "Api/assessment_programs.py",
        "scripts/publish_assessment_program.py", "scripts/assessment_first_case.py",
        "tests/path_start_release_source.py", "tests/path_start_release_inputs.py",
        "tests/browser/path29-participant.spec.mjs"]
    require(not network_attempts, "NETWORK_ATTEMPTED")
    return {
        "status": "OFFLINE_PROPOSAL_VALIDATED_EXECUTION_BLOCKED",
        "runtime_base_sha": BASE, "document_head_sha": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "proposed_program": program["code"] + "@" + program["version"],
        "program_definition_checksum": checksum, "admission_snapshot_checksum": snapshot["snapshot_checksum"],
        "full_m2_count": 61, "planned_count": 39, "outside_count": 22, "observation_rows": 55,
        "route": [row["case_id"] for row in projected["route"]], "timing": projected["timing"],
        "execution_blockers": [
            {"id": "SEED-01", "status": "REPRODUCED_WITH_NO_SQL",
             "reason": "seed_release reserves program IDs, but reserve_release_ids allowlist rejects the program table"},
            {"id": "SOURCE-01", "status": "EXPECTED_NOT_YET_RELEASED",
             "reason": "published-pilot receipt still pins 1.1; no authorized 1.2 publication/readback exists"},
            {"id": "BROWSER-01", "status": "STATIC_PIN_CONFIRMED",
             "reason": "browser assertion pins 1.1, not the exact version of a future verified receipt"},
            {"id": "AUTH-01", "status": "NOT_AUTHORIZED",
             "reason": "version/publication, persistent activation and paid PATH need separate explicit decisions"}],
        "source_files_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                                for path in source_paths},
        "database_connections": 0, "database_writes": 0, "provider_calls": 0,
        "publication_performed": False, "permanent_activation_performed": False,
        "historical_PREP_DIAG_01_root_cause": "UNKNOWN",
        "limitations": ["No fresh persistent DB readback; baseline receipt is historical",
                        "Offline projection supplies eligibility=True, not new human QA or AS admission",
                        "Expected seed failure is diagnosis, not a successful bootstrap or PATH"]}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
