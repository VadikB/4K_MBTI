"""Keep the same case-relevant M4 evidence throughout one PM-03 operation."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re

from Api.cycle_execution_manifest import M5_PARTICIPANT_GROUNDING_PACKAGES, ROOT

CHECK_IDS = frozenset({"common.professional_consistency", "common.authority"})
FINDING = "PARTICIPANT_GROUNDING_MISMATCH"
CASE_AUTHORITY = "case/Паспорт/10 Позиция оцениваемого"

# These are paths in the sanitized, frozen M4 projection, not a taxonomy of professions.
SOURCES = {
    "position": ("user_context/position_or_status",),
    "base_role": ("role_profile/code", "role_profile/base_role_code"),
    "function": ("user_context/regular_tasks", "user_context/decision_situations", "role_profile/card/typical_tasks"),
    "authority": ("user_context/decision_situations", "user_context/regular_tasks",
                  "role_profile/card/independent_authority"),
    "limits": ("user_context/constraints_and_interactions", "role_profile/card/approval_required",
               "role_profile/card/escalation", "role_profile/card/role_constraints",
               "organization_context/general_rules", "organization_context/forbidden_topics",
               "user_context/irrelevant_areas", "user_context/additional_information/constraints"),
    "subject": ("user_context/regular_tasks", "user_context/specialization", "user_context/systems_and_tools",
                "user_context/additional_information/domain",
                "role_profile/card/work_objects", "organization_context/activity_description",
                "organization_context/activities", "organization_context/products_services_programs",
                "organization_context/terminology"),
}


def package_path(version: object) -> Path:
    path = M5_PARTICIPANT_GROUNDING_PACKAGES.get(version) if isinstance(version, str) else None
    if path is None:
        raise ValueError("M5_PARTICIPANT_GROUNDING_PACKAGE_INVALID")
    return ROOT / path


def load_package(directory: Path) -> tuple[dict, dict]:
    raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    files = (
        ("rules", "rules.json"), ("generation", "generation.md"), ("review", "review.md"),
    )
    contents = {key: (directory / name).read_bytes() for key, name in files}
    artifacts = [{"name": name, "sha256": sha256(contents[key]).hexdigest()} for key, name in files]
    if (package_path(manifest.get("version")) != directory
            or (manifest.get("schema_version"), manifest.get("id"), manifest.get("status"), manifest.get("artifacts"))
            != (1, "m5-participant-grounding", "draft", artifacts)):
        raise ValueError("M5_PARTICIPANT_GROUNDING_PACKAGE_INVALID")
    return json.loads(contents["rules"]), {
        "id": manifest["id"], "version": manifest["version"], "checksum": sha256(raw).hexdigest(),
        **{key: {"path": (directory / item["name"]).relative_to(ROOT).as_posix(), "sha256": item["sha256"]}
           for (key, _), item in zip(files, artifacts, strict=True)},
    }


def _source_present(profile: dict, path: str) -> bool:
    value = profile
    for key in path.split("/"):
        value = value.get(key) if isinstance(value, dict) else None
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (tuple, list)):
        return any(isinstance(item, str) and item.strip() for item in value)
    return bool(value)


def has_work_evidence(profile: dict) -> bool:
    return any(_source_present(profile, key) for key in
               ("user_context/regular_tasks", "user_context/decision_situations"))


def build(profile: dict, case_id: str, rules: dict) -> dict:
    policy = rules["case_overrides"].get(case_id, {})
    required = policy.get("requires_work_evidence", False)
    if required and not has_work_evidence(profile):
        raise ValueError("M5_BATTERY_PROFILE_CLARIFICATION_REQUIRED:18/рабочая функция и полномочия")
    position = _position(profile)
    task_first = policy.get("task_first", False)
    return {
        "sources": {name: ["profile/" + path for path in paths if _source_present(profile, path)]
                    for name, paths in SOURCES.items()},
        "requires_work_evidence": required,
        "p00": {"task_first": task_first, "position_available": bool(position and not task_first),
                "position_marker": rules["position_marker"],
                **({"task_opening": policy["task_opening"]} if task_first else {})},
    }


def _position(profile: dict) -> str:
    value = profile["user_context"].get("position_or_status")
    value = value.strip() if isinstance(value, str) else ""
    return value if len(value.splitlines()) == 1 else ""


def bind_p00(candidate: dict, profile: dict, basis: dict, rules: dict) -> dict:
    """Bind the official heading or the case task before checking the whole body."""
    materials = candidate.get("Материалы")
    if not isinstance(materials, list):
        return candidate
    marker = rules["position_marker"]
    opening = basis["p00"].get("task_opening")
    rows = []
    for material in materials:
        if isinstance(material, dict) and material.get("MaterialID") == "P00":
            text = material.get("Текст")
            if isinstance(text, str):
                first, _, body = text.lstrip().partition("\n")
                if first.strip() == marker:
                    heading = (rules["position_prefix"] + _position(profile)
                               if basis["p00"]["position_available"] else "")
                    text = "\n\n".join(filter(None, [heading, body.lstrip()]))
                if opening and text.strip() and not text.lstrip().startswith(opening):
                    text = f"{opening}\n\n{text.lstrip()}"
                material = {**material, "Текст": text}
        rows.append(material)
    return {**candidate, "Материалы": rows}


def check_position_label(candidate: dict, profile: dict, basis: dict, rules: dict, check) -> None:
    materials = candidate.get("Материалы")
    if not isinstance(materials, list):
        return
    marker, prefix = rules["position_marker"], rules["position_prefix"]
    # Only archived v1 inputs used wording as a deterministic rejection.
    archived_pattern = rules.get("unbound_position_pattern")
    allowed = (prefix + _position(profile)
               if basis["p00"]["position_available"] else None)
    for index, material in enumerate(materials):
        if not isinstance(material, dict) or not isinstance(text := material.get("Текст"), str):
            continue
        p00 = material.get("MaterialID") == "P00"
        lines = text.splitlines() if p00 else []
        heading_lines = lines if archived_pattern else lines[:1]
        headings = [(i, line) for i, line in enumerate(heading_lines) if line.startswith(prefix)]
        expected = [(0, allowed)] if p00 and allowed is not None else []
        path = f"candidate_as/Материалы/{index}/Текст"
        check("participant_position_label", marker not in text and (not headings or headings == expected),
              headings or (marker if marker in text else None), path=path,
              expected=expected, reason="Явная подпись берётся из закреплённого профиля в P00.")
        if p00 and archived_pattern:
            declarations = [match.group(1).strip() for match in re.finditer(archived_pattern, text)]
            check("participant_position_declaration", not declarations,
                  [{"phrase": phrase, "subject": "participant"} for phrase in declarations], path=path,
                  expected={"basis_path": "profile/user_context/position_or_status",
                            "correction": "Уберите свободное представление участника и опишите рабочую задачу."},
                  reason="Явная подпись участника допустима через серверный слот.")


def sent_with_basis(messages: list[dict], basis: dict) -> bool:
    for message in messages:
        if message.get("role") != "user":
            continue
        try:
            payload = json.loads(message["content"])
        except (KeyError, TypeError, ValueError):
            continue
        if isinstance(payload, dict) and all(payload.get(key) == value for key, value in basis.items()):
            return True
    return False
