"""Grounded descriptive projection for an immutable M8 Report revision."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from Api.m5_case_runtime import checksum

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "assessment_definitions/prompts/m8_descriptive_report/v2"
CONTRACT_VERSION = "m8-descriptive-report/1.2.0"
FORBIDDEN = re.compile(
    r"\b(рекоменду(?:ем|ется|ю)|совету(?:ем|ю)|попробуйте|вам следует|"
    r"упражнени[ея]|план развития|диагноз|профпригодност)\b", re.IGNORECASE,
)


def load_package(package: Path = PACKAGE) -> dict:
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    identity = tuple(manifest.get(k) for k in ("schema_version", "id", "status", "scope", "owner"))
    if identity != (1, "m8_descriptive_report", "draft", "m8_descriptive_report", "PM-06"):
        raise ValueError("M8_DESCRIPTION_PACKAGE_INVALID")
    version = manifest.get("version")
    artifact_names = {
        "1.1.0": ("prompt.md", "schema.json"),
        "1.2.0": ("prompt.md", "schema.json", "validator_prompt.md", "validator_schema.json"),
    }.get(version)
    if artifact_names is None:
        raise ValueError("M8_DESCRIPTION_PACKAGE_INVALID")
    artifacts = []
    for name in artifact_names:
        raw = (package / name).read_bytes()
        artifacts.append({"name": name, "sha256": hashlib.sha256(raw).hexdigest()})
    if manifest.get("artifacts") != artifacts:
        raise ValueError("CHECKSUM_MISMATCH")
    validator_prompt = ((package / "validator_prompt.md").read_text(encoding="utf-8")
                        if version == "1.2.0" else None)
    return {"manifest": manifest, "prompt": (package / "prompt.md").read_text(encoding="utf-8"),
            "validator_prompt": validator_prompt,
            "schema": json.loads((package / "schema.json").read_text(encoding="utf-8")),
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


def build_input(results: dict, resolved: dict, *, contract_version: str = CONTRACT_VERSION) -> tuple[dict, dict]:
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
    model_input = {"contract_version": contract_version, "cycle_id": results["cycle_id"],
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


def _validate_semantic_decision(decision: dict, output: dict) -> dict:
    if not isinstance(decision, dict) or set(decision) != {"status", "claim_decisions", "summary_decisions"}:
        raise ValueError("M8_DESCRIPTION_SEMANTIC_OUTPUT_INVALID")
    if decision["status"] not in {"accepted", "rejected"}:
        raise ValueError("M8_DESCRIPTION_SEMANTIC_STATUS_INVALID")
    claims = decision["claim_decisions"]
    summaries = decision["summary_decisions"]
    if not isinstance(claims, list) or not isinstance(summaries, list):
        raise ValueError("M8_DESCRIPTION_SEMANTIC_DECISIONS_INVALID")
    allowed_decisions = {"supported", "contradicted", "insufficient"}
    required = {"index", "decision", "reason_code"}
    for items, expected_count in ((claims, len(output["claims"])), (summaries, len(output["summary"]))):
        if len(items) != expected_count or {item.get("index") for item in items if isinstance(item, dict)} != set(range(expected_count)):
            raise ValueError("M8_DESCRIPTION_SEMANTIC_COVERAGE_INVALID")
        for item in items:
            if set(item) != required or item["decision"] not in allowed_decisions or not str(item["reason_code"]).strip():
                raise ValueError("M8_DESCRIPTION_SEMANTIC_DECISION_INVALID")
    all_supported = all(item["decision"] == "supported" for item in claims + summaries)
    if (decision["status"] == "accepted") != all_supported:
        raise ValueError("M8_DESCRIPTION_SEMANTIC_STATUS_MISMATCH")
    return decision


def generate(results: dict, resolved: dict, *, gateway=None, package_path: Path = PACKAGE) -> dict:
    package = load_package(package_path)
    contract_version = f"m8-descriptive-report/{package['manifest']['version']}"
    model_input, allowed = build_input(results, resolved, contract_version=contract_version)
    metadata = {"contract_version": contract_version, "mechanism": {"id": package["manifest"]["id"],
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
        if package["validator_prompt"] is None:
            return {**metadata, "status": "ready", "failure_reason": None, **output}
        semantic_input = {"contract_version": contract_version, "evidence": model_input, "candidate": output}
        semantic_raw = gateway.chat(
            [{"role": "system", "content": package["validator_prompt"]},
             {"role": "user", "content": json.dumps(semantic_input, ensure_ascii=False)}],
            temperature=0, timeout_seconds=package["manifest"]["execution"]["timeout_seconds"],
            max_tokens=package["manifest"]["execution"]["max_tokens"],
            routing_key=f"m8-description-validation:{results['revision_id']}", response_format={"type": "json_object"})
        semantic = _validate_semantic_decision(json.loads(semantic_raw), output)
        if semantic["status"] != "accepted":
            return {**metadata, "status": "failed", "failure_reason": "DESCRIPTION_SEMANTIC_REJECTED",
                    "semantic_validation": semantic, "summary": [], "claims": []}
        return {**metadata, "status": "ready", "failure_reason": None,
                "semantic_validation": semantic, **output}
    except (RuntimeError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {**metadata, "status": "failed", "failure_reason": "DESCRIPTION_GENERATION_FAILED",
                "summary": [], "claims": []}
