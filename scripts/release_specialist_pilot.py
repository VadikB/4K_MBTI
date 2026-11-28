"""Publish a Specialist battery and plan in one transaction on TEST."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import pwd

from Api import assessment_programs, pilot_plan_binding
from Api.assessment_authoring_service import assessment_authoring_service
from Api.assessment_configuration import definition_checksum
from Api.assessment_methodology_publication import load_verified_m2_package
from Api.cycle_execution_manifest import (
    BATTERY_V04_SCENARIO_CURRENT, BATTERY_V06_SCENARIO_PACKAGE, M5_BATTERY_PILOT_REVIEW_PACKAGES,
    battery_scenario_ref,
)
from Api.m5_case_runtime import canonical_bytes, checksum
from Api.m5_catalog_integrity import catalog_readback, publish_catalog, require_release_publisher
from Api.m5_package import digest
from Api.m5_passport_generation import read_as_package
from Api.m5_runtime_rules import import_runtime_rule_version, load_runtime_rule_package
from Api.m5_storage import import_package
from Api.m7_cycle_planner import _catalog
from Api.m7_planning_package import PACKAGE as M7_PACKAGE, load_rules, methodology_targets
from Api.pilot_plan_admission import PUBLISHER_CONTRACT, _require, project_plan, validate_program
from scripts.plan_specialist_program_release import (
    BATTERY_V04_PACKAGE, BATTERY_V04_RUNTIME, BATTERY_V06_PACKAGE, BATTERY_V06_RUNTIME,
    ROOT, build_release_artifacts, build_trace,
)


RELEASE_DIR = ROOT / "assessment_definitions/planning/specialist_pilot_release/2.0"
SOURCE_FIELDS = ("methodology_version_id", "scenario_version_id", "prompt_bundle_checksum")
ROLE = "specialist_expert"
# Api/m7_cycle_planner.py at 4b1154e5b8f6277bc19faaf34638d6ae0b59adbb.
# The v2.0 proposal binds that file; build_plan also replays both approved routes.
V20_PLANNER_SHA256 = "72f2d44c363235b4eb899195948f1a4008c9c5e3e693bbde62f1c5a268991b39"


def load_release(directory: Path) -> tuple[dict, dict]:
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    proposal_bytes = (directory / "m7-proposal.json").read_bytes()
    _require(manifest["contract"] == "specialist_pilot_release/1"
             and digest(proposal_bytes) == manifest["proposal_sha256"], "RELEASE_SOURCE_CHECKSUM_MISMATCH")
    proposal = json.loads(proposal_bytes)
    content = {key: value for key, value in proposal.items() if key not in ("decisions", "proposal_content_sha")}
    _require(digest(canonical_bytes(content).removesuffix(b"\n"))
             == proposal["proposal_content_sha"] == manifest["proposal_content_sha"],
             "RELEASE_PROPOSAL_CHECKSUM_MISMATCH")
    manifest["manifest_sha256"] = digest(manifest_bytes)
    return manifest, proposal


def release_materials(proposal: dict) -> tuple[dict, dict, dict, dict]:
    build_trace(BATTERY_V04_PACKAGE, BATTERY_V04_RUNTIME)
    package = json.loads((BATTERY_V04_PACKAGE / "case-package.json").read_bytes())
    runtime = load_runtime_rule_package(
        BATTERY_V04_RUNTIME, package["cases"], expected_case_package_version=package["version"],
    )
    for case in package["cases"]:
        case["status"] = "FROZEN"
    manifest, execution_rules = build_release_artifacts(
        package, runtime, usage_scope="assessment", package_dir=BATTERY_V04_PACKAGE,
    )
    sources = proposal["source_refs"]
    _require(sources["bank_release"] == {
        "id": manifest["id"], "version": manifest["version"],
        "checksum": checksum({"package": package, "manifest": manifest}),
    } and manifest["dependencies"]["m2"] == sources["m2_checksum"], "RELEASE_BANK_MISMATCH")
    actual_cases = {case["case_id"]: (case["version"], checksum(case),
        {target["indicator_id"] for target in case["indicator_targets"]}) for case in package["cases"]}
    proposed_cases = {case["case_id"]: (case["case_version"], case["case_checksum"], set(case["target_ids"]))
                      for case in proposal["cases"]}
    _require(len(proposal["cases"]) == len(actual_cases) == 9 and actual_cases == proposed_cases,
             "RELEASE_CASE_SET_MISMATCH")
    return package, manifest, execution_rules, runtime


def release_configuration(connection, *, code: str, baseline: dict, catalog_id: int,
                          publisher: int, reason: str) -> dict:
    config = connection.execute("SELECT * FROM assessment_configurations WHERE code=%s", (code,)).fetchone()
    if config is None:
        config = assessment_authoring_service.create_configuration(
            connection, code=code, name=baseline["name"], methodology_version_id=baseline["methodology_version_id"],
            scenario_version_id=baseline["scenario_version_id"], catalog_version_id=catalog_id,
            actor_user_id=publisher, comment=reason,
        )
    _require(config["status"] in {"draft", "published"} and config["catalog_version_id"] == catalog_id
             and not config["is_default"]
             and all(config[key] == baseline[key] for key in SOURCE_FIELDS[:2]), "CONFIGURATION_SCOPE_MISMATCH")
    if config["status"] == "draft":
        config = assessment_authoring_service.publish_configuration(
            connection, configuration_id=config["id"], make_default=False, actor_user_id=publisher, comment=reason,
        )
    _require(isinstance(config["prompt_bundle_json"], dict)
             and definition_checksum(config["prompt_bundle_json"]) == config["prompt_bundle_checksum"],
             "CONFIGURATION_SCOPE_MISMATCH")
    return dict(config)


def build_plan(connection, *, manifest: dict, proposal: dict, configuration: dict, catalog: dict,
               baseline: dict, role: dict, publisher_release: dict) -> tuple[dict, list[int]]:
    catalog_ref = {"catalog_id": catalog["catalog_id"], "catalog_version": catalog["catalog_version"],
                   "manifest_checksum": catalog["manifest_checksum"]}
    m2_checksum = proposal["source_refs"]["m2_checksum"]
    _require(catalog["manifest"]["m2_checksum"] == m2_checksum, "FULL_M2_MISMATCH")
    targets = methodology_targets(["K1", "K2", "K3", "K4"])
    planned = set(proposal["planned_target_ids"])
    _require(len(planned) == proposal["planned_target_count"] and proposal["authority_scope"]["base_role"] == ROLE,
             "TARGET_SET_MISMATCH")
    cases = [{"case_id": case["case_id"], "version": case["case_version"],
              "admitted_checksum": case["case_checksum"], "target_ids": case["target_ids"]}
             for case in proposal["cases"]]
    cases_by_id = {case["case_id"]: case for case in cases}
    route = [{**cases_by_id[row["case_id"]], "position": position, "pre_generate": False}
             for position, row in enumerate(proposal["routes"]["mandate_confirmed"]["route"], 1)]
    observed = [{"case_id": row["case_id"], "case_version": row["case_version"],
                 "indicator_id": row["indicator_id"], "m2_version": row["m2_version"],
                 "observation_condition": row["condition"], "actual_opportunity": row["actual_opportunity"]}
                for row in proposal["case_observation_conditions"]]
    expected_pairs = {(case["case_id"], indicator) for case in cases for indicator in case["target_ids"]}
    _require(len(observed) == len(expected_pairs)
             and {(row["case_id"], row["indicator_id"]) for row in observed} == expected_pairs,
             "OBSERVABILITY_MISMATCH")
    limits = proposal["proposed_limits_carried_from_0_3"]
    configuration_ref = {key: configuration[key] for key in ("id", "code", *SOURCE_FIELDS)}
    sources = {key: configuration[key] for key in SOURCE_FIELDS}
    program = {**manifest["program"], "assessment_configuration_id": configuration["id"],
               "catalog_version_id": catalog["id"], "source_refs_json": sources}
    design = {
        "proposal_id": proposal["proposal_id"], "version": proposal["proposal_version"],
        "program": {key: baseline[key] for key in ("code", "name", "version", "assignment_ref", "mode")},
        "release_program": program, "configuration": configuration_ref, "catalog_ref": catalog_ref,
        "role_refs": [role], "m2_checksum": m2_checksum, "full_m2_matrix": targets,
        "full_m2_count": proposal["full_m2_count"], "proposed_target_ids": proposal["planned_target_ids"],
        "absent_target_ids": proposal["outside_plan_target_ids"], "proposed_primary_route": route,
        "cases": cases, "observation_occurrences": observed,
        "catalog_design_occurrences": proposal["observation_occurrences"],
        "timing_basis": {"time_budget_seconds": limits["active_seconds"],
                         "calendar_window_seconds": limits["calendar_seconds"]},
    }
    if "route_requirements" in proposal:
        design["route_requirements"] = proposal["route_requirements"]
    snapshot = {
        "contract": PUBLISHER_CONTRACT, "artifact_id": proposal["proposal_id"],
        "artifact_version": proposal["proposal_version"], "source_manifest_sha256": manifest["manifest_sha256"],
        "participant_notice": proposal["participant_notice_proposal"], "publisher_release": publisher_release,
        "review": {"payload": design, "proposal_payload_checksum": checksum(design),
                   "canonicalization": "compact sorted UTF-8 JSON + LF"},
    }
    snapshot["snapshot_checksum"] = checksum(snapshot)
    program = {**program, "source_refs_json": {**sources, "pilot_plan_admission": snapshot}}
    role_ids = [role["id"]]
    validate_program(program, role_ids, snapshot)
    pilot_plan_binding.validate_case_sources(connection, snapshot, catalog["id"])

    if "route_requirements" in proposal:
        return program, role_ids

    rules = load_rules()
    projection_ref = {"id": catalog["catalog_id"], "version": catalog["catalog_version"],
                      "checksum": catalog["manifest_checksum"], "m2_checksum": m2_checksum}
    for confirmed, key in ((True, "mandate_confirmed"), (False, "mandate_missing")):
        profile = {"user_context": {"regular_tasks": ["Release validation"],
                   "additional_information": {"professional_recommendation": {
                       "confirmed": confirmed, "basis": "Release validation",
                   }}}}
        actual = _catalog(connection, role=ROLE, rules=rules, planned_ids=planned, catalog_db_id=catalog["id"],
                          usage_scope="assessment", battery_profile=profile,
                          battery_scenario_package=ROOT / BATTERY_V04_SCENARIO_CURRENT)
        projected = project_plan(snapshot, targets=targets, catalog=actual, catalog_ref=projection_ref, role_ref=role)
        _require(actual == proposal["routes"][key]["catalog"]
                 and projected["route"] == proposal["routes"][key]["route"], "RELEASE_ROUTE_MISMATCH")
    return program, role_ids


def release(connection, *, directory: Path, publisher: int, principal: str) -> dict:
    manifest, proposal = load_release(directory)
    require_release_publisher(connection, publisher)
    connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                       (f'{manifest["program"]["code"]}@{manifest["program"]["version"]}',))
    baseline = connection.execute("""SELECT p.*, c.methodology_version_id, c.scenario_version_id,
               m.version AS methodology_revision,m.definition_json AS methodology_definition,
               m.checksum AS methodology_checksum
        FROM assessment_program_definitions p JOIN assessment_configurations c ON c.id=p.assessment_configuration_id
        JOIN assessment_methodology_versions m ON m.id=c.methodology_version_id
        WHERE p.code=%s AND p.version=%s AND p.status='published' AND c.status='published' AND m.status='published'""",
        (manifest["program"]["code"], manifest["baseline_version"])).fetchone()
    _require(baseline is not None, "RELEASE_BASELINE_MISSING")
    m2 = load_verified_m2_package()
    expected_methodology = {**m2["methodology"], "version": baseline["methodology_revision"]}
    _require(m2["manifest"]["artifact"]["sha256"] == proposal["source_refs"]["m2_checksum"]
             and definition_checksum(expected_methodology) == baseline["methodology_checksum"]
             and expected_methodology == baseline["methodology_definition"], "FULL_M2_MISMATCH")
    role = connection.execute("""SELECT rv.id,r.code,rv.version,rv.checksum
        FROM assessment_program_allowed_roles a JOIN assessment_role_profile_versions rv ON rv.id=a.role_profile_version_id
        JOIN assessment_role_profiles r ON r.id=rv.role_profile_id
        WHERE a.program_definition_id=%s AND r.code=%s AND r.scope='base'
          AND rv.status='published' AND rv.methodology_version='1.1'""", (baseline["id"], ROLE)).fetchall()
    _require(len(role) == 1, "ROLE_SCOPE_MISMATCH")
    package, bank_manifest, execution_rules, runtime = release_materials(proposal)
    runtime_ref = proposal["source_refs"]["runtime_release"]
    _require(runtime_ref == {"artifact_id": runtime["manifest"]["id"],
                            "artifact_version": runtime["manifest"]["version"],
                            "manifest_checksum": runtime["manifest_checksum"],
                            "rules_checksum": checksum(execution_rules)}, "RELEASE_RUNTIME_MISMATCH")
    scenario = battery_scenario_ref(BATTERY_V04_SCENARIO_CURRENT)
    review = proposal["source_refs"]["review_package"]
    _, _, review_refs = read_as_package(ROOT / review["path"])
    _require(scenario == proposal["source_refs"]["scenario_ref"] and review == review_refs["protocol_package"]
             and digest((M7_PACKAGE / "rules.json").read_bytes()) == proposal["source_refs"]["planning_rules_sha256"]
             and V20_PLANNER_SHA256 == proposal["source_refs"]["planner_sha256"],
             "RELEASE_EXECUTION_SOURCE_MISMATCH")
    imported = import_package(connection, package=package, manifest=bank_manifest, execution_rules=execution_rules)
    package_id = imported["package_db_id"]
    rules = import_runtime_rule_version(connection, runtime, execution_rules, package_db_id=package_id)
    case_ids = [row["id"] for row in connection.execute(
        "SELECT id FROM m5_case_versions WHERE package_id=%s ORDER BY id", (package_id,)
    ).fetchall()]
    catalog_key = (manifest["catalog_id"], manifest["catalog_version"])
    _require(catalog_key[1] == proposal["source_refs"]["isolated_catalog_version"], "RELEASE_CATALOG_MISMATCH")
    published = connection.execute("""SELECT id FROM m5_catalogs WHERE catalog_id=%s AND catalog_version=%s""",
                                   catalog_key).fetchone()
    release_ref = {"archive_sha256": manifest["archive_sha256"], "proposal_content_sha": manifest["proposal_content_sha"]}
    reason = f'Publisher release {proposal["proposal_id"]} {proposal["proposal_version"]}'
    if published is None:
        published = {"id": publish_catalog(
            connection, catalog_id=catalog_key[0], catalog_version=catalog_key[1],
            package_db_id=package_id, case_version_ids=case_ids, usage_scope="assessment",
            published_by=publisher, decision_basis=reason, idempotency_key="@".join(catalog_key),
            runtime_rule_version_id=rules["id"], review_package=review, scenario_ref=scenario,
            publisher_release={**release_ref, "principal": principal,
                               "case_checksums": {case["case_id"]: case["case_checksum"] for case in proposal["cases"]}},
        )["catalog_db_id"]}
    catalog = catalog_readback(connection, published["id"])
    readback = catalog["manifest"]
    runtime_ids = connection.execute("""SELECT DISTINCT runtime_rule_version_id
        FROM m5_catalog_case_versions WHERE catalog_db_id=%s""", (catalog["id"],)).fetchall()
    _require(catalog["status"] == "published" and readback["organization_id"] is None
             and readback["usage_scope"] == "assessment" and readback["case_version_ids"] == case_ids
             and readback["package_ref"] == proposal["source_refs"]["bank_release"]
             and readback["runtime_rule_ref"] == runtime_ref
             and runtime_ids == [{"runtime_rule_version_id": rules["id"]}]
             and readback["scenario_ref"] == scenario and readback["review_package"] == review,
             "RELEASE_CATALOG_MISMATCH")
    configuration = release_configuration(connection, code=manifest["configuration_code"], baseline=baseline,
                                          catalog_id=catalog["id"], publisher=publisher, reason=reason)
    existing = connection.execute("""SELECT * FROM assessment_program_definitions WHERE code=%s AND version=%s""",
                                  (manifest["program"]["code"], manifest["program"]["version"])).fetchone()
    release_actor = {"publisher_user_id": publisher, "principal": principal}
    if existing is not None:
        previous = pilot_plan_binding.validate_published_program(connection, dict(existing))
        recorded = previous.get("publisher_release", {})
        _require(all(recorded.get(key) == value for key, value in release_ref.items()), "RELEASE_PROGRAM_MISMATCH")
        release_actor = {key: recorded[key] for key in release_actor}
    program, role_ids = build_plan(connection, manifest=manifest, proposal=proposal, configuration=configuration,
                                   catalog=catalog, baseline=baseline, role=dict(role[0]),
                                   publisher_release={**release_ref, **release_actor})
    published_program = assessment_programs.publish_definition(
        connection, program=program, role_ids=role_ids, publisher_user_id=publisher,
    )
    pilot_plan_binding.validate_published_program(connection, published_program)
    return {"program_id": published_program["id"], "program_version": published_program["version"],
            "catalog_db_id": catalog["id"], "catalog_version": catalog["catalog_version"],
            "configuration_id": configuration["id"], "publisher_user_id": published_program["published_by_user_id"],
            "publisher_principal": release_actor["principal"], "published_at": published_program["published_at"],
            "proposal_content_sha": manifest["proposal_content_sha"], "source_refs": proposal["source_refs"],
            "result": "existing" if existing is not None else "published"}


def publish_v06_program(connection, *, publisher: int, principal: str) -> dict:
    """Bind the already admitted 1.4.5 catalog to a separate program version."""
    require_release_publisher(connection, publisher)
    connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("specialist_pilot@2.1",))
    baseline = connection.execute("""SELECT p.*, c.methodology_version_id, c.scenario_version_id
        FROM assessment_program_definitions p JOIN assessment_configurations c ON c.id=p.assessment_configuration_id
        WHERE p.code='specialist_pilot' AND p.version='2.0' AND p.status='published' AND c.status='published'""").fetchone()
    _require(baseline is not None, "RELEASE_BASELINE_MISSING")
    previous = pilot_plan_binding.validate_published_program(connection, baseline)
    design = previous["review"]["payload"]
    _require(len(design["role_refs"]) == 1 and len(design["proposed_target_ids"]) == 39,
             "RELEASE_BASELINE_MISMATCH")

    catalog_row = connection.execute("""SELECT id FROM m5_catalogs
        WHERE catalog_id='specialist-pilot' AND catalog_version='1.4.5'""").fetchone()
    _require(catalog_row is not None, "RELEASE_ADMITTED_CATALOG_REQUIRED")
    catalog = catalog_readback(connection, catalog_row["id"])
    catalog_manifest = catalog["manifest"]
    package = json.loads((BATTERY_V06_PACKAGE / "case-package.json").read_bytes())
    runtime = load_runtime_rule_package(
        BATTERY_V06_RUNTIME, package["cases"], expected_case_package_version=package["version"],
    )
    for case in package["cases"]:
        case["status"] = "FROZEN"
    bank_manifest, rules = build_release_artifacts(
        package, runtime, usage_scope="assessment", package_dir=BATTERY_V06_PACKAGE,
    )
    _, _, review_refs = read_as_package(ROOT / M5_BATTERY_PILOT_REVIEW_PACKAGES["7.0.0"])
    _require(catalog["status"] == "published" and catalog_manifest["usage_scope"] == "assessment"
             and catalog_manifest["organization_id"] is None
             and catalog_manifest.get("battery_pilot") is True
             and catalog_manifest["package_ref"] == {
                 "id": bank_manifest["id"], "version": bank_manifest["version"],
                 "checksum": checksum({"package": package, "manifest": bank_manifest}),
             }
             and catalog_manifest["runtime_rule_ref"] == {
                 "artifact_id": runtime["manifest"]["id"], "artifact_version": runtime["manifest"]["version"],
                 "manifest_checksum": runtime["manifest_checksum"], "rules_checksum": checksum(rules),
             }
             and catalog_manifest["scenario_ref"] == battery_scenario_ref(BATTERY_V06_SCENARIO_PACKAGE)
             and catalog_manifest["review_package"] == review_refs["protocol_package"],
             "RELEASE_CATALOG_MISMATCH")
    planned = design["proposed_target_ids"]
    cases = [{
        "case_id": case["case_id"], "case_version": case["version"], "case_checksum": checksum(case),
        "target_ids": [target["indicator_id"] for target in case["indicator_targets"]],
    } for case in package["cases"]]
    observations = [{
        "case_id": case["case_id"], "case_version": case["version"], "indicator_id": target["indicator_id"],
        "m2_version": target["m2_version"], "condition": target["observation_condition"],
        "actual_opportunity": "NOT_RUN",
    } for case in package["cases"] for target in case["indicator_targets"]]
    _require({row["indicator_id"] for row in observations} == set(planned), "TARGET_SET_MISMATCH")
    proposal = {
        "proposal_id": "specialist-pilot-m5-v0.6", "proposal_version": "2.1",
        "source_refs": {"m2_checksum": design["m2_checksum"]},
        "authority_scope": {"base_role": ROLE}, "cases": cases,
        "planned_target_ids": planned, "planned_target_count": len(planned),
        "outside_plan_target_ids": design["absent_target_ids"], "full_m2_count": design["full_m2_count"],
        "routes": {"mandate_confirmed": {"route": design["proposed_primary_route"]}},
        "route_requirements": {"minimum_target_count": len(planned), "required_target_ids": planned},
        "case_observation_conditions": observations, "observation_occurrences": len(observations),
        "participant_notice_proposal": previous["participant_notice"],
        "proposed_limits_carried_from_0_3": {
            "active_seconds": design["timing_basis"]["time_budget_seconds"],
            "calendar_seconds": design["timing_basis"]["calendar_window_seconds"],
        },
    }
    version = "2.1"
    release_ref = {
        "archive_sha256": bank_manifest["battery_source"]["provenance"]["battery_archive_sha256"],
        "proposal_content_sha": checksum(proposal),
    }
    configuration = release_configuration(
        connection, code="specialist_pilot_v2_1", baseline=baseline, catalog_id=catalog["id"], publisher=publisher,
        reason="M5 v0.6 · назначаемая версия программы",
    )
    existing = connection.execute("""SELECT * FROM assessment_program_definitions
        WHERE code='specialist_pilot' AND version=%s""", (version,)).fetchone()
    actor = {"publisher_user_id": publisher, "principal": principal}
    if existing is not None:
        recorded = pilot_plan_binding.validate_published_program(connection, existing)["publisher_release"]
        _require(all(recorded.get(key) == value for key, value in release_ref.items()), "RELEASE_PROGRAM_MISMATCH")
        actor = {key: recorded[key] for key in actor}
    manifest = {
        "program": {**{key: baseline[key] for key in ("code", "name", "assignment_ref", "mode")}, "version": version},
        "manifest_sha256": digest((BATTERY_V06_PACKAGE / "manifest.json").read_bytes()),
    }
    program, role_ids = build_plan(connection, manifest=manifest, proposal=proposal, configuration=configuration,
                                   catalog=catalog, baseline=baseline, role=design["role_refs"][0],
                                   publisher_release={**release_ref, **actor})
    published = assessment_programs.publish_definition(
        connection, program=program, role_ids=role_ids, publisher_user_id=publisher,
    )
    pilot_plan_binding.validate_published_program(connection, published)
    return {"program_id": published["id"], "program_version": published["version"],
            "catalog_db_id": catalog["id"], "catalog_version": catalog["catalog_version"],
            "configuration_id": configuration["id"], "result": "existing" if existing else "published"}


def main() -> int:
    from Api.database import get_connection

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publisher-user-id", type=int, required=True)
    parser.add_argument("--release-dir", type=Path, default=RELEASE_DIR)
    parser.add_argument("--database", default="agent4k_test")
    parser.add_argument("--bind-v0.6", dest="bind_v0_6", action="store_true",
                        help="Publish program 2.1 from the already admitted specialist-pilot@1.4.5 catalog.")
    args = parser.parse_args()
    principal = pwd.getpwuid(os.geteuid()).pw_name
    with get_connection() as connection:
        current = connection.execute("SELECT current_database() AS name").fetchone()["name"]
        if current != args.database or "test" not in current.lower():
            raise SystemExit("Expected the explicitly named TEST database.")
        if args.bind_v0_6:
            result = publish_v06_program(connection, publisher=args.publisher_user_id, principal=principal)
        else:
            result = release(connection, directory=args.release_dir, publisher=args.publisher_user_id, principal=principal)
        connection.commit()
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
