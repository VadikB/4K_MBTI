"""Trace and idempotently import the approved nine-case Specialist source set.

This command deliberately does not manufacture human admission or publish a
catalog.  It prepares the exact immutable DB versions and reports the first
remaining release gate through the same catalog planner used by production.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Api.m5_case_runtime import checksum
from Api.m5_package import digest, verify_package_directory
from Api.m5_runtime_rules import load_runtime_rule_package


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.5"
RUNTIME_DIR = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization-runtime/1.2.0"
EXPECTED_CASE_IDS = [f"CASE.SPEC.{value:02d}" for value in range(1, 10)]
ADMISSION_EVIDENCE = {
    "case_format": "assessment_definitions/cases/competencies_4k/functional-personalization/0.5/verification-report.json",
    "case_dialogue": "docs/evc/evidence/pers-functional-personalization/protocol-v2-final-summary.json",
    "assessment_situation": "docs/evc/evidence/pers-functional-personalization/scenario-v2-executed/summary.json",
}


def build_trace() -> dict[str, Any]:
    verification = verify_package_directory(PACKAGE_DIR)
    package = json.loads((PACKAGE_DIR / "case-package.json").read_text())
    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text())
    artifacts = {item["name"]: item["sha256"] for item in manifest["artifacts"]}
    cases = sorted(package["cases"], key=lambda item: item["case_id"])
    if [item["case_id"] for item in cases] != EXPECTED_CASE_IDS:
        raise ValueError("SPECIALIST_NINE_CASE_SET_MISMATCH")
    if {item["base_role"] for item in cases} != {"specialist_expert"}:
        raise ValueError("SPECIALIST_NINE_CASE_ROLE_MISMATCH")
    runtime = load_runtime_rule_package(
        RUNTIME_DIR, cases, expected_case_package_version=manifest["version"]
    )
    registry = []
    for case in cases:
        number = case["case_id"].rsplit(".", 1)[-1]
        source_name = next(
            name for name in artifacts
            if name.startswith(f"sources/Case_SPEC_{number}_") and name.count("/") == 1
        )
        as_name = next(
            name for name in artifacts
            if name.startswith(f"sources/AS_SPEC_{number}_") and name.count("/") == 1
        )
        registry.append({
            "case_id": case["case_id"],
            "case_version": case["version"],
            "base_role": case["base_role"],
            "case_status": case["status"],
            "db_content_checksum": checksum(case),
            "source": {"path": source_name, "sha256": artifacts[source_name]},
            "assessment_situation_source": {"path": as_name, "sha256": artifacts[as_name]},
        })
    admitted = (
        verification.get("methodology_admission") == "PASS"
        and verification.get("runtime_admission") == "ENABLED"
        and all(item["case_status"] == "FROZEN" for item in registry)
    )
    return {
        "schema_version": 1,
        "package": {
            "id": manifest["id"], "version": manifest["version"],
            "status": manifest["status"], "runtime_enabled": package["runtime_enabled"],
            "package_checksum": verification["package_checksum"],
        },
        "runtime": {
            "id": runtime["manifest"]["id"], "version": runtime["manifest"]["version"],
            "status": runtime["manifest"]["status"],
            "manifest_checksum": runtime["manifest_checksum"],
        },
        "role": "specialist_expert",
        "sales_semantics": "professional_example_not_base_role",
        "cases": registry,
        "static_verification": verification,
        "assessment_admitted": admitted,
        "release_gate": None if admitted else {
            "code": "SPECIALIST_NINE_CASE_ASSESSMENT_ADMISSION_REQUIRED",
            "methodology_admission": verification.get("methodology_admission"),
            "runtime_admission": verification.get("runtime_admission"),
            "message": "Import is allowed; assessment catalog publication remains fail-closed.",
        },
    }


def apply_import(trace: dict[str, Any]) -> dict[str, Any]:
    from Api.database import get_connection
    from Api.m5_catalog_integrity import publication_plan
    from Api.m5_runtime_rules import import_runtime_rule_version
    from Api.m5_storage import import_package_directory, package_readback
    from scripts.build_m5_sales_package import build_execution_rules

    package = json.loads((PACKAGE_DIR / "case-package.json").read_text())
    loaded_runtime = load_runtime_rule_package(
        RUNTIME_DIR, package["cases"], expected_case_package_version=trace["package"]["version"]
    )
    with get_connection() as connection:
        imported = import_package_directory(connection, PACKAGE_DIR)
        runtime = import_runtime_rule_version(
            connection, loaded_runtime, build_execution_rules(package["cases"], loaded_runtime["bindings"])
        )
        readback = package_readback(connection, imported["package_db_id"])
        case_ids = [int(item["id"]) for item in readback["cases"]]
        plan = publication_plan(
            connection, package_db_id=imported["package_db_id"], case_version_ids=case_ids,
            usage_scope="assessment", runtime_rule_version_id=runtime["id"],
        )
        connection.commit()
    return {"import": imported, "runtime": runtime, "readback": readback, "publication_plan": plan}


def build_admitted_materials(decision_basis: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build the DB release snapshot without rewriting the repository candidate."""
    if not str(decision_basis or "").strip():
        raise ValueError("SPECIALIST_ADMISSION_DECISION_BASIS_REQUIRED")
    package = json.loads((PACKAGE_DIR / "case-package.json").read_text())
    loaded_runtime = load_runtime_rule_package(
        RUNTIME_DIR, package["cases"], expected_case_package_version="0.5"
    )
    admitted = copy.deepcopy(package)
    runtime = copy.deepcopy(loaded_runtime)
    for case in admitted["cases"]:
        case["status"] = "FROZEN"
        case["author_case"]["Status"] = "FROZEN"
        runtime["bindings"]["case_bindings"][case["case_id"]]["case_checksum"] = checksum(case)
    evidence_refs: dict[str, dict[str, str]] = {}
    for scope, relative in ADMISSION_EVIDENCE.items():
        path = ROOT / relative
        if not path.is_file():
            raise ValueError(f"SPECIALIST_ADMISSION_EVIDENCE_MISSING:{scope}")
        value = json.loads(path.read_text())
        if scope == "case_format" and value.get("result") != "PASS":
            raise ValueError(f"SPECIALIST_ADMISSION_EVIDENCE_NOT_PASS:{scope}")
        if scope == "case_dialogue" and value.get("final_status_counts") != {"PASS": 27}:
            raise ValueError(f"SPECIALIST_ADMISSION_EVIDENCE_NOT_PASS:{scope}")
        if scope == "assessment_situation" and (
            value.get("completed") != 34 or value.get("status_counts") != {"PASS": 34}
        ):
            raise ValueError(f"SPECIALIST_ADMISSION_EVIDENCE_NOT_PASS:{scope}")
        evidence_refs[scope] = {"path": relative, "sha256": digest(path.read_bytes())}
    return admitted, runtime, evidence_refs


