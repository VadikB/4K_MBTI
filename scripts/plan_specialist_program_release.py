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
from Api.m5_package import digest, json_bytes, verify_package_directory
from Api.m5_runtime_rules import load_runtime_rule_package
from Api.m5_passport_generation import ADDRESSED_RUNTIME, BANK_PACKAGE
from scripts.build_m5_passport_bank import BATTERY_PACKAGE, BATTERY_RUNTIME
from Api.cycle_execution_manifest import M5_BATTERY_PILOT_REVIEW_PACKAGE, battery_pilot_review_path
from Api.m5_battery_contract import PILOT_CASE_SUFFIX, RULE_PACKAGE
from scripts.build_m5_passport_bank import RUNTIME_PACKAGE as BANK_RUNTIME_DIR


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.5"
RUNTIME_DIR = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization-runtime/1.2.0"
EXPECTED_CASE_IDS = [f"CASE.SPEC.{value:02d}" for value in range(1, 10)]
ADMISSION_EVIDENCE = {
    "case_format": "assessment_definitions/cases/competencies_4k/functional-personalization/0.5/verification-report.json",
    "case_dialogue": "docs/evc/evidence/pers-functional-personalization/protocol-v2-final-summary.json",
    "assessment_situation": "docs/evc/evidence/pers-functional-personalization/scenario-v2-executed/summary.json",
}


