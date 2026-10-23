"""Grounded descriptive projection for an immutable M8 Report revision."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from Api.m5_case_runtime import checksum

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "assessment_definitions/prompts/m8_descriptive_report/v1"
CONTRACT_VERSION = "m8-descriptive-report/1.1.0"
FORBIDDEN = re.compile(
    r"\b(рекоменду(?:ем|ется|ю)|совету(?:ем|ю)|попробуйте|вам следует|"
    r"упражнени[ея]|план развития|диагноз|профпригодност)\b", re.IGNORECASE,
)


def load_package() -> dict:
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    expected = (1, "m8_descriptive_report", "1.1.0", "draft", "m8_descriptive_report", "PM-06")
    if tuple(manifest.get(k) for k in ("schema_version", "id", "version", "status", "scope", "owner")) != expected:
        raise ValueError("M8_DESCRIPTION_PACKAGE_INVALID")
    artifacts = []
    for name in ("prompt.md", "schema.json"):
        raw = (PACKAGE / name).read_bytes()
        artifacts.append({"name": name, "sha256": hashlib.sha256(raw).hexdigest()})
    if manifest.get("artifacts") != artifacts:
        raise ValueError("CHECKSUM_MISMATCH")
    return {"manifest": manifest, "prompt": (PACKAGE / "prompt.md").read_text(encoding="utf-8"),
            "schema": json.loads((PACKAGE / "schema.json").read_text(encoding="utf-8")),
            "package_checksum": checksum({"manifest": manifest, "artifacts": artifacts})}


def _profile_context(snapshot: dict | None) -> list[dict]:
    content = (snapshot or {}).get("content") or {}
    values = []
    paths = {
        "user_context.regular_tasks": (content.get("user_context") or {}).get("regular_tasks"),
        "user_context.decision_situations": (content.get("user_context") or {}).get("decision_situations"),
        "user_context.constraints_and_interactions": (content.get("user_context") or {}).get("constraints_and_interactions"),
        "role_profile.card.typical_tasks": ((content.get("role_profile") or {}).get("card") or {}).get("typical_tasks"),
        "organization_context.activity_description": (content.get("organization_context") or {}).get("activity_description"),
    }
    for path, raw in paths.items():
        for value in raw if isinstance(raw, list) else [raw]:
            text = str(value or "").strip()
            if text:
                values.append({"ref": path, "text": text[:1000]})
    return values


def build_input(results: dict, resolved: dict) -> tuple[dict, dict]:
    payload = results["results"]
    if resolved.get("cycle_id") != results["cycle_id"] or resolved.get("results_revision_id") != results["revision_id"]:
        raise ValueError("M8_DESCRIPTION_SCOPE_MISMATCH")
    skills = {item["skill_id"]: item for item in payload["assessed_skill_profile"]}
    bases = []
    allowed = {"skills": set(skills), "basis": set(), "basis_skills": {}, "quotes": {},
               "context": set(), "limitations": set()}
    for projection in resolved.get("projections", []):
        skill_id = (projection.get("criterion") or {}).get("skill_id")
        if skill_id not in skills:
            raise ValueError("M8_DESCRIPTION_SKILL_MISMATCH")
        ref = str(projection["revision_id"])
        allowed["basis"].add(ref)
        allowed["basis_skills"][ref] = skill_id
        fragments = []
        for trace in projection.get("traces", []):
            for fragment in trace.get("fragments", []):
                quote = str(fragment.get("quote") or "").strip()
                if quote:
                    fragments.append({"ref": str(fragment["id"]), "quote": quote})
                    allowed["quotes"].setdefault(quote, set()).add((ref, skill_id))
        target = projection["target"]
        limitations = list(dict.fromkeys((target.get("confidence") or {}).get("limitations", [])
                                          + (projection.get("bundle") or {}).get("limitations", [])))
        allowed["limitations"].update(str(item).strip() for item in limitations if str(item).strip())
        bases.append({"ref": ref, "skill_id": skill_id, "indicator_id": target["indicator_id"],
                      "outcome": target.get("outcome"), "rationale": target.get("rationale"),
                      "confirmed_features": (target.get("confidence") or {}).get("confirmed_features", []),
                      "limitations": limitations,
                      "fragments": fragments})
    context = _profile_context(payload.get("personalized_profile_snapshot"))
    allowed["context"] = {item["ref"] for item in context}
    allowed["limitations"].update(str(item).strip() for item in payload.get("limitations", []) if str(item).strip())
    for skill in skills.values():
        allowed["limitations"].update(str(item).strip() for item in skill.get("limitations", []) if str(item).strip())
    for reason in (payload.get("partial_result") or {}).get("limitation_reasons", []):
        text = str(reason.get("message") or reason.get("text") or "").strip()
        if text:
            allowed["limitations"].add(text)
    model_input = {"contract_version": CONTRACT_VERSION, "cycle_id": results["cycle_id"],
                   "results_revision_id": results["revision_id"],
                   "skills": [{k: item.get(k) for k in ("skill_id", "skill_name", "skill_description", "competency_id", "competency_name",
                                                         "outcome", "score", "completeness", "limitations")}
                              for item in skills.values()],
                   "bases": bases, "context": context,
                   "global_limitations": payload.get("limitations", []),
                   "partial_result": payload.get("partial_result")}
    return model_input, allowed


def _validate(output: dict, allowed: dict) -> dict:
    if not isinstance(output, dict) or set(output) != {"summary", "claims"}:
        raise ValueError("M8_DESCRIPTION_OUTPUT_INVALID")
    if not isinstance(output["summary"], list) or len(output["summary"]) > 4:
        raise ValueError("M8_DESCRIPTION_SUMMARY_INVALID")
    for text in output["summary"]:
        if not isinstance(text, str) or not text.strip() or FORBIDDEN.search(text):
            raise ValueError("M8_DESCRIPTION_TEXT_FORBIDDEN")
    claims = output["claims"]
    if not isinstance(claims, list):
        raise ValueError("M8_DESCRIPTION_CLAIMS_INVALID")
    for claim in claims:
        required = {"kind", "skill_ids", "basis_refs", "text", "limitations", "context_refs"}
        if not isinstance(claim, dict) or set(claim) != required:
            raise ValueError("M8_DESCRIPTION_CLAIM_INVALID")
        if claim["kind"] not in {"observation", "explanation", "context", "limitation", "quote"}:
            raise ValueError("M8_DESCRIPTION_KIND_INVALID")
        if not claim["skill_ids"] or not set(claim["skill_ids"]).issubset(allowed["skills"]):
            raise ValueError("M8_DESCRIPTION_SKILL_MISMATCH")
        if not set(claim["basis_refs"]).issubset(allowed["basis"]):
            raise ValueError("M8_DESCRIPTION_BASIS_MISMATCH")
        if claim["kind"] in {"observation", "explanation", "quote"}:
            if not claim["basis_refs"]:
                raise ValueError("M8_DESCRIPTION_BASIS_REQUIRED")
            if any(allowed["basis_skills"].get(ref) not in claim["skill_ids"] for ref in claim["basis_refs"]):
                raise ValueError("M8_DESCRIPTION_BASIS_MISMATCH")
            grounded_skills = {allowed["basis_skills"].get(ref) for ref in claim["basis_refs"]}
            if not set(claim["skill_ids"]).issubset(grounded_skills):
                raise ValueError("M8_DESCRIPTION_SKILL_BASIS_REQUIRED")
        if not set(claim["context_refs"]).issubset(allowed["context"]):
            raise ValueError("M8_DESCRIPTION_CONTEXT_MISMATCH")
        if claim["kind"] == "context" and not claim["context_refs"]:
            raise ValueError("M8_DESCRIPTION_CONTEXT_MISMATCH")
        text = str(claim["text"]).strip()
        if not text or FORBIDDEN.search(text):
            raise ValueError("M8_DESCRIPTION_TEXT_FORBIDDEN")
        if claim["kind"] == "quote":
            owners = allowed["quotes"].get(text) or set()
            if any(not any((ref, skill_id) in owners for ref in claim["basis_refs"])
                   for skill_id in claim["skill_ids"]):
                raise ValueError("M8_DESCRIPTION_QUOTE_MISMATCH")
        if not isinstance(claim["limitations"], list):
            raise ValueError("M8_DESCRIPTION_LIMITATIONS_INVALID")
        if any(str(item).strip() not in allowed["limitations"] for item in claim["limitations"]):
            raise ValueError("M8_DESCRIPTION_LIMITATIONS_INVALID")
        if claim["kind"] == "limitation" and text not in allowed["limitations"]:
            raise ValueError("M8_DESCRIPTION_LIMITATIONS_INVALID")
    grounded_summary = {claim["text"].strip() for claim in claims if claim["kind"] != "quote"}
    if any(text.strip() not in grounded_summary for text in output["summary"]):
        raise ValueError("M8_DESCRIPTION_SUMMARY_INVALID")
    return output


def generate(results: dict, resolved: dict, *, gateway=None) -> dict:
    package = load_package()
    model_input, allowed = build_input(results, resolved)
    metadata = {"contract_version": CONTRACT_VERSION, "mechanism": {"id": package["manifest"]["id"],
                "version": package["manifest"]["version"], "checksum": package["package_checksum"]},
                "input": model_input, "input_checksum": checksum(model_input)}
    if not model_input["bases"]:
        return {**metadata, "status": "ready", "failure_reason": None, "summary": [], "claims": []}
    try:
        if gateway is None:
            from Api.llm.deepseek_gateway import DeepSeekGateway
            gateway = DeepSeekGateway()
        if not getattr(gateway, "enabled", True):
            raise RuntimeError("provider unavailable")
        raw = gateway.chat([{"role": "system", "content": package["prompt"]},
                            {"role": "user", "content": json.dumps(model_input, ensure_ascii=False)}],
                           temperature=0, timeout_seconds=package["manifest"]["execution"]["timeout_seconds"],
                           max_tokens=package["manifest"]["execution"]["max_tokens"],
                           routing_key=f"m8-description:{results['revision_id']}", response_format={"type": "json_object"})
        output = _validate(json.loads(raw), allowed)
        return {**metadata, "status": "ready", "failure_reason": None, **output}
    except (RuntimeError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {**metadata, "status": "failed", "failure_reason": "DESCRIPTION_GENERATION_FAILED",
                "summary": [], "claims": []}
