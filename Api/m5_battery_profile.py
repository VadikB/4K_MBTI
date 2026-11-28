"""Source-bound applicability of the v0.6 specialist cases before AS generation."""
from __future__ import annotations

import json

from Api.m5_case_runtime import checksum


FIELDS = ("regular_tasks", "decision_situations", "constraints_and_interactions")
STATES = {"supported", "contradicted", "unspecified"}
PILOT_PACKAGE_VERSION = "0.9-pilot.1"
# These pinned rules used only scalar answers when computing the source checksum.
STRING_ONLY_RULES = frozenset({"1.10.0", "1.10.1", "1.10.2", "1.10.3"})


def _sources(profile: dict, *, allow_lists: bool) -> dict[str, str | list[str]]:
    context = profile.get("user_context") or {}
    sources = {}
    for field in FIELDS:
        value = context.get(field)
        if isinstance(value, str) and value.strip():
            sources[field] = value
        elif (allow_lists and isinstance(value, list) and all(isinstance(item, str) for item in value)
              and any(item.strip() for item in value)):
            sources[field] = value
    return sources


def _subject(design: dict) -> dict:
    policy = design["profile_fit"]
    return {"case_id": policy["case_id"], "scenario_ref": design["ref"], "criteria": policy["criteria"]}


def _receipt(subject: dict, source: dict, rows: dict) -> dict:
    criteria = subject["criteria"]
    if not isinstance(rows, dict) or rows.keys() != criteria.keys():
        raise ValueError("M5_BATTERY_PROFILE_REVIEW_INVALID")
    source_paths = {}
    for key, item in rows.items():
        if (not isinstance(item, dict) or item.keys() != {"status", "field", "quote"}
                or not isinstance(item["status"], str) or item["status"] not in STATES):
            raise ValueError("M5_BATTERY_PROFILE_REVIEW_INVALID")
        field, quote = item["field"], item["quote"]
        if item["status"] == "unspecified":
            valid = field is None and quote is None
        else:
            valid = (isinstance(field, str) and field in criteria[key]["fields"] and field in source
                     and isinstance(quote, str) and bool(quote.strip()))
            if valid:
                value = source[field]
                if isinstance(value, list):
                    paths = [f"user_context/{field}/{index}" for index, text in enumerate(value) if quote in text]
                    if paths:
                        source_paths[key] = paths
                    valid = bool(paths)
                else:
                    valid = quote in value
        if not valid:
            raise ValueError(f"M5_BATTERY_PROFILE_REVIEW_EVIDENCE_INVALID:{subject['case_id']}:{key}")
    receipt = {"subject_checksum": checksum(subject), "profile_sources_checksum": checksum(source), "evidence": rows}
    if source_paths:
        receipt["evidence_source_paths"] = source_paths
    for state, status, reason_key in (("contradicted", "incompatible", "incompatibility"),
                                      ("unspecified", "clarification_required", "question")):
        for key, criterion in criteria.items():
            if rows[key]["status"] == state:
                return {**receipt, "status": status, "criterion": key, "message": criterion[reason_key]}
    return {**receipt, "status": "applicable"}


def verified_receipt(profile: dict, design: dict, reviewed: dict | None) -> dict:
    subject = _subject(design)
    sources = _sources(profile, allow_lists=design["ref"]["version"] not in STRING_ONLY_RULES)
    if reviewed is None:
        rows = {key: {"status": "unspecified", "field": None, "quote": None} for key in subject["criteria"]}
        return _receipt(subject, sources, rows)
    if not isinstance(reviewed, dict):
        raise ValueError("M5_BATTERY_PROFILE_REVIEW_INVALID")
    actual = _receipt(subject, sources, reviewed.get("evidence"))
    if actual != reviewed:
        raise ValueError("M5_BATTERY_PROFILE_REVIEW_SOURCE_MISMATCH")
    return actual


def review(profile: dict, designs: list[dict], gateway, *, operation_id: str) -> dict:
    if not designs:
        return {}
    source_modes = {design["ref"]["version"] not in STRING_ONLY_RULES for design in designs}
    if len(source_modes) != 1:
        raise ValueError("M5_BATTERY_PROFILE_REVIEW_INVALID")
    sources = _sources(profile, allow_lists=source_modes.pop())
    if not sources:
        return {design["profile_fit"]["case_id"]: verified_receipt(profile, design, None) for design in designs}
    subjects = {_subject(design)["case_id"]: _subject(design) for design in designs}
    instructions = {design["profile_fit"]["instruction"] for design in designs}
    if len(instructions) != 1:
        raise ValueError("M5_BATTERY_PROFILE_REVIEW_INVALID")
    user = {"profile": sources, "cases": {key: subject["criteria"] for key, subject in subjects.items()}}
    raw = gateway.chat([
        {"role": "system", "content": instructions.pop()},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ], temperature=0.0, routing_key=f"m5-v06-profile-fit:{operation_id}", response_format={"type": "json_object"})
    try:
        result = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("M5_BATTERY_PROFILE_REVIEW_INVALID") from exc
    if (not isinstance(result, dict) or result.keys() != {"cases"}
            or not isinstance(result["cases"], dict) or result["cases"].keys() != subjects.keys()):
        raise ValueError("M5_BATTERY_PROFILE_REVIEW_INVALID")
    return {key: _receipt(subject, sources, result["cases"][key]) for key, subject in subjects.items()}


def configuration_designs(connection, *, configuration_id: int) -> list[dict]:
    """Read only the newly assigned bank. Old Cycles never run a new review."""
    from Api.cycle_execution_manifest import ROOT, battery_scenario_path
    from Api.m5_battery_contract import load_scenario

    rows = connection.execute("""SELECT p.package_version, catalog.manifest_json, cv.content_json
        FROM assessment_configurations c
        JOIN m5_catalogs catalog ON catalog.id=c.catalog_version_id
        JOIN m5_catalog_case_versions member ON member.catalog_db_id=catalog.id
        JOIN m5_case_versions cv ON cv.id=member.case_version_id
        JOIN m5_packages p ON p.id=cv.package_id
        WHERE c.id=%s AND p.package_version=%s ORDER BY cv.case_id""", (configuration_id, PILOT_PACKAGE_VERSION)).fetchall()
    designs = []
    for row in rows:
        path = battery_scenario_path(row["package_version"], row["manifest_json"]["scenario_ref"])
        design = load_scenario(row["content_json"], ROOT / path, pilot=True)
        if "profile_fit" in design:
            designs.append(design)
    return designs