def build_trace(package_dir: Path = PACKAGE_DIR, runtime_dir: Path = RUNTIME_DIR) -> dict[str, Any]:
    verification = verify_package_directory(package_dir)
    package = json.loads((package_dir / "case-package.json").read_text())
    manifest = json.loads((package_dir / "manifest.json").read_text())
    artifacts = {item["name"]: item["sha256"] for item in manifest["artifacts"]}
    cases = sorted(package["cases"], key=lambda item: item["case_id"])
    if [item["case_id"] for item in cases] != EXPECTED_CASE_IDS:
        raise ValueError("SPECIALIST_NINE_CASE_SET_MISMATCH")
    if {item["base_role"] for item in cases} != {"specialist_expert"}:
        raise ValueError("SPECIALIST_NINE_CASE_ROLE_MISMATCH")
    runtime = load_runtime_rule_package(
        runtime_dir, cases, expected_case_package_version=manifest["version"]
    )
    registry = []
    for case in cases:
        if case["schema_version"] == 4:
            source_name = case["passport_source"]["file"]
            source_refs = {"as_contract_ref": case["as_contract_ref"]}
        else:
            number = case["case_id"].rsplit(".", 1)[-1]
            source_name = next(
                name for name in artifacts
                if name.startswith(f"sources/Case_SPEC_{number}_") and name.count("/") == 1
            )
            as_name = next(
                name for name in artifacts
                if name.startswith(f"sources/AS_SPEC_{number}_") and name.count("/") == 1
            )
            source_refs = {"assessment_situation_source": {"path": as_name, "sha256": artifacts[as_name]}}
        registry.append({
            "case_id": case["case_id"], "case_version": case["version"],
            "base_role": case["base_role"], "case_status": case["status"],
            "db_content_checksum": checksum(case),
            "source": {"path": source_name, "sha256": artifacts[source_name]},
            **source_refs,
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


def apply_import(trace: dict[str, Any], package_dir: Path = PACKAGE_DIR,
                 runtime_dir: Path = RUNTIME_DIR) -> dict[str, Any]:
    from Api.database import get_connection
    from Api.m5_catalog_integrity import publication_plan
    from Api.m5_runtime_rules import import_runtime_rule_version
    from Api.m5_storage import import_package_directory, package_readback
    from scripts.build_m5_sales_package import build_execution_rules

    package = json.loads((package_dir / "case-package.json").read_text())
    loaded_runtime = load_runtime_rule_package(
        runtime_dir, package["cases"], expected_case_package_version=trace["package"]["version"]
    )
    with get_connection() as connection:
        imported = import_package_directory(connection, package_dir)
        if package["schema_version"] == 4:
            rules = json.loads((package_dir / "execution-rules.json").read_bytes())
            if loaded_runtime["manifest"]["schema_version"] == 3:
                rules.update(owner_task="M5-02", case_bindings=loaded_runtime["bindings"]["case_bindings"])
        else:
            rules = build_execution_rules(package["cases"], loaded_runtime["bindings"])
        runtime = import_runtime_rule_version(
            connection, loaded_runtime, rules,
            package_db_id=imported["package_db_id"],
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
    """Build the approved Case content, also used to replay historical releases."""
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


def publish_diagnostic_battery(connection, *, published_by: int, organization_id: int,
                               catalog_id: str, catalog_version: str, idempotency_key: str,
                               decision_basis: str) -> dict[str, Any]:
    """Import the exact WORKING battery and publish its organization-scoped QA catalog."""
    from Api.m5_catalog_integrity import catalog_readback, publish_catalog
    from Api.m5_runtime_rules import import_runtime_rule_version
    from Api.m5_storage import import_package_directory, package_readback

    build_trace(BATTERY_PACKAGE, BATTERY_RUNTIME)
    imported = import_package_directory(connection, BATTERY_PACKAGE)
    package_id = imported["package_db_id"]
    readback = package_readback(connection, package_id)
    package = readback["package"]
    runtime = load_runtime_rule_package(
        BATTERY_RUNTIME, package["package_json"]["cases"], expected_case_package_version=package["package_version"],
    )
    bound = import_runtime_rule_version(connection, runtime, package["runtime_rules_json"], package_db_id=package_id)
    catalog = publish_catalog(
        connection, catalog_id=catalog_id, catalog_version=catalog_version, package_db_id=package_id,
        case_version_ids=[case["id"] for case in readback["cases"]], usage_scope="qa",
        published_by=published_by, organization_id=organization_id, decision_basis=decision_basis,
        idempotency_key=idempotency_key, runtime_rule_version_id=bound["id"],
    )
    return {"import": imported, "runtime": bound, "readback": readback, "catalog": catalog,
            "catalog_readback": catalog_readback(connection, catalog["catalog_db_id"])}


def build_release_artifacts(
    package: dict[str, Any], runtime: dict[str, Any], *, usage_scope: str,
    package_dir: Path = PACKAGE_DIR,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Assign immutable DB versions and seal the derived package and rule bindings."""
    from scripts.build_m5_sales_package import build_execution_rules

    if usage_scope not in {"assessment", "qa"}:
        raise ValueError("M5_USAGE_SCOPE_INVALID")
    scope_suffix = "-qa" if usage_scope == "qa" else ""
    passport_bank = package["schema_version"] == 4
    addressed_rules = runtime["manifest"]["schema_version"] == 3
    release_series = "passport.2" if addressed_rules else ("passport.1" if passport_bank else "admitted.1")
    battery_pilot = package_dir == BATTERY_PACKAGE
    release_suffix = PILOT_CASE_SUFFIX if battery_pilot else f"-{release_series}{scope_suffix}"
    source_manifest = json.loads((package_dir / "manifest.json").read_text())
    source_package = json.loads((package_dir / "case-package.json").read_text())
    source_ref = {
        "id": source_manifest["id"], "version": source_manifest["version"],
        "checksum": checksum({"package": source_package, "manifest": source_manifest}),
    }
    package["version"] = f"{source_ref['version']}{release_suffix}"
    package["status"] = "FROZEN"
    bindings = runtime["bindings"]
    for case in package["cases"]:
        case["version"] += release_suffix
        if passport_bank:
            case["passport"]["7 Version"] = case["version"]
        bindings["case_bindings"][case["case_id"]].update(
            case_version=case["version"], case_checksum=checksum(case),
        )
    rules = ({"schema_version": 3, "status": "structured_draft", "owner_task": "M5-02" if addressed_rules else "M5-01",
              "case_bindings": bindings["case_bindings"]} if passport_bank
             else build_execution_rules(package["cases"], bindings))
    replacements = {"case-package.json": package, "execution-rules.json": rules}
    manifest = {
        **source_manifest, "version": package["version"], "status": package["status"],
        "source_package_ref": source_ref,
        "artifacts": [
            {**item, "sha256": digest(json_bytes(replacements[item["name"]]))}
            if item["name"] in replacements else item
            for item in source_manifest["artifacts"]
        ],
    }
    if battery_pilot:
        manifest.pop("diagnostic_only")
        manifest["battery_pilot"] = True

    runtime_manifest = runtime["manifest"]
    source_runtime_ref = {
        "id": runtime_manifest["id"], "version": runtime_manifest["version"],
        "manifest_checksum": runtime["manifest_checksum"],
    }
    runtime_series = ("1.5.1" if battery_pilot else
                      ("1.4.1" if addressed_rules else ("1.3.1" if passport_bank else "1.2.1")))
    runtime_version = f"{runtime_series}{scope_suffix}"
    bindings["version"] = runtime_version
    bindings.pop("artifact_checksum")
    bindings["artifact_checksum"] = digest(json_bytes(bindings))
    runtime_manifest.update(
        version=runtime_version,
        source={
            "case_package_id": manifest["id"], "case_package_version": manifest["version"],
            "runtime_ref": source_runtime_ref,
            **({"as_contract_ref": package["as_contract_ref"]} if passport_bank else {}),
            **({"scenario_case_ids": runtime_manifest["source"]["scenario_case_ids"]} if addressed_rules else {}),
        },
        artifacts=[{"name": "event-bindings.json", "sha256": bindings["artifact_checksum"]}],
    )
    runtime["manifest_checksum"] = digest(json_bytes(runtime_manifest))
    return manifest, rules


def build_passport_admission(package_dir: Path, runtime_dir: Path, *, usage_scope: str,
                             evidence_path: Path | None) -> tuple[dict, dict, dict, dict | None]:
    battery_pilot = package_dir == BATTERY_PACKAGE
    if json.loads((package_dir / "manifest.json").read_bytes()).get("diagnostic_only") is True and (
        not battery_pilot or usage_scope != "assessment"
    ):
        raise ValueError("M5_BATTERY_PREPARATION_NOT_ENABLED")
    package = json.loads((package_dir / "case-package.json").read_bytes())
    runtime = load_runtime_rule_package(runtime_dir, package["cases"], expected_case_package_version=package["version"])
    expected = {case["case_id"]: checksum(case) for case in package["cases"]}
    review_package = None
    if usage_scope == "qa":
        # Only QA scope receives synthetic evidence. Assessment requires review of
        # the exact passport checksums AND the new AS result contract.
        artifact = package_dir / "verification-report.json"
        raw = artifact.read_bytes()
    else:
        if evidence_path is None:
            raise ValueError("M5_PASSPORT_BANK_ASSESSMENT_EVIDENCE_REQUIRED")
        artifact = evidence_path
        raw = artifact.read_bytes()
        evidence = json.loads(raw)
        if battery_pilot:
            from Api.m5_battery_contract import load_scenario
            from Api.m5_passport_generation import read_as_package

            try:
                review_path = battery_pilot_review_path(evidence.get("review_package"))
            except ValueError as exc:
                raise ValueError("M5_BATTERY_PILOT_REVIEW_EVIDENCE_MISMATCH") from exc
            _, as_contract, review_refs = read_as_package(ROOT / review_path)
            # A pre-existing v5 publication used an implicit pin in its manifest.
            if review_path != M5_BATTERY_PILOT_REVIEW_PACKAGE:
                review_package = review_refs["protocol_package"]
            scenario_refs = [load_scenario(case, ROOT / RULE_PACKAGE)["ref"] for case in package["cases"]]
            if (not str(evidence.get("human_review_ref") or "").strip()
                    or evidence.get("scenario_ref") != scenario_refs[0]
                    or evidence.get("review_package") != review_refs["protocol_package"]
                    or evidence.get("prepared_as_contract_ref") != as_contract
                    or evidence.get("runtime_rule_ref") != {
                        "id": runtime["manifest"]["id"], "version": runtime["manifest"]["version"],
                        "manifest_checksum": runtime["manifest_checksum"],
                    }):
                raise ValueError("M5_BATTERY_PILOT_REVIEW_EVIDENCE_MISMATCH")
        if (evidence.get("as_contract_ref") != package["as_contract_ref"] or evidence.get("cases") != expected
                or evidence.get("scopes") != {key: "PASS" for key in ADMISSION_EVIDENCE}
                or (runtime["manifest"]["schema_version"] == 3 and evidence.get("runtime_rule_ref") != {
                    "id": runtime["manifest"]["id"], "version": runtime["manifest"]["version"],
                    "manifest_checksum": runtime["manifest_checksum"],
                })):
            raise ValueError("M5_PASSPORT_BANK_ASSESSMENT_EVIDENCE_MISMATCH")
    path = str(artifact.relative_to(ROOT)) if artifact.is_relative_to(ROOT) else artifact.name
    ref = {"path": path, "sha256": digest(raw)}
    for case in package["cases"]:
        case["status"] = "FROZEN"
    return package, runtime, {scope: ref for scope in ADMISSION_EVIDENCE}, review_package


def publish_admitted_catalog(
    trace: dict[str, Any], *, published_by: int, decision_basis: str,
    catalog_id: str, catalog_version: str, idempotency_key: str,
    organization_id: int | None, usage_scope: str = "assessment", package_dir: Path = PACKAGE_DIR,
    runtime_dir: Path = RUNTIME_DIR, evidence_path: Path | None = None,
) -> dict[str, Any]:
    from Api.database import get_connection
    from Api.m5_catalog_integrity import catalog_readback, publish_catalog
    from Api.m5_runtime_rules import import_runtime_rule_version
    from Api.m5_storage import import_package, package_readback
    if not str(decision_basis or "").strip():
        raise ValueError("SPECIALIST_ADMISSION_DECISION_BASIS_REQUIRED")
    review_package = None
    if package_dir == PACKAGE_DIR:
        package, loaded_runtime, evidence_refs = build_admitted_materials(decision_basis)
    else:
        verify_package_directory(package_dir)
        package, loaded_runtime, evidence_refs, review_package = build_passport_admission(
            package_dir, runtime_dir, usage_scope=usage_scope, evidence_path=evidence_path,
        )
    manifest, execution_rules = build_release_artifacts(
        package, loaded_runtime, usage_scope=usage_scope, package_dir=package_dir,
    )
    with get_connection() as connection:
        imported = import_package(
            connection, package=package, manifest=manifest, execution_rules=execution_rules
        )
        runtime = import_runtime_rule_version(
            connection, loaded_runtime, execution_rules, package_db_id=imported["package_db_id"],
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
                    "base_role": case["base_role"], "usage_scopes": [usage_scope],
                    "origin": {
                        "type": "synthetic_test" if usage_scope == "qa" else "human_review",
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
            case_version_ids=[int(case["id"]) for case in cases], usage_scope=usage_scope,
            organization_id=organization_id, published_by=published_by,
            decision_basis=decision_basis, idempotency_key=idempotency_key,
            runtime_rule_version_id=runtime["id"], review_package=review_package,
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
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--historical-0.5", dest="historical_0_5", action="store_true", help="Replay the historical release.")
    sources.add_argument("--passport-01", action="store_true", help="Replay the M5-01 passport release.")
    sources.add_argument("--diagnostic-battery", action="store_true", help="Select WORKING battery v0.3 for QA.")
    sources.add_argument("--pilot-battery", action="store_true", help="Select the reviewed ordinary pilot release.")
    parser.add_argument("--assessment-evidence", type=Path, help="Reviewed admission evidence for the passport bank.")
    parser.add_argument("--publish-admitted-catalog", action="store_true")
    parser.add_argument("--published-by", type=int)
    parser.add_argument("--decision-basis")
    parser.add_argument("--catalog-id", default="specialist-pilot")
    parser.add_argument("--catalog-version")
    parser.add_argument("--idempotency-key")
    parser.add_argument("--organization-id", type=int)
    parser.add_argument("--usage-scope", choices=("assessment", "qa"), default="assessment",
                        help="Publication scope; qa uses synthetic evidence and separate artifact versions.")
    args = parser.parse_args()
    if args.diagnostic_battery:
        if args.publish_admitted_catalog:
            parser.error("The diagnostic battery cannot be published as an admitted catalog.")
        result = build_trace(BATTERY_PACKAGE, BATTERY_RUNTIME)
        if args.apply_import:
            if (args.usage_scope != "qa" or args.organization_id is None or args.published_by is None
                    or not args.decision_basis or not args.catalog_version):
                parser.error("Diagnostic import requires --usage-scope qa, --organization-id, --published-by, "
                             "--decision-basis and --catalog-version.")
            from Api.database import get_connection

            catalog_id = "specialist-battery-diagnostic" if args.catalog_id == "specialist-pilot" else args.catalog_id
            with get_connection() as connection:
                result["database"] = publish_diagnostic_battery(
                    connection, published_by=args.published_by, organization_id=args.organization_id,
                    catalog_id=catalog_id, catalog_version=args.catalog_version,
                    idempotency_key=args.idempotency_key or f"{catalog_id}-{args.catalog_version}",
                    decision_basis=args.decision_basis,
                )
                connection.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    package_dir, runtime_dir = ((PACKAGE_DIR, RUNTIME_DIR) if args.historical_0_5
                                else (BANK_PACKAGE, BANK_RUNTIME_DIR if args.passport_01 else ADDRESSED_RUNTIME))
    default_version = "1.0" if args.historical_0_5 else ("1.1" if args.passport_01 else "1.2")
    if args.pilot_battery:
        if args.usage_scope != "assessment" or (args.apply_import and not args.publish_admitted_catalog):
            parser.error("The pilot release requires explicit assessment catalog publication.")
        package_dir, runtime_dir = BATTERY_PACKAGE, BATTERY_RUNTIME
        default_version = "1.3"
    if not args.historical_0_5 and args.usage_scope == "qa":
        default_version += "-qa"
    catalog_version = args.catalog_version or default_version
    idempotency_key = args.idempotency_key or f"{args.catalog_id}-{catalog_version}"
    result = build_trace(package_dir, runtime_dir)
    if args.publish_admitted_catalog:
        if args.published_by is None or not args.decision_basis:
            parser.error("--publish-admitted-catalog requires --published-by and --decision-basis")
        result["database"] = publish_admitted_catalog(
            copy.deepcopy(result), published_by=args.published_by, decision_basis=args.decision_basis,
            catalog_id=args.catalog_id, catalog_version=catalog_version,
            idempotency_key=idempotency_key, organization_id=args.organization_id,
            usage_scope=args.usage_scope, package_dir=package_dir, runtime_dir=runtime_dir,
            evidence_path=args.assessment_evidence,
        )
    elif args.apply_import:
        result["database"] = apply_import(result, package_dir, runtime_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
