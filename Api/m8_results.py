from __future__ import annotations

import json
from collections import defaultdict
from uuid import UUID, uuid4

from Api.assessment_configuration import definition_checksum
from Api.m5_case_runtime import checksum
from Api import m7_completion
from Api import m6_cycle_aggregation_repository as calculations
from Api.m8_report_package import load_package as load_report_package
from Api.m8_recommendations import generate as generate_recommendations
from Api.typst_pdf_renderer import render_typst_report

RESULTS_VERSION = "m8-results/1.0.0"
REPORT_TEMPLATE_VERSION = "m8-basic-report/1.2.0"
ALLOWED_AUDIENCES = {"assessee", "customer", "methodology_qa"}


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_results (
        id UUID PRIMARY KEY, cycle_db_id BIGINT NOT NULL UNIQUE REFERENCES m5_cycles(id), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_result_revisions (
        id UUID PRIMARY KEY, results_id UUID NOT NULL REFERENCES m8_results(id), revision_no INTEGER NOT NULL,
        calculation_id UUID NOT NULL REFERENCES m6_cycle_calculations(id), c46_revision_id UUID NOT NULL REFERENCES m7_c46_revisions(id),
        composition_checksum TEXT NOT NULL, payload_json JSONB NOT NULL, payload_checksum TEXT NOT NULL,
        reason TEXT NOT NULL, created_by BIGINT NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(results_id,revision_no), UNIQUE(results_id,calculation_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_result_keys (
        cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id), request_key TEXT NOT NULL, request_hash TEXT NOT NULL,
        result_revision_id UUID NOT NULL REFERENCES m8_result_revisions(id), PRIMARY KEY(cycle_db_id,request_key))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_reports (
        id UUID PRIMARY KEY, result_revision_id UUID NOT NULL REFERENCES m8_result_revisions(id), revision_no INTEGER NOT NULL,
        audience TEXT NOT NULL, target_profile_json JSONB, target_profile_checksum TEXT,
        template_version TEXT NOT NULL, c67_json JSONB NOT NULL, c67_checksum TEXT NOT NULL,
        status TEXT NOT NULL, request_key TEXT NOT NULL, request_hash TEXT NOT NULL,
        created_by BIGINT NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(result_revision_id,revision_no), UNIQUE(result_revision_id,request_key))""")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_m8_history_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'M8 history is immutable'; END; $$ LANGUAGE plpgsql""")
    for table in ("m8_results", "m8_result_revisions", "m8_reports"):
        trigger = f"immutable_{table}"
        connection.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        connection.execute(f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION prevent_m8_history_change()")


def _integrity(value: dict, digest: str) -> None:
    if checksum(value) != digest and definition_checksum(value) != digest:
        raise ValueError("CHECKSUM_MISMATCH")


def _skill_catalog() -> dict[str, dict]:
    from Api.m6_aggregation_package import M2
    source = json.loads(M2.read_bytes())
    result = {}
    for competency in source["competencies"]:
        for skill in competency["skills"]:
            result[skill["id"]] = {
                "skill_id": skill["id"],
                "skill_name": skill.get("name") or skill["id"],
                "competency_id": competency["id"],
                "competency_name": competency.get("name") or competency["id"],
            }
    return result


def _comparison(skill: dict, target: dict | None) -> dict:
    if target is None:
        return {"status": "NO_TARGET_REQUIREMENT"}
    if target.get("target_level") is None:
        return {"status": "NO_TARGET_REQUIREMENT"}
    if skill["outcome"] == "no_result":
        return {"status": "NO_SKILL_RESULT", "target_level": target["target_level"]}
    return {"status": "NOT_COMPARABLE", "target_level": target["target_level"],
            "reason": "NORMATIVE_SKILL_LEVEL_NOT_AVAILABLE"}


def _build_payload(cycle: dict, c46: dict, calculation: dict, target_profile: dict | None,
                   profile_snapshot: dict | None) -> dict:
    c56 = calculation["c56"]
    if c56.get("contract") != "C-56" or c56.get("readiness") != "ready_for_pm06":
        raise ValueError("M8_INPUT_NOT_READY")
    if c46.get("status") != "reconciled" or c46["payload_json"].get("calculation", {}).get("status") != "completed":
        raise ValueError("M8_INPUT_NOT_READY")
    ref = c46["payload_json"]["calculation"]["revision_ref"]
    if str(ref.get("id")) != str(calculation["id"]):
        raise ValueError("COMPOSITION_MISMATCH")
    if c46["composition_checksum"] != c56.get("composition_checksum"):
        raise ValueError("COMPOSITION_MISMATCH")
    if str(c56.get("cycle_id")) != str(cycle["cycle_id"]):
        raise ValueError("COMPOSITION_MISMATCH")
    catalog = _skill_catalog()
    targets = {x["skill_id"]: x for x in (target_profile or {}).get("requirements", [])}
    skills = []
    for raw in c56["skill_outcomes"]:
        meta = catalog.get(raw["skill_id"], {"skill_id": raw["skill_id"], "skill_name": raw["skill_id"],
                                             "competency_id": raw["skill_id"].split(".")[0],
                                             "competency_name": raw["skill_id"].split(".")[0]})
        item = {**meta, **raw, "comparison": _comparison(raw, targets.get(raw["skill_id"]))}
        skills.append(item)
    competencies = defaultdict(list)
    for skill in skills:
        competencies[(skill["competency_id"], skill["competency_name"])].append(skill["skill_id"])
    failed_admissions = [item for item in c56.get("admissions", []) if item.get("processing_status") == "failed"]
    processing = {
        "contract_version": "m10-processing-recovery/1.0.0",
        "status": "failed" if failed_admissions else "completed",
        "stage": "substantive_admission",
        "error_code": "M6_ADMISSION_PROCESSING_FAILED" if failed_admissions else None,
        "affected_indicator_ids": sorted(item["indicator_id"] for item in failed_admissions),
        "message": ("Не удалось завершить техническую обработку части результатов. "
                    "Сохранённые ответы и подтверждённые основания не потеряны."
                    if failed_admissions else "Обработка завершена."),
        "allowed_actions": [],
    }
    limitations = list(c56.get("limitations") or []) + ["Skill Level is not derived from numeric Score"]
    if failed_admissions:
        limitations.append("Часть результата ограничена техническим сбоем обработки; это не L0 и не содержательный вывод.")
    return {
        "schema_version": 1, "results_version": RESULTS_VERSION, "cycle_id": str(cycle["cycle_id"]),
        "subject_user_id": cycle["owner_user_id"], "profile_ref": cycle["profile_ref_json"],
        "personalized_profile_snapshot": profile_snapshot,
        "role_ref": cycle["selected_role_ref_json"], "composition": c56["composition"],
        "composition_checksum": c56["composition_checksum"], "calculation_ref": c56["calculation_ref"],
        "c46_ref": {"id": str(c46["id"]), "revision_no": c46["revision_no"], "checksum": c46["payload_checksum"]},
        "c56_ref": {"calculation_id": str(calculation["id"]), "revision_no": calculation["revision_no"]},
        "goal": c46["payload_json"].get("goal"), "full_target_set": c56["full_target_set"],
        "planned_target_set": c56["planned_target_set"], "sessions": c56["cycle_context"]["sessions"],
        "assessment_situations": c56["cycle_context"]["assessment_situations"],
        "time": c46["payload_json"]["time"], "collection": c46["payload_json"]["collection"],
        "assessed_skill_profile": skills,
        "competencies": [{"competency_id": key[0], "competency_name": key[1], "skill_ids": value,
                          "score": None} for key, value in sorted(competencies.items())],
        "coverage": c56["coverage"], "admissions": c56["admissions"], "observations": c56["observations"],
        "confidence": c56["confidence"], "reliability": c56["reliability"],
        "limitations": limitations, "processing": processing,
        "target_profile": target_profile, "sources": c56["sources"], "algorithm": c56["algorithm"],
    }


def create_results(connection, *, cycle_id: str, calculation_id: str, key: str,
                   target_profile: dict | None, created_by: int) -> dict:
    cycle = m7_completion._cycle(connection, cycle_id)
    if cycle["status"] != "calculated":
        raise ValueError("M8_INPUT_NOT_READY")
    calculation = calculations.read(connection, calculation_id)
    c46 = m7_completion.read_c46(connection, cycle_id)
    request = {"calculation_id": str(calculation_id), "target_profile": target_profile}
    request_hash = checksum(request)
    prior = connection.execute("SELECT * FROM m8_result_keys WHERE cycle_db_id=%s AND request_key=%s",
                               (cycle["id"], key)).fetchone()
    if prior:
        if prior["request_hash"] != request_hash:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return read_results_revision(connection, prior["result_revision_id"])
    profile_row = connection.execute(
        "SELECT content_json,checksum FROM assessment_personalized_profiles WHERE id=%s",
        (cycle["personalized_profile_id"],),
    ).fetchone()
    if not profile_row or profile_row["checksum"] != cycle["profile_ref_json"].get("checksum"):
        raise ValueError("CHECKSUM_MISMATCH")
    profile_snapshot = {"ref": cycle["profile_ref_json"], "content": profile_row["content_json"]}
    payload = _build_payload(cycle, c46, calculation, target_profile, profile_snapshot)
    logical = connection.execute("SELECT * FROM m8_results WHERE cycle_db_id=%s FOR UPDATE", (cycle["id"],)).fetchone()
    if not logical:
        results_id = uuid4()
        connection.execute("INSERT INTO m8_results(id,cycle_db_id) VALUES(%s,%s)", (results_id, cycle["id"]))
        revision_no = 1
    else:
        results_id = logical["id"]
        existing = connection.execute(
            "SELECT id FROM m8_result_revisions WHERE results_id=%s AND calculation_id=%s",
            (results_id, UUID(str(calculation_id))),
        ).fetchone()
        if existing:
            connection.execute("INSERT INTO m8_result_keys VALUES(%s,%s,%s,%s)",
                               (cycle["id"], key, request_hash, existing["id"]))
            return read_results_revision(connection, existing["id"])
        revision_no = connection.execute("SELECT COALESCE(MAX(revision_no),0)+1 AS n FROM m8_result_revisions WHERE results_id=%s",
                                         (results_id,)).fetchone()["n"]
    revision_id = uuid4()
    connection.execute("""INSERT INTO m8_result_revisions
        (id,results_id,revision_no,calculation_id,c46_revision_id,composition_checksum,payload_json,payload_checksum,reason,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
        (revision_id, results_id, revision_no, UUID(str(calculation_id)), c46["id"], c46["composition_checksum"],
         json.dumps(payload, ensure_ascii=False), checksum(payload), "initial" if revision_no == 1 else "recalculation", created_by))
    connection.execute("INSERT INTO m8_result_keys VALUES(%s,%s,%s,%s)", (cycle["id"], key, request_hash, revision_id))
    return read_results_revision(connection, revision_id)


def read_results_revision(connection, revision_id) -> dict:
    row = connection.execute("""SELECT r.*,x.cycle_db_id,x.id AS logical_id,c.cycle_id
        FROM m8_result_revisions r JOIN m8_results x ON x.id=r.results_id JOIN m5_cycles c ON c.id=x.cycle_db_id
        WHERE r.id=%s""", (UUID(str(revision_id)),)).fetchone()
    if not row:
        raise ValueError("M8_RESULTS_NOT_FOUND")
    _integrity(row["payload_json"], row["payload_checksum"])
    return {"id": str(row["logical_id"]), "revision_id": str(row["id"]), "revision_no": row["revision_no"],
            "cycle_id": str(row["cycle_id"]), "created_at": row["created_at"], "results": row["payload_json"]}


def read_latest_results(connection, cycle_id: str) -> dict:
    cycle = m7_completion._cycle(connection, cycle_id, lock=False)
    row = connection.execute("""SELECT rr.id FROM m8_results r JOIN m8_result_revisions rr ON rr.results_id=r.id
        WHERE r.cycle_db_id=%s ORDER BY rr.revision_no DESC LIMIT 1""", (cycle["id"],)).fetchone()
    if not row:
        raise ValueError("M8_RESULTS_NOT_FOUND")
    return read_results_revision(connection, row["id"])


def _admission_summary(decision: dict) -> dict:
    fields = ("schema_version", "cycle_id", "indicator_id", "considered_revision_ids",
              "interpretable_revision_ids", "included_revision_ids", "excluded_revision_ids",
              "interpretation_admissible", "numeric_admissible", "reason_code", "sufficiency",
              "source", "processing_status", "mechanism_ref")
    result = {k: decision[k] for k in fields if k in decision}
    # Provider trace contains full sent messages. C-67 receives findings, never raw prompts/material.
    result["individual"] = [{k: v for k, v in item.items() if k != "ai_trace"}
                            for item in decision.get("individual", [])]
    result["joint"] = {k: v for k, v in decision.get("joint", {}).items() if k != "ai_trace"}
    return result


def _report_content(results: dict, audience: str, target_profile: dict | None, *, connection=None) -> dict:
    package = load_report_package()
    payload = results["results"]
    if audience not in ALLOWED_AUDIENCES:
        raise ValueError("M8_AUDIENCE_INVALID")
    detail = "full" if audience == "methodology_qa" else ("summary_with_coverage" if audience == "customer" else "personal")
    skills = []
    recommendation_skills = []
    targets = {x["skill_id"]: x for x in (target_profile or {}).get("requirements", [])}
    for source in payload["assessed_skill_profile"]:
        item = dict(source)
        item["comparison"] = _comparison(source, targets.get(source["skill_id"])) if target_profile else source["comparison"]
        recommendation_skills.append(dict(item))
        if audience == "assessee":
            item.pop("components", None)
        skills.append(item)
    admission_summary = [_admission_summary(d) for d in payload.get("admissions", []) if d.get("schema_version") == 2]
    recommendation_payload = {**payload, "assessed_skill_profile": recommendation_skills,
                              "admissions": [_admission_summary(d) if d.get("schema_version") == 2 else d
                                             for d in payload.get("admissions", [])],
                              "target_profile": target_profile or payload.get("target_profile")}
    try:
        from Api.m8_recommendation_basis import resolve
        resolved = resolve(connection, results) if connection is not None else None
        if resolved is not None:
            resolved = {**resolved, "results_checksum": checksum(recommendation_payload)}
        recommendation_generation = generate_recommendations(
            {**recommendation_payload, "results_revision_id": results["revision_id"]},
            payload.get("personalized_profile_snapshot"), resolved=resolved,
        )
    except (ValueError, KeyError, OSError) as exc:
        recommendation_generation = {
            "contract_version": "m8-recommendations/1.2.0",
            "mechanism": None,
            "input": {"results_revision_id": results["revision_id"], "profile_ref": payload.get("profile_ref")},
            "input_checksum": None,
            "recommendations": [],
            "notices": [package["template"]["recommendation_failure_notice"]],
            "status": "failed", "failure_reason": "RECOMMENDATION_GENERATION_FAILED",
        }
    return {"schema_version": 1, "contract": "C-67", "message_version": "1.1", "owner": "PM-06", "consumer": "PM-07",
            "results_id": results["id"], "results_revision_id": results["revision_id"],
            "results_revision_no": results["revision_no"], "cycle_id": results["cycle_id"], "audience": audience,
            "disclosure": detail, "profile_ref": payload["profile_ref"], "role_ref": payload["role_ref"],
            "goal": payload["goal"], "time": payload["time"], "collection": payload["collection"],
            "sessions": payload["sessions"], "assessment_situations": payload["assessment_situations"],
            "skills": skills, "competencies": payload["competencies"], "coverage": payload["coverage"],
            "confidence": payload["confidence"], "reliability": payload["reliability"],
            "limitations": payload["limitations"], "target_profile": target_profile or payload.get("target_profile"),
            "provenance": {"composition_checksum": payload["composition_checksum"], "c46_ref": payload["c46_ref"],
                           "c56_ref": payload["c56_ref"], "sources": payload["sources"], "algorithm": payload["algorithm"]},
            "admission_summary": admission_summary, "processing": payload.get("processing", {
                "contract_version":"m10-processing-recovery/1.0.0","status":"completed",
                "stage":"substantive_admission","error_code":None,"affected_indicator_ids":[],
                "message":"Обработка завершена.","allowed_actions":[]}),
            "report_mechanism": {"id": package["manifest"]["id"], "version": package["manifest"]["version"],
                                 "checksum": package["template_hash"]},
            "recommendation_generation": recommendation_generation,
            "recommendations": recommendation_generation["recommendations"],
            "recommendation_notices": recommendation_generation["notices"]}


def create_report(connection, *, results_revision_id: str, audience: str, key: str,
                  target_profile: dict | None, created_by: int) -> dict:
    results = read_results_revision(connection, results_revision_id)
    request = {"audience": audience, "target_profile": target_profile, "template_version": REPORT_TEMPLATE_VERSION}
    request_hash = checksum(request)
    prior = connection.execute("SELECT id,request_hash FROM m8_reports WHERE result_revision_id=%s AND request_key=%s",
                               (UUID(results_revision_id), key)).fetchone()
    if prior:
        if prior["request_hash"] != request_hash:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return read_report(connection, prior["id"])
    revision_no = connection.execute("SELECT COALESCE(MAX(revision_no),0)+1 AS n FROM m8_reports WHERE result_revision_id=%s",
                                     (UUID(results_revision_id),)).fetchone()["n"]
    report_id = uuid4()
    c67 = _report_content(results, audience, target_profile, connection=connection)
    c67["report_id"] = str(report_id); c67["report_revision_no"] = revision_no
    c67["template_version"] = REPORT_TEMPLATE_VERSION
    target_hash = checksum(target_profile) if target_profile else None
    connection.execute("""INSERT INTO m8_reports
        (id,result_revision_id,revision_no,audience,target_profile_json,target_profile_checksum,template_version,c67_json,c67_checksum,status,request_key,request_hash,created_by)
        VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s,'ready',%s,%s,%s)""",
        (report_id, UUID(results_revision_id), revision_no, audience, json.dumps(target_profile) if target_profile else None,
         target_hash, REPORT_TEMPLATE_VERSION, json.dumps(c67, ensure_ascii=False), checksum(c67), key, request_hash, created_by))
    return read_report(connection, report_id)


OWNER_CYCLE_SCOPE = """c.owner_user_id=%s AND c.usage_scope='assessment'
    AND EXISTS (SELECT 1 FROM organization_memberships member
        JOIN organizations org ON org.id=member.organization_id
        WHERE member.user_id=c.owner_user_id AND member.organization_id=c.organization_id
          AND org.is_active=TRUE)"""


def owner_can_read_cycle(connection, cycle_id: str, user_id: int) -> bool:
    return connection.execute("SELECT c.id FROM m5_cycles c WHERE c.cycle_id=%s AND " + OWNER_CYCLE_SCOPE,
                              (UUID(str(cycle_id)), user_id)).fetchone() is not None


def list_owned_cycles(connection, user_id: int) -> list[dict]:
    """Read-only owner history; one card per Cycle, revisions never count as Cycles."""
    rows = connection.execute("""SELECT c.cycle_id,c.status AS cycle_status,
        c.created_at AS cycle_created_at,c.started_at,c.collection_closed_at,
        pipeline.status AS processing_status,pipeline.stage AS processing_stage,
        (to_jsonb(pipeline)->>'error_code') AS processing_error,
        rr.id AS results_revision_id,rr.revision_no AS results_revision_no,
        p.id AS report_id,p.revision_no,p.created_at
        FROM m5_cycles c
        LEFT JOIN m10_pipeline_runs pipeline ON pipeline.cycle_db_id=c.id
        LEFT JOIN m8_results r ON r.cycle_db_id=c.id
        LEFT JOIN m8_result_revisions rr ON rr.results_id=r.id
        LEFT JOIN m8_reports p ON p.result_revision_id=rr.id AND p.audience='assessee'
        WHERE """ + OWNER_CYCLE_SCOPE + """
        ORDER BY c.created_at DESC,c.id DESC,rr.revision_no DESC NULLS LAST,
                 p.revision_no DESC NULLS LAST""", (user_id,)).fetchall()
    cycles = {}
    for row in rows:
        cid = str(row['cycle_id'])
        item = cycles.setdefault(cid, {
            'cycle_id':cid, 'cycle_status':row['cycle_status'],
            'cycle_created_at':row['cycle_created_at'], 'started_at':row['started_at'],
            'collection_closed_at':row['collection_closed_at'],
            'processing_status':row['processing_status'], 'processing_stage':row['processing_stage'],
            'processing_error':row['processing_error'],
            'processing_message':('Не удалось завершить техническую обработку. Сохранённые ответы не потеряны.'
                                  if row['processing_status']=='failed' else None),
            'allowed_actions':[],
            'results_revision_id':str(row['results_revision_id']) if row['results_revision_id'] else None,
            'results_revision_no':row['results_revision_no'],
            'latest_results_revision_id':str(row['results_revision_id']) if row['results_revision_id'] else None,
            'latest_results_revision_no':row['results_revision_no'],
            'report_id':None, 'revision_no':None, 'created_at':row['cycle_created_at'], 'versions':[]})
        if row['report_id']:
            version = {'cycle_id':cid,'report_id':str(row['report_id']), 'revision_no':row['revision_no'],
                'created_at':row['created_at'],'results_revision_id':str(row['results_revision_id']),
                'results_revision_no':row['results_revision_no']}
            item['versions'].append(version)
            if item['report_id'] is None:
                item.update({k:version[k] for k in ('report_id','revision_no','created_at','results_revision_id','results_revision_no')})
    for item in cycles.values():
        item['status'] = ('failed' if item['processing_status']=='failed' or item['cycle_status']=='failed' else
            'report_ready' if item['report_id'] else
            'results_ready' if item['results_revision_id'] else
            'processing' if item['cycle_status'] in {'collection_closed','calculation_pending','calculated'} else 'collecting')
    return list(cycles.values())


def list_owned_reports(connection, user_id: int) -> list[dict]:
    return [item for item in list_owned_cycles(connection, user_id) if item['report_id']]


def read_report(connection, report_id) -> dict:
    row = connection.execute("""SELECT p.*,r.payload_json AS results_payload,x.cycle_db_id,c.cycle_id,c.owner_user_id
        FROM m8_reports p JOIN m8_result_revisions r ON r.id=p.result_revision_id
        JOIN m8_results x ON x.id=r.results_id JOIN m5_cycles c ON c.id=x.cycle_db_id WHERE p.id=%s""",
        (UUID(str(report_id)),)).fetchone()
    if not row:
        raise ValueError("M8_REPORT_NOT_FOUND")
    _integrity(row["c67_json"], row["c67_checksum"])
    if row["target_profile_json"] is not None and checksum(row["target_profile_json"]) != row["target_profile_checksum"]:
        raise ValueError("CHECKSUM_MISMATCH")
    presented = _present_report(row["c67_json"])
    if presented.get("recommendations"):
        try:
            from Api.m8_recommendation_basis import resolve
            verified = resolve(connection, read_results_revision(connection, row["result_revision_id"]))
            prior = presented["recommendation_generation"]["input"]["resolved"]
            if any(verified.get(k) != prior.get(k) for k in ("cycle_id", "results_revision_id", "c56_checksum", "projections")):
                raise ValueError("RECOMMENDATION_SAVED_INPUT_MISMATCH")
        except (ValueError, KeyError, TypeError, OSError):
            presented["recommendations"] = []
            presented["recommendation_notices"] = [load_report_package()["template"]["recommendation_failure_notice"]]
            presented["recommendation_generation"] = {"status":"failed", "failure_reason":"BASIS_VALIDATION_FAILED",
                "recommendations":[], "notices":presented["recommendation_notices"]}
    return {"id": str(row["id"]), "revision_no": row["revision_no"], "audience": row["audience"],
            "status": row["status"], "cycle_id": str(row["cycle_id"]), "owner_user_id": row["owner_user_id"],
            "results_revision_id": str(row["result_revision_id"]), "created_at": row["created_at"], "c67": presented}


def _present_report(saved: dict) -> dict:
    """Pure projection: immutable historical C-67 remains untouched; no generation on GET."""
    from copy import deepcopy
    from Api.m8_recommendations import CONTRACT_VERSION, VERIFIED_CONTRACT_VERSIONS
    c67 = deepcopy(saved)
    generation = c67.get("recommendation_generation") or {}
    if generation.get("contract_version") not in VERIFIED_CONTRACT_VERSIONS and c67.get("recommendations"):
        c67["recommendations"] = []
        c67["recommendation_notices"] = [load_report_package()["template"]["legacy_recommendation_notice"]]
        c67["recommendation_generation"] = {"contract_version":generation.get("contract_version"),
            "status":"unavailable", "failure_reason":None, "recommendations":[],
            "notices":c67["recommendation_notices"]}
        c67["recommendation_presentation"] = {"policy_version":CONTRACT_VERSION, "status":"legacy_unverified"}
    return c67


def read_latest_report(connection, cycle_id: str, audience: str) -> dict:
    cycle = m7_completion._cycle(connection, cycle_id, lock=False)
    row = connection.execute("""SELECT p.id FROM m8_reports p JOIN m8_result_revisions rr ON rr.id=p.result_revision_id
        JOIN m8_results r ON r.id=rr.results_id WHERE r.cycle_db_id=%s AND p.audience=%s
        ORDER BY rr.revision_no DESC,p.revision_no DESC LIMIT 1""", (cycle["id"], audience)).fetchone()
    if not row:
        raise ValueError("M8_REPORT_NOT_FOUND")
    return read_report(connection, row["id"])


def render_pdf(report: dict) -> bytes:
    package = load_report_package(); labels = package["template"]["outcome_labels"]
    c67 = _present_report(report["c67"])
    skills = []
    for skill in c67["skills"]:
        score = skill.get("score")
        skills.append({
            "name": skill.get("skill_name") or skill["skill_id"],
            "outcome": labels.get(skill["outcome"], skill["outcome"]),
            "score": "—" if score is None else f"{score['numerator']}/{score['denominator']} ({score['value']})",
            "completeness": skill.get("completeness") or "—",
        })
    coverage = []
    for scope, cuts in c67["coverage"].items():
        if not isinstance(cuts, dict):
            continue
        for name, cut in cuts.items():
            if not isinstance(cut, dict) or "ratio" not in cut:
                continue
            ratio = "не определено" if cut["ratio"] is None else f"{cut['numerator']}/{cut['denominator']} ({cut['ratio'] * 100:.1f}%)"
            coverage.append({"scope": scope, "name": name, "ratio": ratio})
    payload = {
        "title": "4K — базовый индивидуальный отчёт",
        "cycle_id": c67["cycle_id"],
        "results_revision_no": c67["results_revision_no"],
        "report_revision_no": report["revision_no"],
        "skills": skills,
        "coverage": coverage,
        "limitations": c67["limitations"],
        "processing": c67.get("processing", {"status":"completed","message":"Обработка завершена."}),
        "recommendations": c67.get("recommendations", []),
        "recommendation_notices": c67.get("recommendation_notices", []),
        "reliability": c67["reliability"].get("status", "not_provided"),
    }
    return render_typst_report(payload, "m8_basic_report.typ")
