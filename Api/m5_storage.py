"""Транзакционное хранение пакетов M5 и неизменяемых Assessment Situation."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from Api.assessment_case_contracts import AssessmentSituationV2, CaseVersionV2
from Api.m5_case_runtime import build_assessment_situation, checksum


class M5ImportConflict(ValueError):
    pass


def import_package(connection, *, package: dict, manifest: dict, execution_rules: dict | None = None) -> dict:
    if package.get("runtime_enabled") is not False or package.get("source_status") != "WORKING":
        raise ValueError("M5 candidate import expects WORKING/runtime_disabled package")
    package_checksum = checksum({"package": package, "manifest": manifest})
    existing = connection.execute(
        "SELECT id, package_checksum FROM m5_packages WHERE package_id=%s AND package_version=%s FOR UPDATE",
        (manifest["id"], manifest["version"]),
    ).fetchone()
    if existing:
        if existing["package_checksum"] != package_checksum:
            raise M5ImportConflict("M5_PACKAGE_VERSION_CONTENT_CONFLICT")
        return {"package_db_id": int(existing["id"]), "created": False, "case_count": len(package["cases"])}
    row = connection.execute("""
        INSERT INTO m5_packages (package_id, package_version, schema_version, status, source_checksum,
            package_checksum, manifest_json, package_json, runtime_rules_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb) RETURNING id
    """, (manifest["id"], manifest["version"], package["schema_version"], package["status"],
          next(x["sha256"] for x in manifest["artifacts"] if x["name"].startswith("sources/")),
          package_checksum, json.dumps(manifest, ensure_ascii=False), json.dumps(package, ensure_ascii=False),
          json.dumps(execution_rules or {}, ensure_ascii=False))).fetchone()
    package_db_id = int(row["id"])
    for raw in package["cases"]:
        case = CaseVersionV2.model_validate(raw)
        content = case.model_dump()
        content_checksum = checksum(content)
        conflict = connection.execute(
            "SELECT content_checksum FROM m5_case_versions WHERE case_id=%s AND case_version=%s",
            (case.case_id, case.version),
        ).fetchone()
        if conflict:
            if conflict["content_checksum"] != content_checksum:
                raise M5ImportConflict("M5_CASE_VERSION_CONTENT_CONFLICT")
            raise M5ImportConflict("M5_CASE_VERSION_ALREADY_OWNED_BY_OTHER_PACKAGE")
        case_row = connection.execute("""
            INSERT INTO m5_case_versions (package_id, case_id, case_version, status, base_role, content_json, content_checksum)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING id
        """, (package_db_id, case.case_id, case.version, case.status, case.base_role,
              json.dumps(content, ensure_ascii=False), content_checksum)).fetchone()
        case_db_id = int(case_row["id"])
        for position, target in enumerate(case.indicator_targets, 1):
            connection.execute("""
                INSERT INTO m5_case_targets (case_version_id, indicator_id, m2_version, skill_id, component_id, target_json, display_order)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
            """, (case_db_id, target.indicator_id, target.m2_version, target.skill_id, target.component_id,
                  json.dumps(target.model_dump(), ensure_ascii=False), position))
        for table, key, values in (
            ("m5_case_characters", "character_id", case.characters),
            ("m5_case_materials", "material_id", case.materials),
            ("m5_case_scenario_steps", "step_id", case.scenario),
        ):
            for position, value in enumerate(values, 1):
                payload = value.model_dump()
                connection.execute(
                    f"INSERT INTO {table} (case_version_id,{key},content_json,display_order) VALUES (%s,%s,%s::jsonb,%s)",
                    (case_db_id, payload[key], json.dumps(payload, ensure_ascii=False), position),
                )
    return {"package_db_id": package_db_id, "created": True, "case_count": len(package["cases"])}


def import_package_directory(connection, directory: Path) -> dict:
    return import_package(
        connection,
        package=json.loads((directory / "case-package.json").read_text()),
        manifest=json.loads((directory / "manifest.json").read_text()),
        execution_rules=json.loads((directory / "execution-rules.json").read_text()),
    )


def package_readback(connection, package_db_id: int) -> dict:
    package = dict(connection.execute("SELECT * FROM m5_packages WHERE id=%s", (package_db_id,)).fetchone())
    cases = [dict(x) for x in connection.execute("""
        SELECT cv.id, cv.case_id, cv.case_version, cv.status, cv.base_role, cv.content_checksum,
               count(DISTINCT t.indicator_id) AS target_count,
               count(DISTINCT m.material_id) AS material_count,
               count(DISTINCT s.step_id) AS scenario_step_count
        FROM m5_case_versions cv
        LEFT JOIN m5_case_targets t ON t.case_version_id=cv.id
        LEFT JOIN m5_case_materials m ON m.case_version_id=cv.id
        LEFT JOIN m5_case_scenario_steps s ON s.case_version_id=cv.id
        WHERE cv.package_id=%s GROUP BY cv.id ORDER BY cv.case_id
    """, (package_db_id,)).fetchall()]
    return {"package": package, "cases": cases}


def qa_lab_catalog(connection, package: dict) -> dict:
    profiles = [dict(x) for x in connection.execute("""
        SELECT p.id, p.user_id, p.checksum, p.content_json, u.full_name
        FROM assessment_personalized_profiles p JOIN users u ON u.id=p.user_id
        WHERE p.status='ready' ORDER BY p.id DESC LIMIT 200
    """).fetchall()]
    return {
        "source_status": package["source_status"], "qa_scope": True,
        "profiles": [{"id": x["id"], "user_id": x["user_id"], "full_name": x["full_name"],
                      "checksum": x["checksum"],
                      "base_role": (x["content_json"].get("base_role") or x["content_json"].get("base_role_code")
                                    or (x["content_json"].get("role_profile") or {}).get("code"))} for x in profiles],
        "cases": [{"case_id": x["case_id"], "case_version": x["version"], "title": x["title"],
                   "base_role": x["base_role"], "indicator_ids": [y["indicator_id"] for y in x["indicator_targets"]],
                   "admitted_for_assessment": False} for x in package["cases"]],
    }


def save_assessment_situation(connection, *, situation: dict, execution_payload: dict, personalized_profile_id: int,
                              policy: dict, evidence_ids: list[int], usage_scope: str = "assessment",
                              qa_authorized_by: int | None = None) -> dict:
    if usage_scope == "qa" and qa_authorized_by is None:
        raise ValueError("QA_SERVER_AUTHORIZATION_REQUIRED")
    value = AssessmentSituationV2.model_validate(situation)
    case_row = connection.execute(
        "SELECT id FROM m5_case_versions WHERE case_id=%s AND case_version=%s",
        (value.case_ref.id, value.case_ref.version),
    ).fetchone()
    if not case_row:
        raise ValueError("M5_CASE_VERSION_NOT_IMPORTED")
    snapshot = value.model_dump()
    row = connection.execute("""
        INSERT INTO m5_assessment_situations (assessment_situation_id, case_version_id, personalized_profile_id,
            usage_scope, status, snapshot_json, execution_payload_json, snapshot_checksum)
        VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s) RETURNING id
    """, (UUID(value.assessment_situation_id), int(case_row["id"]), personalized_profile_id,
          usage_scope, "admitted" if value.admission.admitted else "rejected", json.dumps(snapshot, ensure_ascii=False),
          json.dumps(execution_payload, ensure_ascii=False), checksum(snapshot))).fetchone()
    as_db_id = int(row["id"])
    connection.execute("""
        INSERT INTO m5_admission_decisions (assessment_situation_db_id, policy_id, policy_version, policy_checksum,
            admitted, code, reasons_json, evidence_ids_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
    """, (as_db_id, policy["id"], policy["version"], checksum(policy), value.admission.admitted,
          value.admission.code, json.dumps(value.admission.reasons, ensure_ascii=False), json.dumps(evidence_ids)))
    if usage_scope == "qa":
        connection.execute("""
            INSERT INTO m5_qa_overrides (assessment_situation_db_id,authorized_by,reason)
            VALUES (%s,%s,'WORKING_CASE_TECHNICAL_QA')
        """, (as_db_id, qa_authorized_by))
    return {"id": as_db_id, "assessment_situation_id": value.assessment_situation_id,
            "status": "admitted" if value.admission.admitted else "rejected"}


def prepare_assessment_situation(connection, *, assessment_situation_id: str, case_id: str, case_version: str,
                                 personalized_profile_id: int, substitutions: list[dict], policy: dict,
                                 usage_scope: str = "assessment", qa_authorized_by: int | None = None) -> dict:
    case_row = connection.execute(
        "SELECT cv.content_json, p.manifest_json, p.runtime_rules_json FROM m5_case_versions cv JOIN m5_packages p ON p.id=cv.package_id WHERE cv.case_id=%s AND cv.case_version=%s",
        (case_id, case_version),
    ).fetchone()
    profile_row = connection.execute("""
        SELECT id, status, content_json, provenance_json, checksum
        FROM assessment_personalized_profiles WHERE id=%s
    """, (personalized_profile_id,)).fetchone()
    if not case_row:
        raise ValueError("M5_CASE_VERSION_NOT_IMPORTED")
    if not profile_row or profile_row["status"] != "ready":
        raise ValueError("M4_PROFILE_NOT_READY")
    profile = dict(profile_row["content_json"])
    role_profile = profile.get("role_profile") if isinstance(profile.get("role_profile"), dict) else {}
    base_role = profile.get("base_role") or profile.get("base_role_code") or role_profile.get("code")
    evidence_rows = connection.execute("""
        SELECT id, scope, result, evidence_json, evidence_checksum
        FROM m5_qa_evidence
        WHERE case_version_id=(SELECT id FROM m5_case_versions WHERE case_id=%s AND case_version=%s)
          AND assessment_situation_id IS NULL
          AND evidence_json->>'eligibility'='user_admission'
        ORDER BY id DESC
    """, (case_id, case_version)).fetchall()
    latest = {}
    for item in evidence_rows:
        latest.setdefault(item["scope"], item)
    evidence = [{"scope": x["scope"], "result": x["result"],
                 "artifact_ref": f"db:m5_qa_evidence:{x['id']}", "checksum": x["evidence_checksum"]}
                for x in latest.values()]
    refs = [{"id": "m2-competencies-4k", "version": "1.1",
             "checksum": case_row["manifest_json"]["dependencies"]["m2"]}]
    situation, execution = build_assessment_situation(
        assessment_situation_id=assessment_situation_id, case_value=case_row["content_json"],
        profile_ref={"id": f"assessment_personalized_profiles:{profile_row['id']}", "version": "1",
                     "checksum": profile_row["checksum"]},
        profile_snapshot={**profile, "base_role": base_role}, methodology_refs=refs,
        substitutions=substitutions, qa_evidence=evidence, policy=policy,
    )
    execution["runtime_rules"] = case_row["runtime_rules_json"]
    situation["execution_payload_ref"]["checksum"] = checksum(execution)
    saved = save_assessment_situation(connection, situation=situation, execution_payload=execution,
                                      personalized_profile_id=personalized_profile_id, policy=policy,
                                      evidence_ids=[int(x["id"]) for x in latest.values()], usage_scope=usage_scope,
                                      qa_authorized_by=qa_authorized_by)
    return {**saved, "snapshot": situation, "execution_payload": execution}


def record_technical_qa_evidence(connection, *, assessment_situation_id: str, trajectory: str,
                                 expected: dict, actual: dict, defects: list[dict], performed_by: int) -> dict:
    row = connection.execute("""
        SELECT s.id, s.status, s.snapshot_json, s.snapshot_checksum, s.case_version_id, cv.content_checksum
        FROM m5_assessment_situations s JOIN m5_case_versions cv ON cv.id=s.case_version_id
        WHERE s.assessment_situation_id=%s
    """, (UUID(assessment_situation_id),)).fetchone()
    if not row:
        raise ValueError("M5_AS_NOT_FOUND")
    if row["status"] not in {"scenario_ended", "terminated", "closed"}:
        raise ValueError("QA_EVIDENCE_REQUIRES_FINISHED_SCENARIO")
    trace_rows = connection.execute("""
        SELECT 'turn' AS kind, turn_id::text AS ref, sequence_no, created_at FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s
        UNION ALL
        SELECT 'event', event_id::text, sequence_no, created_at FROM m5_scenario_events WHERE assessment_situation_db_id=%s
        ORDER BY sequence_no
    """, (row["id"], row["id"])).fetchall()
    evidence = {
        "schema_version": 1, "eligibility": "technical_qa", "controlled_or_simulated": True,
        "case_ref": {**row["snapshot_json"]["case_ref"], "content_checksum": row["content_checksum"]},
        "base_role": row["snapshot_json"]["base_role"],
        "assessment_situation_ref": {"id": assessment_situation_id, "checksum": row["snapshot_checksum"]},
        "trajectory": trajectory, "expected": expected, "actual": actual, "defects": defects,
        "trace_refs": [{"kind": x["kind"], "id": x["ref"], "sequence_no": x["sequence_no"]} for x in trace_rows],
        "performed_by": performed_by, "empirical_pilot": "NOT_RUN", "human_methodological_approval": "NOT_RUN",
    }
    digest = checksum(evidence)
    saved = connection.execute("""
        INSERT INTO m5_qa_evidence
            (case_version_id,assessment_situation_id,scope,result,evidence_json,evidence_checksum)
        VALUES (%s,%s,'assessment_situation',%s,%s::jsonb,%s)
        ON CONFLICT (evidence_checksum) DO UPDATE SET evidence_checksum=EXCLUDED.evidence_checksum RETURNING *
    """, (row["case_version_id"], row["id"], "FAIL" if defects else "PASS",
          json.dumps(evidence, ensure_ascii=False), digest)).fetchone()
    return dict(saved)
