"""Versioned pilot design snapshot, activated only by a published ProgramDefinition.

This is not AS admission. No database, provider, publication or implicit file lookup
is performed by validation. Historical review bytes/statuses remain untouched.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from Api.m5_case_runtime import checksum

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "m7_pilot_plan_admission/1"
PUBLISHER_CONTRACT = "m7_pilot_plan_admission/2"


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError("PILOT_PLAN_" + code)


def _hash(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def pairs(rows: list[dict]) -> set[tuple[str, str]]:
    _require(isinstance(rows, list) and bool(rows), "TARGET_SET_INVALID")
    values = [(row["indicator_id"], row["m2_version"]) for row in rows]
    _require(all(isinstance(a, str) and a and isinstance(b, str) and b for a, b in values)
             and len(set(values)) == len(values) and len({a for a, _ in values}) == len(values), "TARGET_SET_INVALID")
    return set(values)


def _validate_legacy_review(snapshot: dict, design: dict, review: dict) -> None:
    decision = snapshot["owner_decision"]
    _require(snapshot["owner_decision_ref"]["content_checksum"] == checksum(decision)
             and _hash(snapshot["owner_decision_ref"].get("sha256")),
             "DECISION_CHECKSUM_MISMATCH")
    _require(decision["proposal_id"] == design["proposal_id"]
             and decision["proposal_version"] == design["version"]
             and decision["proposal_payload_checksum"] == review["proposal_payload_checksum"],
             "DECISION_SCOPE_MISMATCH")
    _require(bool(decision.get("human_owner")) and bool(decision.get("decision_id"))
             and decision.get("origin", {}).get("type") == "current_chat_user_message"
             and bool(decision["origin"].get("user_reply_verbatim")), "HUMAN_DECISION_MISSING")
    for role, ids in (("productologist", ["P1", "P2", "P3"]),
                      ("methodologist", ["M1", "M2", "M3", "M4"])):
        _require(decision.get(role, {}).get("status") == "APPROVED_FOR_EXACT_PROPOSAL"
                 and decision[role].get("decision_ids") == ids, "HUMAN_DECISION_MISSING")
    for name, reference in snapshot["source_files"].items():
        _require(_hash(reference) and decision["reviewed_files_sha256"].get(name) == reference,
                 "REVIEW_SOURCE_MISMATCH")
    _require(bool(snapshot["source_files"]), "REVIEW_SOURCE_MISMATCH")


def _validate_legacy_summary(decision: dict, design: dict) -> None:
    summary = decision["accepted_plan_summary"]
    timing = design["timing_basis"]
    _require(summary["full_m2_count"] == len(design["full_m2_matrix"])
             and summary["planned_target_count"] == len(design["proposed_target_ids"])
             and summary["outside_plan_target_count"] == len(design["absent_target_ids"])
             and summary["primary_route"] == [row["case_id"] for row in design["proposed_primary_route"]]
             and summary["source_observation_row_count"] == len(design["observation_occurrences"])
             and all(summary[name] == timing[name] for name in
                     ("time_budget_seconds", "calendar_window_seconds")), "DECISION_SCOPE_MISMATCH")


def validate_snapshot(snapshot: dict) -> dict:
    """Return the accepted design; an unchecked client JSON never grants start."""
    try:
        _require(isinstance(snapshot, dict) and snapshot.get("contract") in {CONTRACT, PUBLISHER_CONTRACT},
                 "CONTRACT_UNSUPPORTED")
        _require(all(isinstance(snapshot.get(key), str) and bool(snapshot[key].strip())
                     for key in ("artifact_id", "artifact_version"))
                 and _hash(snapshot.get("source_manifest_sha256")), "ARTIFACT_REF_INVALID")
        content = {key: value for key, value in snapshot.items() if key != "snapshot_checksum"}
        _require(checksum(content) == snapshot.get("snapshot_checksum"), "SNAPSHOT_CHECKSUM_MISMATCH")
        review = snapshot["review"]
        design = review["payload"]
        # The review contract includes LF; use it, not an invented hash equality
        # between the reviewed payload and the encompassing runtime snapshot.
        _require(review["canonicalization"] == "compact sorted UTF-8 JSON + LF"
                 and checksum(design) == review["proposal_payload_checksum"], "REVIEW_CHECKSUM_MISMATCH")
        if snapshot["contract"] == CONTRACT:
            _validate_legacy_review(snapshot, design, review)
        else:
            release = snapshot["publisher_release"]
            _require("release_program" in design
                     and snapshot.get("owner_decision") is None
                     and type(release.get("publisher_user_id")) is int
                     and release["publisher_user_id"] > 0
                     and bool(release.get("principal"))
                     and _hash(release.get("archive_sha256"))
                     and _hash(release.get("proposal_content_sha")),
                     "PUBLISHER_RELEASE_INVALID")
        _require(isinstance(snapshot.get("participant_notice"), str) and bool(snapshot["participant_notice"].strip()),
                 "PARTICIPANT_NOTICE_REQUIRED")
        full = pairs(design["full_m2_matrix"])
        full_ids = {indicator for indicator, _ in full}
        planned = design["proposed_target_ids"]
        outside = design["absent_target_ids"]
        if "route_requirements" in design:
            requirements = design["route_requirements"]
            _require("release_program" in design and isinstance(requirements, dict)
                     and requirements.keys() == {"minimum_target_count", "required_target_ids"}
                     and type(requirements["minimum_target_count"]) is int
                     and 0 < requirements["minimum_target_count"] <= len(planned)
                     and isinstance(requirements["required_target_ids"], list)
                     and len(set(requirements["required_target_ids"])) == len(requirements["required_target_ids"])
                     and set(requirements["required_target_ids"]) <= set(planned), "ROUTE_REQUIREMENTS_INVALID")
        _require(len(full) == design["full_m2_count"]
                 and len(planned) == len(set(planned))
                 and len(outside) == len(set(outside))
                 and bool(planned) and set(planned).isdisjoint(outside)
                 and set(planned) | set(outside) == full_ids, "TARGET_SET_MISMATCH")
        route = design["proposed_primary_route"]
        cases = {(row["case_id"], row["version"]): row for row in design["cases"]}
        _require(bool(route) and len(cases) == len(design["cases"]), "ROUTE_INVALID")
        _require(len({row["case_id"] for row in route}) == len(route), "ROUTE_INVALID")
        for position, row in enumerate(route, 1):
            original = cases[(row["case_id"], row["version"])]
            _require(row["position"] == position and row["pre_generate"] is False
                     and all(row.get(key) == value for key, value in original.items()), "ROUTE_INVALID")
        _require(set().union(*(set(row["target_ids"]) for row in route)) == set(planned),
                 "ROUTE_TARGET_MISMATCH")
        opportunities = design["observation_occurrences"]
        versions = dict(full)
        for row in opportunities:
            _require((row["case_id"], row["case_version"]) in cases
                     and row["indicator_id"] in cases[(row["case_id"], row["case_version"])]["target_ids"]
                     and versions.get(row["indicator_id"]) == row["m2_version"]
                     and bool(row["observation_condition"])
                     and row["actual_opportunity"] == "NOT_RUN", "OBSERVABILITY_MISMATCH")
        _require(len(opportunities) == design["catalog_design_occurrences"], "OBSERVABILITY_MISMATCH")
        timing = design["timing_basis"]
        _require(all(type(timing[name]) is int and timing[name] > 0
                     for name in ("time_budget_seconds", "calendar_window_seconds")), "TIMING_INVALID")
        if snapshot["contract"] == CONTRACT:
            _validate_legacy_summary(snapshot["owner_decision"], design)
        else:
            _require(all(_hash(case.get("admitted_checksum")) for case in cases.values()),
                     "CASE_CHECKSUM_MISMATCH")
        return deepcopy(design)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("PILOT_PLAN_SNAPSHOT_INVALID") from exc


def build_snapshot(package: Path, *, root: Path = ROOT) -> dict:
    """Offline construction only. A draft package is never runtime authorization."""
    manifest = json.loads((package / "manifest.json").read_bytes())
    _require(manifest.get("contract") == CONTRACT and manifest.get("status") == "draft",
             "PACKAGE_INVALID")
    loaded = {}
    for name in ("review", "owner_decision"):
        ref = manifest["sources"][name]
        path = (root / ref["path"]).resolve()
        _require(path.is_relative_to(root.resolve()), "SOURCE_PATH_INVALID")
        data = path.read_bytes()
        _require(hashlib.sha256(data).hexdigest() == ref["sha256"], "SOURCE_CHECKSUM_MISMATCH")
        loaded[name] = json.loads(data)
    notice_ref = manifest["notice_source"]
    notice_path = (root / notice_ref["path"]).resolve()
    _require(notice_path.is_relative_to(root.resolve()), "SOURCE_PATH_INVALID")
    notice_bytes = notice_path.read_bytes()
    _require(hashlib.sha256(notice_bytes).hexdigest() == notice_ref["sha256"], "SOURCE_CHECKSUM_MISMATCH")
    notice = manifest["participant_notice"]
    _require(notice in " ".join(notice_bytes.decode("utf-8").split()), "PARTICIPANT_NOTICE_SOURCE_MISMATCH")
    result = {"contract": CONTRACT, "artifact_id": manifest["id"], "artifact_version": manifest["version"],
              "source_manifest_sha256": hashlib.sha256((package / "manifest.json").read_bytes()).hexdigest(),
              "owner_decision_ref": {**manifest["sources"]["owner_decision"],
                                     "content_checksum": checksum(loaded["owner_decision"])},
              "participant_notice": notice,
              **loaded, "source_files": {manifest["sources"]["review"]["path"]:
                                         manifest["sources"]["review"]["sha256"],
                                         notice_ref["path"]: notice_ref["sha256"]}}
    result["snapshot_checksum"] = checksum(result)
    validate_snapshot(result)
    return result


def validate_program(program: dict, role_ids: list[int], snapshot: dict) -> dict:
    """Only a new version with unchanged accepted baseline sources may opt in."""
    design = validate_snapshot(snapshot)
    baseline = design["program"]
    target = design.get("release_program")
    for name in ("code", "name", "assignment_ref", "mode"):
        _require(program.get(name) == baseline[name], "PROGRAM_SCOPE_MISMATCH")
    for name in ("assessment_configuration_id", "catalog_version_id"):
        _require(program.get(name) == (target or baseline)[name], "PROGRAM_SCOPE_MISMATCH")
    _require(isinstance(program.get("version"), str) and bool(program["version"].strip())
             and program["version"] != baseline["version"], "NEW_PROGRAM_VERSION_REQUIRED")
    if target is not None:
        _require(program["version"] == target["version"], "PROGRAM_SCOPE_MISMATCH")
    sources = program.get("source_refs_json") or {}
    _require({key: value for key, value in sources.items() if key != "pilot_plan_admission"}
             == (target or baseline)["source_refs_json"], "PROGRAM_SCOPE_MISMATCH")
    _require(set(role_ids) == {role["id"] for role in design["role_refs"]}, "ROLE_SCOPE_MISMATCH")
    return design


def project_eligible_route(catalog: list[dict], targets: list[dict], requirements: dict) -> dict:
    """Recompute the whole route and retain the reasons for the advertised coverage gap."""
    from Api.m7_cycle_planner import ranked_route

    route, missing = ranked_route(catalog, targets)
    covered = {row["indicator_id"] for row in targets} - missing
    required_missing = set(requirements["required_target_ids"]) - covered
    excluded = [{"case_id": row["case_id"], "case_version": row["case_version"],
                 "reasons": row["reasons"], **({key: row["profile_fit"][key] for key in ("status", "message")}
                                               if row.get("profile_fit", {}).get("status") in {
                                                   "incompatible", "clarification_required"} else {})}
                for row in catalog if not row["eligible"] and (set(row["target_ids"]) & missing)]
    coverage = {"available_target_count": len(covered), "minimum_target_count": requirements["minimum_target_count"],
                "missing_target_ids": sorted(missing), "missing_required_target_ids": sorted(required_missing),
                "excluded_cases": excluded}
    for row in catalog:
        fit = row.get("profile_fit", {})
        if (missing and fit.get("status") == "clarification_required" and len(row["reasons"]) == 1
                and len(covered | set(row["contribution_target_ids"])) >= requirements["minimum_target_count"]
                and required_missing <= set(row["contribution_target_ids"])):
            coverage["clarification_question"] = fit["message"]
            break
    return {"route": route, "covered": covered, "coverage": coverage,
            "admissible": bool(route) and len(covered) >= requirements["minimum_target_count"] and not required_missing}


def project_plan(snapshot: dict, *, targets: list[dict], catalog: list[dict],
                 catalog_ref: dict, role_ref: dict) -> dict:
    """Validate accepted sources and select the exact initial route, not their union."""
    design = validate_snapshot(snapshot)
    _require(pairs(targets) == pairs(design["full_m2_matrix"]), "FULL_M2_MISMATCH")
    _require(catalog_ref["id"] == design["catalog_ref"]["catalog_id"]
             and catalog_ref["version"] == design["catalog_ref"]["catalog_version"]
             and catalog_ref["checksum"] == design["catalog_ref"]["manifest_checksum"]
             and catalog_ref["m2_checksum"] == design["m2_checksum"], "CATALOG_SCOPE_MISMATCH")
    _require(any(role_ref["code"] == item["code"] and str(role_ref["version"]) == str(item["version"])
                 and role_ref["checksum"] == item["checksum"] for item in design["role_refs"]),
             "ROLE_SCOPE_MISMATCH")
    available = {(row["case_id"], row["case_version"]): row for row in catalog}
    _require(set(available) == {(row["case_id"], row["version"]) for row in design["cases"]},
             "CATALOG_CASE_SET_MISMATCH")
    planned_targets = [row for row in targets if row["indicator_id"] in design["proposed_target_ids"]]
    outside = design["absent_target_ids"]
    coverage = None
    if "release_program" in design:
        from Api.m7_cycle_planner import ranked_route

        for expected in design["cases"]:
            actual = available[(expected["case_id"], expected["version"])]
            _require(set(actual["target_ids"]) == set(expected["target_ids"]), "CASE_TARGET_SET_MISMATCH")
        if "route_requirements" in design:
            projection = project_eligible_route(catalog, planned_targets, design["route_requirements"])
            coverage = projection["coverage"]
            if not projection["admissible"]:
                raise ValueError("PILOT_PLAN_PROGRAM_COVERAGE_UNAVAILABLE:" + json.dumps(coverage, ensure_ascii=False))
            route = projection["route"]
            planned_targets = [row for row in planned_targets if row["indicator_id"] in projection["covered"]]
            outside = sorted({row["indicator_id"] for row in targets} - projection["covered"])
        else:
            route, uncovered = ranked_route(catalog, planned_targets)
            _require(bool(route) and not uncovered, "PLANNED_TARGET_GAP")
    else:
        route = []
        for wanted in design["proposed_primary_route"]:
            actual = available[(wanted["case_id"], wanted["version"])]
            _require(actual["eligible"] is True and set(actual["target_ids"]) == set(wanted["target_ids"]),
                     "ROUTE_NOT_ADMITTED")
            route.append({**actual, "purpose_target_ids": wanted["new_purpose_target_ids"],
                          "duration_source": "M5 CaseVersion planned range", "conditional": True, "reserve_for": []})
    return {"planned_targets": planned_targets,
            "outside_plan_target_ids": outside, "route": route,
            **({"route_coverage": coverage} if coverage is not None else {}),
            "timing": {name: design["timing_basis"][name]
                       for name in ("time_budget_seconds", "calendar_window_seconds")}}
