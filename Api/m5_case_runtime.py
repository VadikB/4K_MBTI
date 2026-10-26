"""Техническая сборка и допуск M5 v2 без выбора последовательности M7."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any
from uuid import UUID

from Api.assessment_case_contracts import (
    AdmissionDecisionV2,
    AssessmentSituationV2,
    C34ExecutionEnvelope,
    CaseVersionV2,
    CaseVersionV3,
    QAEvidenceV2,
    VersionRef,
    validate_case_version,
)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def checksum(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def evaluate_admission(case: CaseVersionV2, evidence: list[QAEvidenceV2], policy: dict) -> AdmissionDecisionV2:
    reasons: list[str] = []
    if case.status not in policy["allowed_case_statuses"]:
        reasons.append(f"case_status:{case.status}")
    if case.unresolved_decisions:
        reasons.extend(f"unresolved:{x}" for x in case.unresolved_decisions)
    by_scope = {x.scope: x for x in evidence}
    for scope in policy["required_evidence_scopes"]:
        item = by_scope.get(scope)
        if item is None:
            reasons.append(f"missing_evidence:{scope}")
        elif item.result != "PASS":
            reasons.append(f"evidence_{item.result.lower()}:{scope}")
    return AdmissionDecisionV2(
        admitted=not reasons,
        code="ADMITTED" if not reasons else (
            "CASE_NOT_ADMITTED" if any(x.startswith(("case_status", "unresolved", "missing_evidence:case_", "evidence_not_run:case_", "evidence_fail:case_")) for x in reasons)
            else "AS_NOT_ADMITTED"
        ),
        reasons=reasons,
    )


def _replace_casefold(value: str, source: str, replacement: str) -> str:
    return re.sub(re.escape(source), lambda _: replacement, value, flags=re.IGNORECASE)


def _materialize_v3_presentation(
    case: CaseVersionV3, profile_snapshot: dict, profile_ref: dict, substitutions: list[dict],
) -> dict:
    presentation = case.participant_presentation.model_dump()
    targets: dict[str, list] = {}
    for target in case.participant_presentation.substitution_targets:
        targets.setdefault(target.slot, []).append(target)
    supplied = {str(item.get("slot", "")): item for item in substitutions}
    if len(supplied) != len(substitutions):
        raise ValueError("DUPLICATE_SUBSTITUTION_SLOT")
    unknown = set(supplied) - set(targets)
    if unknown:
        raise ValueError("SUBSTITUTION_TARGET_NOT_ALLOWED:" + ",".join(sorted(unknown)))
    organization_context = profile_snapshot.get("organization_context")
    organization_context = organization_context if isinstance(organization_context, dict) else {}
    usage_rules = str(organization_context.get("organization_name_usage_rules") or "").casefold()
    if "organization_name" in supplied and "не использовать" in usage_rules:
        raise ValueError("ORGANIZATION_NAME_SUBSTITUTION_FORBIDDEN")
    for slot, item in supplied.items():
        replacement = str(item.get("value") or "").strip()
        if not replacement:
            raise ValueError(f"SUBSTITUTION_VALUE_REQUIRED:{slot}")
        if slot == "organization_name" and replacement != str(organization_context.get("name") or "").strip():
            raise ValueError("SUBSTITUTION_VALUE_PROFILE_MISMATCH:organization_name")
        if item.get("source_path") != "organization_context.name" or item.get("source_checksum") != profile_ref.get("checksum"):
            raise ValueError(f"SUBSTITUTION_PROVENANCE_MISMATCH:{slot}")
        for target in targets[slot]:
            if target.path == "introduction":
                presentation["introduction"] = _replace_casefold(
                    presentation["introduction"], target.source_value, replacement,
                )
                continue
            match = re.fullmatch(r"initial_materials\.(\d+)\.text", target.path)
            if match is None:
                raise ValueError(f"UNSUPPORTED_SUBSTITUTION_PATH:{target.path}")
            material = presentation["initial_materials"][int(match.group(1))]
            material["text"] = _replace_casefold(material["text"], target.source_value, replacement)
    presentation.pop("substitution_targets", None)
    presentation["case_id"] = case.case_id
    presentation["case_version"] = case.version
    presentation["substitutions"] = deepcopy(substitutions)
    return presentation


def build_assessment_situation(
    *,
    assessment_situation_id: str,
    cycle_ref: dict,
    session_ref: dict,
    case_value: dict,
    profile_ref: dict,
    profile_snapshot: dict,
    methodology_refs: list[dict],
    substitutions: list[dict],
    qa_evidence: list[dict],
    policy: dict,
    ai_operations: dict | None = None,
) -> tuple[dict, dict]:
    case = validate_case_version(case_value)
    if profile_snapshot.get("base_role") != case.base_role:
        raise ValueError("PROFILE_BASE_ROLE_NOT_APPLICABLE")
    evidence = [QAEvidenceV2.model_validate(x) for x in qa_evidence]
    admission = evaluate_admission(case, evidence, policy)
    if isinstance(case, CaseVersionV3):
        participant_payload = _materialize_v3_presentation(case, profile_snapshot, profile_ref, substitutions)
    else:
        participant_payload = {
            "case_id": case.case_id,
            "case_version": case.version,
            "title": case.title,
            "initial_situation": case.passport["InitialSituation"],
            "trigger": case.passport["Trigger"],
            "assessee_position": case.passport["AssesseePosition"],
            "participants_and_positions": case.passport["ParticipantsAndPositions"],
            "assessee_task": case.passport["AssesseeTask"],
            "conditions_and_constraints": case.passport["ConditionsAndConstraints"],
            "substitutions": deepcopy(substitutions),
        }
    execution_payload = {
        "case_id": case.case_id,
        "case_version": case.version,
        "characters": [x.model_dump() for x in case.characters],
        "materials": [x.model_dump() for x in case.materials],
        "scenario": [x.model_dump() for x in case.scenario],
        "indicator_targets": [x.model_dump() for x in case.indicator_targets],
        "ai_operations": deepcopy(ai_operations or {}),
    }
    execution_checksum = checksum(execution_payload)
    as_value = AssessmentSituationV2(
        assessment_situation_id=assessment_situation_id,
        cycle_ref=cycle_ref,
        session_ref=session_ref,
        case_ref={"id": case.case_id, "version": case.version, "checksum": checksum(case_value)},
        profile_ref=profile_ref,
        methodology_refs=methodology_refs,
        base_role=case.base_role,
        substitutions=substitutions,
        participant_payload=participant_payload,
        execution_payload_ref={"id": f"{assessment_situation_id}:execution", "version": "1", "checksum": execution_checksum},
        planned_minutes=case.planned_max_minutes,
        indicator_targets=case.indicator_targets,
        qa_evidence=evidence,
        admission=admission,
    )
    return as_value.model_dump(), execution_payload


def build_c34_envelope(assessment_situation: dict) -> dict:
    situation = AssessmentSituationV2.model_validate(assessment_situation)
    if not situation.admission.admitted:
        raise ValueError("AS_NOT_ADMITTED")
    return C34ExecutionEnvelope(
        assessment_situation_ref=VersionRef(
            id=situation.assessment_situation_id,
            version="1",
            checksum=checksum(situation.model_dump()),
        ),
        cycle_ref=situation.cycle_ref,
        session_ref=situation.session_ref,
        execution_payload_ref=situation.execution_payload_ref,
        participant_payload_checksum=checksum(situation.participant_payload),
        indicator_ids=[x.indicator_id for x in situation.indicator_targets],
        admitted=True,
    ).model_dump()
