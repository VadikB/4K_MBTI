"""Транзакционное хранение пакетов M5 и неизменяемых Assessment Situation."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from Api.assessment_case_contracts import AssessmentSituationV2, CaseVersionV2
from Api.assessment_contexts import build_personalized_profile, canonical_json, context_checksum
from Api.m5_case_runtime import build_assessment_situation, checksum
from Api.m5_rule_engine import build_m5_ai_operations_snapshot


class M5ImportConflict(ValueError):
    pass


def resolve_legacy_base_role(*values: object) -> str:
    """Разрешает технические коды и отображаемые имена legacy-ролей в M3 base role."""
    aliases = {
        "leader": "direction_system_leader",
        "лидер": "direction_system_leader",
        "manager": "project_product_process_manager",
        "менеджер": "project_product_process_manager",
        "linear": "specialist_expert",
        "linear_employee": "specialist_expert",
        "specialist": "specialist_expert",
        "линейный сотрудник": "specialist_expert",
        "специалист": "specialist_expert",
    }
    base_roles = {
        "direction_system_leader",
        "project_product_process_manager",
        "specialist_expert",
    }
    for value in values:
        normalized = " ".join(str(value or "").strip().lower().split())
        if not normalized:
            continue
        if normalized in base_roles:
            return normalized
        if normalized in aliases:
            return aliases[normalized]
    return ""


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


def migrate_legacy_test_profile(connection, *, user_id: int, authorized_by: int) -> dict:
    """Фиксирует текущий test-профиль в M4 для серверного QA-контура."""
    existing = connection.execute(
        "SELECT id,checksum FROM assessment_personalized_profiles "
        "WHERE user_id=%s AND provenance_json->>'migration'='legacy_test_profile_migration' "
        "ORDER BY id DESC LIMIT 1", (user_id,),
    ).fetchone()
    if existing:
        return {"personalized_profile_id": int(existing["id"]), "checksum": existing["checksum"], "idempotent": True}
    user = connection.execute("""
        SELECT u.id,u.full_name,u.job_description,u.company_industry,
               p.raw_position,p.raw_duties,p.normalized_duties,p.role_selected,p.role_selected_code,
               r.code AS platform_role_code,r.name AS platform_role_name,p.company_context,
               p.user_domain,p.user_processes,p.user_tasks,p.user_stakeholders,p.user_constraints,
               p.user_artifacts,p.user_systems,p.user_success_metrics
        FROM users u
        LEFT JOIN user_role_profiles p ON p.id=u.active_profile_id
        LEFT JOIN roles r ON r.id=u.role_id
        WHERE u.id=%s
    """, (user_id,)).fetchone()
    if user is None:
        raise ValueError("LEGACY_TEST_USER_NOT_FOUND")
    memberships = connection.execute("""
        SELECT o.id,o.name,o.industry,o.profile,o.notes FROM organization_memberships m
        JOIN organizations o ON o.id=m.organization_id WHERE m.user_id=%s AND o.is_active=TRUE
    """, (user_id,)).fetchall()
    if len(memberships) != 1:
        raise ValueError("M4_REQUIRES_SINGLE_ACTIVE_ORGANIZATION")
    organization = memberships[0]
    role_code = resolve_legacy_base_role(
        user["role_selected_code"],
        user["platform_role_code"],
        user["role_selected"],
        user["platform_role_name"],
    )
    role = connection.execute("""
        SELECT v.id,v.definition_json,v.checksum FROM assessment_role_profile_versions v
        JOIN assessment_role_profiles p ON p.id=v.role_profile_id
        WHERE p.code=%s AND p.scope='base' AND v.status='published' AND v.methodology_version='1.1'
        ORDER BY v.version DESC LIMIT 1
    """, (role_code,)).fetchone()
    if role is None:
        raise ValueError(f"M4_PUBLISHED_ROLE_PROFILE_NOT_FOUND:{role_code or 'unknown'}")
    configuration = connection.execute("""
        SELECT c.id FROM assessment_configurations c JOIN assessment_methodology_versions m ON m.id=c.methodology_version_id
        WHERE c.status='published' AND m.status='published' AND m.definition_json->>'methodology_version'='1.1'
        ORDER BY c.is_default DESC,c.id DESC LIMIT 1
    """).fetchone()
    if configuration is None:
        raise ValueError("M4_PUBLISHED_CONFIGURATION_1_1_NOT_FOUND")
    marker = {"migration": "legacy_test_profile_migration", "authorized_by": authorized_by,
              "source_user_id": user_id, "scope": "qa"}
    organization_definition = {
        "name": organization["name"], "organization_type": "компания",
        "industry": organization["industry"] or user["company_industry"] or "не указана",
        "activity_description": organization["profile"] or organization["notes"] or user["company_context"] or "тестовый контекст организации",
        "case_reality_level": "обобщённый",
        "organization_name_usage_rules": "не использовать название без необходимости",
    }
    org_parent = connection.execute("""
        INSERT INTO assessment_organization_contexts (organization_id,code) VALUES (%s,'legacy-test-migration')
        ON CONFLICT (organization_id,code) DO UPDATE SET code=EXCLUDED.code RETURNING id
    """, (organization["id"],)).fetchone()
    org_checksum = context_checksum(organization_definition)
    org_version = connection.execute("""
        INSERT INTO assessment_organization_context_versions
        (organization_context_id,version,status,definition_json,source_manifest_json,checksum,confirmed_by_user_id,confirmed_at)
        VALUES (%s,1,'published',%s::jsonb,%s::jsonb,%s,%s,NOW()) RETURNING id
    """, (org_parent["id"], canonical_json(organization_definition), canonical_json(marker),
           org_checksum, authorized_by)).fetchone()
    duties = user["user_tasks"] or ([user["normalized_duties"] or user["raw_duties"]]
                                    if user["normalized_duties"] or user["raw_duties"] else [])
    professional = {
        "position_or_status": user["raw_position"] or user["job_description"], "regular_tasks": duties,
        "work_materials": user["user_artifacts"] or [], "systems_and_tools": user["user_systems"] or [],
        "additional_information": {"domain": user["user_domain"], "processes": user["user_processes"] or [],
            "stakeholders": user["user_stakeholders"] or [], "constraints": user["user_constraints"] or [],
            "success_metrics": user["user_success_metrics"] or []},
    }
    user_parent = connection.execute("""
        INSERT INTO assessment_user_contexts (user_id,organization_id) VALUES (%s,%s)
        ON CONFLICT (user_id,organization_id) DO UPDATE SET organization_id=EXCLUDED.organization_id RETURNING id
    """, (user_id, organization["id"])).fetchone()
    user_identity = {"full_name": user["full_name"]}
    user_checksum = context_checksum({"identity": user_identity, "professional": professional})
    user_version = connection.execute("""
        INSERT INTO assessment_user_context_versions
        (user_context_id,version,status,identity_json,professional_context_json,checksum,confirmed_by_user_id,confirmed_at)
        VALUES (%s,1,'confirmed',%s::jsonb,%s::jsonb,%s,%s,NOW()) RETURNING id
    """, (user_parent["id"], canonical_json(user_identity), canonical_json(professional),
           user_checksum, user_id)).fetchone()
    snapshot = build_personalized_profile(
        organization_id=int(organization["id"]), organization_context=organization_definition,
        organization_context_ref={"version_id": int(org_version["id"]), "checksum": org_checksum},
        role_profile=dict(role["definition_json"]),
        role_profile_ref={"version_id": int(role["id"]), "checksum": role["checksum"]},
        user_identity=user_identity, user_context=professional,
        user_context_ref={"version_id": int(user_version["id"]), "checksum": user_checksum}, conflicts=[])
    snapshot["provenance"].update({"migration": marker["migration"], "authorized_by": authorized_by})
    snapshot["checksum"] = context_checksum({k: v for k, v in snapshot.items() if k != "checksum"})
    profile = connection.execute("""
        INSERT INTO assessment_personalized_profiles
        (user_id,organization_id,assessment_configuration_id,organization_context_version_id,role_profile_version_id,
         user_context_version_id,status,content_json,provenance_json,conflicts_json,checksum)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,'[]'::jsonb,%s) RETURNING id
    """, (user_id, organization["id"], configuration["id"], org_version["id"], role["id"], user_version["id"],
           snapshot["status"], canonical_json(snapshot["content"]), canonical_json(snapshot["provenance"]),
           snapshot["checksum"])).fetchone()
    return {"personalized_profile_id": int(profile["id"]), "checksum": snapshot["checksum"],
            "base_role": role_code, "idempotent": False, "provenance": marker["migration"]}


def save_assessment_situation(connection, *, situation: dict, execution_payload: dict, personalized_profile_id: int,
                              cycle_db_id: int, session_db_id: int, policy: dict, evidence_ids: list[int], usage_scope: str = "assessment",
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
    membership = connection.execute("""
        SELECT c.id AS cycle_id, s.id AS session_id, c.personalized_profile_id,
               c.target_set_json, c.profile_ref_json, c.selected_role_ref_json
        FROM m5_cycles c JOIN m5_cycle_sessions s ON s.cycle_db_id=c.id
        WHERE c.id=%s AND s.id=%s
    """, (cycle_db_id, session_db_id)).fetchone()
    if not membership or int(membership["personalized_profile_id"]) != personalized_profile_id:
        raise ValueError("M7_CYCLE_SESSION_OWNERSHIP_MISMATCH")
    if dict(membership["profile_ref_json"]) != value.profile_ref.model_dump():
        raise ValueError("M7_FROZEN_PROFILE_MISMATCH")
    selected_role = dict(membership["selected_role_ref_json"])
    # Numeric RoleProfileVersion refs are authoritative through the frozen profile;
    # textual refs must equal the Case base role.
    if not str(selected_role.get("id", "")).isdigit() and selected_role.get("id") != value.base_role:
        raise ValueError("ROLE_NOT_ALLOWED")
    if value.cycle_ref.id != str(cycle_db_id) or value.session_ref.id != str(session_db_id):
        raise ValueError("M7_CYCLE_SESSION_REF_MISMATCH")
    cycle_targets = {(x["indicator_id"], x["m2_version"]) for x in membership["target_set_json"]}
    as_targets = {(x.indicator_id, x.m2_version) for x in value.indicator_targets}
    if not as_targets.issubset(cycle_targets):
        raise ValueError("TARGET_SET_MISMATCH")
    row = connection.execute("""
        INSERT INTO m5_assessment_situations (assessment_situation_id, case_version_id, personalized_profile_id,
            cycle_db_id,session_db_id,usage_scope, status, snapshot_json, execution_payload_json, snapshot_checksum)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s) RETURNING id
    """, (UUID(value.assessment_situation_id), int(case_row["id"]), personalized_profile_id,
          cycle_db_id, session_db_id, usage_scope, "admitted" if value.admission.admitted else "rejected", json.dumps(snapshot, ensure_ascii=False),
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
                                 personalized_profile_id: int, cycle_db_id: int, session_db_id: int,
                                 substitutions: list[dict], policy: dict,
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
    cycle = connection.execute("SELECT * FROM m5_cycles WHERE id=%s", (cycle_db_id,)).fetchone()
    session = connection.execute("SELECT * FROM m5_cycle_sessions WHERE id=%s AND cycle_db_id=%s", (session_db_id, cycle_db_id)).fetchone()
    if not cycle or not session:
        raise ValueError("M7_CYCLE_SESSION_OWNERSHIP_MISMATCH")
    situation, execution = build_assessment_situation(
        assessment_situation_id=assessment_situation_id, case_value=case_row["content_json"],
        cycle_ref={"id": str(cycle_db_id), "version": "1", "checksum": checksum({"cycle_id": str(cycle["cycle_id"]), "target_set_checksum": cycle["target_set_checksum"]})},
        session_ref={"id": str(session_db_id), "version": "1", "checksum": checksum({"session_id": str(session["session_id"]), "cycle_id": str(cycle["cycle_id"]), "ordinal": session["ordinal"]})},
        profile_ref={"id": f"assessment_personalized_profiles:{profile_row['id']}", "version": "1",
                     "checksum": profile_row["checksum"]},
        profile_snapshot={**profile, "base_role": base_role}, methodology_refs=refs,
        substitutions=substitutions, qa_evidence=evidence, policy=policy,
        ai_operations=build_m5_ai_operations_snapshot(),
    )
    execution["runtime_rules"] = case_row["runtime_rules_json"]
    situation["execution_payload_ref"]["checksum"] = checksum(execution)
    saved = save_assessment_situation(connection, situation=situation, execution_payload=execution,
                                      personalized_profile_id=personalized_profile_id, cycle_db_id=cycle_db_id,
                                      session_db_id=session_db_id, policy=policy,
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