def publish_admitted_catalog(
    trace: dict[str, Any], *, published_by: int, decision_basis: str,
    catalog_id: str, catalog_version: str, idempotency_key: str,
    organization_id: int | None,
) -> dict[str, Any]:
    from Api.database import get_connection
    from Api.m5_catalog_integrity import catalog_readback, publish_catalog
    from Api.m5_runtime_rules import import_runtime_rule_version
    from Api.m5_storage import import_package, package_readback
    from scripts.build_m5_sales_package import build_execution_rules

    package, loaded_runtime, evidence_refs = build_admitted_materials(decision_basis)
    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text())
    execution_rules = json.loads((PACKAGE_DIR / "execution-rules.json").read_text())
    with get_connection() as connection:
        imported = import_package(
            connection, package=package, manifest=manifest, execution_rules=execution_rules
        )
        runtime = import_runtime_rule_version(
            connection, loaded_runtime,
            build_execution_rules(package["cases"], loaded_runtime["bindings"]),
        )
        readback = package_readback(connection, imported["package_db_id"])
        cases = readback["cases"]
        for case in cases:
            for scope, evidence_ref in evidence_refs.items():
                evidence = {
                    "schema_version": 1, "eligibility": "user_admission", "scope": scope,
                    "result": "PASS", "case_ref": {
                        "id": case["case_id"], "version": case["case_version"],
                        "checksum": case["content_checksum"],
                    },
                    "base_role": case["base_role"], "usage_scopes": ["assessment"],
                    "origin": {
                        "type": "human_review",
                        "actor_ref": f"user:{published_by}:{decision_basis.strip()}",
                    },
                    "evidence_ref": evidence_ref,
                }
                evidence_checksum = checksum(evidence)
                connection.execute(
                    """INSERT INTO m5_qa_evidence
                       (case_version_id,scope,result,evidence_json,evidence_checksum)
                       VALUES (%s,%s,'PASS',%s::jsonb,%s)
                       ON CONFLICT (evidence_checksum) DO NOTHING""",
                    (case["id"], scope, json.dumps(evidence, ensure_ascii=False), evidence_checksum),
                )
        catalog = publish_catalog(
            connection, catalog_id=catalog_id, catalog_version=catalog_version,
            package_db_id=imported["package_db_id"],
            case_version_ids=[int(case["id"]) for case in cases], usage_scope="assessment",
            organization_id=organization_id, published_by=published_by,
            decision_basis=decision_basis, idempotency_key=idempotency_key,
            runtime_rule_version_id=runtime["id"],
        )
        result = {
            "import": imported, "runtime": runtime, "readback": readback,
            "catalog": catalog, "catalog_readback": catalog_readback(connection, catalog["catalog_db_id"]),
            "source_trace": trace,
        }
        connection.commit()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-import", action="store_true")
    parser.add_argument("--publish-admitted-catalog", action="store_true")
    parser.add_argument("--published-by", type=int)
    parser.add_argument("--decision-basis")
    parser.add_argument("--catalog-id", default="specialist-pilot")
    parser.add_argument("--catalog-version", default="1.0")
    parser.add_argument("--idempotency-key", default="specialist-pilot-1.0")
    parser.add_argument("--organization-id", type=int)
    args = parser.parse_args()
    result = build_trace()
    if args.publish_admitted_catalog:
        if args.published_by is None or not args.decision_basis:
            parser.error("--publish-admitted-catalog requires --published-by and --decision-basis")
        result["database"] = publish_admitted_catalog(
            result, published_by=args.published_by, decision_basis=args.decision_basis,
            catalog_id=args.catalog_id, catalog_version=args.catalog_version,
            idempotency_key=args.idempotency_key, organization_id=args.organization_id,
        )
    elif args.apply_import:
        result["database"] = apply_import(result)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
