"""Offline verification of recorded audit evidence, not product acceptance."""
from collections import Counter
import hashlib
import json
from pathlib import Path


def require(condition, code):
    if not condition:
        raise ValueError(code)


def validate_semantics(directory):
    def read(name):
        return json.loads((directory / name).read_text())

    matrix = read("audit-matrix.json")
    require(matrix["code_sha"] == "946a46cb71e5ca5cc99778f036807d6c193188dc", "PRODUCT_SHA")
    require(matrix["real_path_sha"] == "e63eba67d77fb73f7fb9bb219bc3fe5d3807a909", "PAID_SHA_RELABELLED")
    require(matrix["real_run_id"] == "2ff983f12c67494b990b0f85284b8d70", "REAL_RUN")
    require(matrix["final_sha_whole_path"] == matrix["post_deploy_whole_path"] == "NOT_RUN", "WHOLE_PATH_OVERCLAIM")
    require(matrix["overall"] == "NOT_READY_FOR_COMPLETE_PATH_ACCEPTANCE", "ACCEPTANCE_OVERCLAIM")
    require(matrix["human_acceptance"] == "NOT_GRANTED_BY_THIS_AUDIT", "HUMAN_ACCEPTANCE")
    rows = matrix["rows"]
    require(len(rows) == 18 and {row["id"] for row in rows} == {f"AC{i:02d}" for i in range(1, 19)}, "AC_IDENTITIES")
    require(Counter(row["status"] for row in rows) == {"PASS": 13, "NOT_RUN": 5}, "AC_COUNTS")
    require({row["id"] for row in rows if row["status"] == "NOT_RUN"} == {"AC06", "AC07", "AC09", "AC10", "AC18"}, "PROOF_GAPS")
    require(all(row.get("basis") and row.get("remaining") and row.get("owner") for row in rows), "AC_TRACEABILITY")
    require(matrix["new_paid_calls"] == 0 and matrix["working_database_access"] is False, "AUDIT_SCOPE")
    auth = read("auth-observation.json")
    require("Сессия входа не сохранилась" in auth["before"] and auth["after"] == "", "AUTH_OBSERVATION")
    require(auth["journey401"] == auth["heldChatRequests"] == 1, "AUTH_TRANSPORT")
    require(auth["historical_causality"] == "NOT_ESTABLISHED" and auth["product_changed"] is False, "AUTH_CAUSAL_OVERCLAIM")
    stats = read("auth-diagnostic-results.json")["stats"]
    require((stats["expected"], stats["unexpected"], stats["skipped"], stats["flaky"]) == (0, 1, 0, 0), "AUTH_FALSE_PASS")
    prep = read("prep-review.json")
    require(prep["root_cause"] == "UNKNOWN" and prep["failed_check_ids"] is None and prep["individual_check_reasons"] is None, "PREP_INVENTED_CAUSE")
    require(prep["actual"] == "M5_FUNCTIONAL_AS_NOT_ADMITTED:INCOMPLETE", "PREP_AGGREGATE")
    require(prep["started"] is False and prep["saved_as"] is None and prep["assessment_answers"] == 0, "PREP_FALSE_START")
    require(prep["product_fix"] == "NOT_PERFORMED" and prep["new_paid_calls"] == 0 and prep["database_access"] is False, "PREP_SCOPE")
    path = read("offline-path-check.json")
    require(path["result"] == "PASS_OFFLINE_ACTUAL_PATH" and path["run_id"] == matrix["real_run_id"], "OFFLINE_PATH")
    require(path["primary_files_verified"] == 34 and path["runtime_files_verified"] == 11, "PRIMARY_COUNTS")
    require(path["new_provider_calls"] == path["db_connections"] == path["python_socket_attempts"] == 0, "OFFLINE_SCOPE")
    identity = read("source-identities.json")
    require(identity["all_recorded_runner_files_unchanged"] is True and identity["backend_artifact_diff"] == "", "SOURCE_DRIFT")
    require(len(identity["files"]) == 11 and all(row["paid_runtime_sha256"] == row["current_sha256"] for row in identity["files"]), "RUNNER_HASHES")
    require(hashlib.sha256((directory / "path-start-1.3.txt").read_bytes()).hexdigest() == identity["assignment_sha256"], "ASSIGNMENT_BYTES")
    release = read("release2068.json")
    server = read("release2068-server-readback.json")
    require(release["main_sha"] == release["test_sha"] == server["actual_sha"] == matrix["code_sha"], "DEPLOYMENT_SHA")
    require(release["deployment"]["status"] == server["status"] == "PASS" and server["tracked_assets"] == 45, "DEPLOYMENT_READBACK")
    return {"audit_evidence": "PASS", "criteria": {"PASS": 13, "NOT_RUN": 5},
            "whole_final_path": "NOT_RUN", "auth_diagnostic": "FAIL_REPRODUCED",
            "prep_root_cause": "UNKNOWN", "new_provider_calls": 0, "human_acceptance": False}


def verify_manifest(directory):
    root = directory.parents[3]
    manifest = json.loads((directory / "FILES.json").read_text())
    for item in manifest["files"]:
        target = (root / item["path"]).resolve()
        require(target.is_relative_to(root.resolve()) and target.is_file(), "MANIFEST_PATH")
        data = target.read_bytes()
        require(len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"], "MANIFEST_DIGEST:" + item["path"])
    return len(manifest["files"])


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("OPTIMIZED_PYTHON_FORBIDDEN")
    here = Path(__file__).resolve().parent
    result = validate_semantics(here)
    result["verified_files"] = verify_manifest(here)
    print(json.dumps(result, ensure_ascii=False))
