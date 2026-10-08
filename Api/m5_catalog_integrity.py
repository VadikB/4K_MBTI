"""Immutable M5 catalog publication and exact QA-evidence admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from Api.m5_case_runtime import checksum


POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "assessment_definitions/catalog_contracts/competencies_4k/1.0/catalog-integrity-policy.json"
)


def load_policy() -> dict[str, Any]:
    value = json.loads(POLICY_PATH.read_bytes())
    expected = (1, "m5_catalog_integrity", "1.0.0", "sha256-canonical-json-v1")
    if tuple(value.get(key) for key in (
        "schema_version", "id", "version", "evidence_checksum_algorithm"
    )) != expected:
        raise ValueError("M5_CATALOG_POLICY_INVALID")
    if set(value.get("required_evidence_scopes") or []) != {
        "case_format", "case_dialogue", "assessment_situation"
    }:
        raise ValueError("M5_CATALOG_POLICY_INVALID")
    value["checksum"] = hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()
    return value


def _reason(code: str, scope: str | None = None) -> str:
    return code if scope is None else f"{code}:{scope}"


def _validate_evidence(
    *, row: dict[str, Any], case: dict[str, Any], usage_scope: str, policy: dict[str, Any]
) -> list[str]:
    scope = str(row["scope"])
    payload = dict(row.get("evidence_json") or {})
    reasons: list[str] = []
    if checksum(payload) != row.get("evidence_checksum"):
        reasons.append(_reason("QA_EVIDENCE_CHECKSUM_MISMATCH", scope))
    if payload.get("eligibility") != policy["evidence_eligibility"]:
        reasons.append(_reason("QA_EVIDENCE_ELIGIBILITY_MISMATCH", scope))
    if payload.get("scope") != scope or payload.get("result") != row.get("result"):
        reasons.append(_reason("QA_EVIDENCE_PAYLOAD_MISMATCH", scope))
    case_ref = payload.get("case_ref") if isinstance(payload.get("case_ref"), dict) else {}
    expected_ref = {
        "id": str(case["case_id"]),
        "version": str(case["case_version"]),
        "checksum": str(case["content_checksum"]),
    }
    if any(case_ref.get(key) != value for key, value in expected_ref.items()):
        reasons.append(_reason("QA_EVIDENCE_CASE_REF_MISMATCH", scope))
    if payload.get("base_role") != case["base_role"]:
        reasons.append(_reason("QA_EVIDENCE_BASE_ROLE_MISMATCH", scope))
    scopes = payload.get("usage_scopes")
    if not isinstance(scopes, list) or usage_scope not in scopes:
        reasons.append(_reason("QA_EVIDENCE_USAGE_SCOPE_MISMATCH", scope))
    origin = payload.get("origin") if isinstance(payload.get("origin"), dict) else {}
    if origin.get("type") not in policy["allowed_origins"][usage_scope]:
        reasons.append(_reason("QA_EVIDENCE_ORIGIN_NOT_ALLOWED", scope))
    if row.get("result") != "PASS":
        reasons.append(_reason(f"QA_EVIDENCE_{str(row.get('result')).upper()}", scope))
    return reasons


def case_admission(
    connection,
    *,
    case_version_id: int,
    usage_scope: str,
    catalog_db_id: int | None = None,
) -> dict[str, Any]:
    """Return one shared, failure-preserving admission result for planner and AS."""
    if usage_scope not in {"assessment", "qa"}:
        raise ValueError("M7_USAGE_SCOPE_INVALID")
    policy = load_policy()
    case = connection.execute(
        "SELECT id,package_id,case_id,case_version,status,base_role,content_json,content_checksum "
        "FROM m5_case_versions WHERE id=%s",
        (case_version_id,),
    ).fetchone()
    if case is None:
        raise ValueError("M5_CASE_VERSION_NOT_IMPORTED")
    case = dict(case)
    reasons: list[str] = []
    if catalog_db_id is not None and connection.execute(
        "SELECT 1 FROM m5_catalog_case_versions WHERE catalog_db_id=%s AND case_version_id=%s",
        (catalog_db_id, case_version_id),
    ).fetchone() is None:
        reasons.append("CASE_OUTSIDE_FROZEN_CATALOG")
    if case["status"] not in policy["allowed_case_statuses"]:
        reasons.append(f"CASE_STATUS_NOT_ADMITTED:{case['status']}")
    if (case.get("content_json") or {}).get("unresolved_decisions"):
        reasons.append("CASE_UNRESOLVED_DECISIONS")
    rows = connection.execute(
        """SELECT id,scope,result,evidence_json,evidence_checksum,created_at
           FROM m5_qa_evidence
           WHERE case_version_id=%s AND assessment_situation_id IS NULL
             AND evidence_json->>'eligibility'=%s
           ORDER BY scope,id DESC""",
        (case_version_id, policy["evidence_eligibility"]),
    ).fetchall()
    latest: dict[str, dict[str, Any]] = {}
    for raw in rows:
        latest.setdefault(str(raw["scope"]), dict(raw))
    accepted: list[dict[str, Any]] = []
    for scope in policy["required_evidence_scopes"]:
        row = latest.get(scope)
        if row is None:
            reasons.append(_reason("QA_EVIDENCE_MISSING", scope))
            continue
        item_reasons = _validate_evidence(row=row, case=case, usage_scope=usage_scope, policy=policy)
        reasons.extend(item_reasons)
        if not item_reasons:
            accepted.append({
                "id": int(row["id"]), "scope": scope, "result": row["result"],
                "artifact_ref": f"db:m5_qa_evidence:{row['id']}",
                "checksum": row["evidence_checksum"],
            })
    return {
        "admitted": not reasons,
        "code": "ADMITTED" if not reasons else "CASE_NOT_ADMITTED",
        "reasons": reasons,
        "case": case,
        "evidence": accepted,
        "policy_ref": {"id": policy["id"], "version": policy["version"], "checksum": policy["checksum"]},
    }


def resolve_profile_base_role(connection, *, role_profile_version_id: int) -> dict[str, Any]:
    row = connection.execute(
        """SELECT selected.id,selected.checksum,selected.base_role_version_id,
                  profile.code,profile.scope
           FROM assessment_role_profile_versions selected
           JOIN assessment_role_profiles profile ON profile.id=selected.role_profile_id
           WHERE selected.id=%s AND selected.status='published'""",
        (role_profile_version_id,),
    ).fetchone()
    if row is None:
        raise ValueError("ROLE_NOT_ALLOWED")
    base_id = int(row["base_role_version_id"] or row["id"])
    base = connection.execute(
        """SELECT version.id,version.version,version.checksum,profile.code,profile.scope
           FROM assessment_role_profile_versions version
           JOIN assessment_role_profiles profile ON profile.id=version.role_profile_id
           WHERE version.id=%s AND version.status='published'""",
        (base_id,),
    ).fetchone()
    if base is None or base["scope"] != "base":
        raise ValueError("ROLE_BASE_ROLE_REQUIRED")
    return {"id": str(base["id"]), "version": str(base["version"]),
            "checksum": base["checksum"], "code": base["code"]}


def resolve_configuration_catalog(connection, *, configuration_id: int, usage_scope: str) -> dict[str, Any]:
    has_binding = connection.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() "
        "AND table_name='assessment_configurations' AND column_name='catalog_version_id'"
    ).fetchone()
    if has_binding is None:
        return {"db_id": None, "id": "legacy-unbound-test-catalog", "version": "0",
                "checksum": "legacy-unbound-test-catalog", "package_checksum": "legacy",
                "m2_checksum": "legacy", "organization_id": None, "usage_scope": usage_scope}
    row = connection.execute(
        """SELECT catalog.id,catalog.catalog_id,catalog.catalog_version,catalog.manifest_checksum,
                  catalog.package_db_id,package.package_checksum,package.manifest_json,
                  catalog.organization_id,catalog.usage_scope
           FROM assessment_configurations configuration
           LEFT JOIN m5_catalogs catalog ON catalog.id=configuration.catalog_version_id
           LEFT JOIN m5_packages package ON package.id=catalog.package_db_id
           WHERE configuration.id=%s AND configuration.status='published'""",
        (configuration_id,),
    ).fetchone()
    if row is None:
        raise ValueError("M5_CONFIGURATION_NOT_PUBLISHED")
    if row["id"] is None:
        raise ValueError("M5_CATALOG_REF_REQUIRED")
    if row["usage_scope"] != usage_scope and not (row["usage_scope"] == "qa" and usage_scope == "qa"):
        raise ValueError("M5_CATALOG_USAGE_SCOPE_MISMATCH")
    return {
        "db_id": int(row["id"]), "id": row["catalog_id"], "version": row["catalog_version"],
        "checksum": row["manifest_checksum"], "package_db_id": int(row["package_db_id"]),
        "package_checksum": row["package_checksum"], "m2_checksum": row["manifest_json"]["dependencies"]["m2"],
        "organization_id": row["organization_id"], "usage_scope": row["usage_scope"],
    }


def publication_plan(
    connection, *, package_db_id: int, case_version_ids: list[int], usage_scope: str,
    organization_id: int | None = None,
) -> dict[str, Any]:
    package = connection.execute("SELECT * FROM m5_packages WHERE id=%s", (package_db_id,)).fetchone()
    if package is None:
        raise ValueError("M5_PACKAGE_NOT_FOUND")
    selected = sorted(set(int(value) for value in case_version_ids))
    cases = connection.execute(
        "SELECT id FROM m5_case_versions WHERE package_id=%s AND id=ANY(%s) ORDER BY id",
        (package_db_id, selected),
    ).fetchall() if selected else []
    if len(cases) != len(selected):
        raise ValueError("M5_CATALOG_CASE_OUTSIDE_PACKAGE")
    decisions = [case_admission(connection, case_version_id=value, usage_scope=usage_scope) for value in selected]
    return {
        "package_db_id": package_db_id, "package_id": package["package_id"],
        "package_version": package["package_version"], "package_checksum": package["package_checksum"],
        "m2_checksum": package["manifest_json"]["dependencies"]["m2"],
        "organization_id": organization_id, "usage_scope": usage_scope,
        "case_version_ids": selected, "decisions": [
            {"case_id": item["case"]["case_id"], "case_version": item["case"]["case_version"],
             "admitted": item["admitted"], "reasons": item["reasons"]} for item in decisions
        ],
        "publishable": all(item["admitted"] for item in decisions),
    }


def publish_catalog(
    connection, *, catalog_id: str, catalog_version: str, package_db_id: int,
    case_version_ids: list[int], usage_scope: str, published_by: int, decision_basis: str,
    idempotency_key: str, organization_id: int | None = None, dry_run: bool = False,
) -> dict[str, Any]:
    if not str(decision_basis or "").strip():
        raise ValueError("M5_CATALOG_DECISION_BASIS_REQUIRED")
    plan = publication_plan(connection, package_db_id=package_db_id, case_version_ids=case_version_ids,
                            usage_scope=usage_scope, organization_id=organization_id)
    request = {**plan, "catalog_id": catalog_id, "catalog_version": catalog_version,
               "published_by": published_by, "decision_basis": decision_basis.strip()}
    request_hash = checksum(request)
    if dry_run:
        return {"dry_run": True, "request_hash": request_hash, **plan}
    if not plan["publishable"]:
        raise ValueError("M5_CATALOG_CASE_NOT_ADMITTED")
    existing = connection.execute(
        "SELECT * FROM m5_catalogs WHERE published_by=%s AND idempotency_key=%s FOR UPDATE",
        (published_by, idempotency_key),
    ).fetchone()
    if existing:
        if existing["request_hash"] != request_hash:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return {"dry_run": False, "idempotent": True, "catalog_db_id": int(existing["id"]),
                "manifest_checksum": existing["manifest_checksum"]}
    manifest = {"schema_version": 1, "catalog_id": catalog_id, "catalog_version": catalog_version,
                "package_ref": {"id": plan["package_id"], "version": plan["package_version"],
                                "checksum": plan["package_checksum"]},
                "m2_checksum": plan["m2_checksum"], "organization_id": organization_id,
                "usage_scope": usage_scope, "case_version_ids": plan["case_version_ids"]}
    manifest_checksum = checksum(manifest)
    row = connection.execute(
        """INSERT INTO m5_catalogs
           (catalog_id,catalog_version,organization_id,usage_scope,package_db_id,manifest_json,
            manifest_checksum,status,published_by,decision_basis,idempotency_key,request_hash,published_at)
           VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,'published',%s,%s,%s,%s,NOW()) RETURNING id""",
        (catalog_id, catalog_version, organization_id, usage_scope, package_db_id,
         json.dumps(manifest, ensure_ascii=False), manifest_checksum, published_by,
         decision_basis.strip(), idempotency_key, request_hash),
    ).fetchone()
    for case_version_id in plan["case_version_ids"]:
        connection.execute("INSERT INTO m5_catalog_case_versions VALUES (%s,%s)",
                           (row["id"], case_version_id))
    return {"dry_run": False, "idempotent": False, "catalog_db_id": int(row["id"]),
            "manifest_checksum": manifest_checksum}


def catalog_readback(connection, catalog_db_id: int) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM m5_catalogs WHERE id=%s", (catalog_db_id,)).fetchone()
    if row is None:
        raise ValueError("M5_CATALOG_NOT_FOUND")
    manifest = dict(row["manifest_json"])
    if checksum(manifest) != row["manifest_checksum"]:
        raise ValueError("CHECKSUM_MISMATCH")
    case_ids = [int(item["case_version_id"]) for item in connection.execute(
        "SELECT case_version_id FROM m5_catalog_case_versions WHERE catalog_db_id=%s ORDER BY case_version_id",
        (catalog_db_id,),
    ).fetchall()]
    if case_ids != manifest["case_version_ids"]:
        raise ValueError("M5_CATALOG_CONTENT_MISMATCH")
    return {"id": int(row["id"]), "catalog_id": row["catalog_id"],
            "catalog_version": row["catalog_version"], "status": row["status"],
            "manifest": manifest, "manifest_checksum": row["manifest_checksum"]}
