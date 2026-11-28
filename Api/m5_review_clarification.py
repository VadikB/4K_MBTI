"""Contract of a targeted retry for a contradictory M5 review row."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from Api.cycle_execution_manifest import ROOT
from Api.m5_functional_tester import _locate_candidate_path, candidate_path_value, checksum, normalize_results

CLARIFICATION_SUFFIX = ":status-clarification"


def load_response_contract(directory: Path) -> dict:
    raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    prompt = directory / "prompt.md"
    prompt_sha = checksum(prompt.read_bytes())
    if ((manifest.get("id"), manifest.get("version"), manifest.get("schema_version"), manifest.get("status"))
            != ("m5-review-response", "1.0.0", 1, "draft")
            or manifest.get("artifacts") != [{"name": prompt.name, "sha256": prompt_sha}]):
        raise ValueError("M5_REVIEW_RESPONSE_CONTRACT_INVALID")
    return {
        "id": manifest["id"], "version": manifest["version"], "checksum": checksum(raw),
        "instruction": {"path": str(prompt.relative_to(ROOT)), "sha256": prompt_sha},
    }


def response_forms(required_output: dict) -> dict:
    row = required_output["checks"][0]
    return {
        **required_output,
        "checks": [{key: value for key, value in row.items() if key != "findings"}],
        "findings_by_status": {
            "FAIL": row["findings"],
            "PASS|NOT_RUN|INDETERMINATE|TECHNICAL_ERROR": [],
        },
    }


def _review_paths(row: dict) -> list[str]:
    paths = row.get("evidence_paths")
    paths = list(paths) if isinstance(paths, list) else []
    for finding in row["findings"]:
        if isinstance(finding, dict) and isinstance(finding.get("paths"), list):
            paths.extend(finding["paths"])
    adversarial = row.get("adversarial_review")
    conflicts = adversarial.get("candidate_conflicts") if isinstance(adversarial, dict) else None
    if isinstance(conflicts, list):
        paths.extend(conflicts)
    return [path for path in paths if isinstance(path, str)]


def _review_materials(candidate: dict, paths: list[str]) -> dict:
    materials = {}
    for path in paths:
        located = _locate_candidate_path(candidate, path, mixed_paths=True)
        if not located or not located[0] or not located[1]:
            continue
        value = candidate_path_value(candidate, located[0])
        pointer = "/candidate_as" + "".join(
            "/" + token.replace("~", "~0").replace("/", "~1") for token in located[0]
        )
        materials[pointer] = value
    return materials


def clarification_messages(plan: dict, checks: list[dict], *, review_basis: dict, call: dict,
                           initial_messages: list[dict], instruction: str,
                           grounding_review: str | None = None) -> tuple[list[dict], list[dict]]:
    """Build the same scoped second request during preparation and receipt replay."""
    dispatch = call["review_dispatch"]
    normalized = normalize_results(plan, checks, reviewer=dispatch["reviewer"], **review_basis)
    occurrences = Counter(row["check_id"] for row in checks)
    conflicted = {
        row["check_id"]: row["protocol_errors"] for row in normalized
        if occurrences[row["check_id"]] == 1
        and any(error["code"] == "STATUS_FINDINGS_CONFLICT" for error in row["protocol_errors"])
    }
    definitions = [row for row in plan["required_checks"] if row["check_id"] in conflicted]
    if not definitions:
        return [], []

    previous = {row["check_id"]: row for row in checks if row["check_id"] in conflicted}
    candidate = review_basis["candidate_as"]
    previous_rows = []
    for definition in definitions:
        check_id = definition["check_id"]
        row = previous[check_id]
        materials = _review_materials(candidate, _review_paths(row))
        if not materials:
            materials = _review_materials(candidate, definition["finding_evidence_sections"])
        previous_rows.append({
            "original_row": row, "protocol_errors": conflicted[check_id], "related_materials": materials,
        })

    check_ids = [row["check_id"] for row in definitions]
    clarification_id = checksum({"dispatch": dispatch, "response_sha256": call["response_sha256"], "check_ids": check_ids})
    initial_payload = json.loads(initial_messages[-1]["content"])
    required_output = initial_payload["required_output"]
    payload = {
        "review_dispatch": {
            **{key: dispatch[key] for key in ("operation_id", "round", "reviewer", "batch_no", "candidate_sha256", "package")},
            "check_ids": check_ids,
        },
        "clarification_id": clarification_id,
        "previous_rows": previous_rows,
        "applicability_plan": {"required_checks": definitions},
        "required_output": {**required_output, "clarification_id": clarification_id},
    }
    system_messages = [{"role": "system", "content": instruction}]
    if grounding_review and any(row.get("participant_basis_paths") for row in definitions):
        payload.update({key: initial_payload[key] for key in ("profile", "participant_grounding")})
        system_messages.append({"role": "system", "content": grounding_review})
    return [*system_messages, {"role": "user", "content": json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            )}], definitions


def apply_clarification(original: list[dict], clarified: object, messages: list[dict], plan: dict,
                        definitions: list[dict], *, review_basis: dict, reviewer: str) -> tuple[list[dict], list[str]]:
    request = json.loads(messages[-1]["content"])
    if not isinstance(clarified, dict) or clarified.get("clarification_id") != request["clarification_id"]:
        return original, []
    rows = clarified.get("checks")
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or not isinstance(row.get("check_id"), str) for row in rows
    ):
        return original, []
    if Counter(row["check_id"] for row in rows) != Counter(row["check_id"] for row in definitions):
        return original, []

    subplan = {**plan, "required_checks": definitions}
    reviewed = normalize_results(subplan, rows, reviewer=reviewer, **review_basis)
    valid = {row["check_id"] for row in reviewed if row["status"] in {"PASS", "FAIL"} and not row["protocol_errors"]}
    accepted = {row["check_id"]: row for row in rows if row["check_id"] in valid
                and isinstance(row.get("reason"), str) and row["reason"].strip()
                and isinstance(row.get("findings"), list)}
    results = [accepted.get(row["check_id"], row) for row in original]
    accepted_ids = [key for key in request["review_dispatch"]["check_ids"] if key in accepted]
    return results, accepted_ids
