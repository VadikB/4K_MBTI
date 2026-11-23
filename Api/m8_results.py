from __future__ import annotations

import json
from collections import defaultdict
from uuid import UUID, uuid4

from Api.assessment_configuration import definition_checksum
from Api.m5_case_runtime import checksum
from Api import m7_completion
from Api import m6_cycle_aggregation_repository as calculations
from Api.m8_report_package import load_package as load_report_package
from Api.typst_pdf_renderer import render_typst_report
from Api.cycle_execution_manifest import resolve_cycle_dependency

RESULTS_VERSION = "m8-results/1.0.0"
REPORT_TEMPLATE_VERSION = "m8-basic-report/1.5.0"
ALLOWED_AUDIENCES = {"assessee", "customer", "methodology_qa"}


def _cycle_report_packages(connection, cycle_id: str):
    cycle = m7_completion._cycle(connection, cycle_id, lock=False)
    report = resolve_cycle_dependency(cycle, "m8_report_projection")
    descriptive = resolve_cycle_dependency(cycle, "m8_descriptive_report")
    source_set = resolve_cycle_dependency(cycle, "source_set")
    return cycle, report, descriptive, source_set


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
                "skill_description": skill.get("function") or skill.get("place_in_logic") or "",
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


def _partial_result_projection(c46: dict, c56: dict, processing: dict, template: dict) -> dict:
    situations = list(c56["cycle_context"].get("assessment_situations") or [])
    route = list((c46["payload_json"].get("plan") or {}).get("untraversed_route") or [])
    positions = list((c46["payload_json"].get("route") or {}).get("positions") or [])
    planned = len(route)
    presented = [x for x in situations if x.get("handoff_id") or x.get("status") not in {"prepared", "admitted"}]
    completed = [x for x in situations if x.get("handoff_id")]
    interrupted = [x for x in presented if x.get("status") in {"terminated", "closed"} and not x.get("handoff_id")]
    presented_count = (sum(value.get("state") not in {"not_presented", None} for value in positions)
                       if positions else len(presented))
    not_presented = max(0, planned - presented_count)
    full_cut = c56["coverage"]["full_m2"]["indicator_assessments"]
    plan_cut = c56["coverage"]["cycle_plan"]["indicator_assessments"]
    codes = []
    if c56["coverage"]["cycle_plan"]["indicator_assessments"]["denominator"] < full_cut["denominator"]:
        codes.append("plan_scope")
    close_reason = str(c46["payload_json"].get("collection", {}).get("reason") or "")
    completed_positions = {int(value["position_no"]) for value in positions
                           if value.get("state") == "completed" and value.get("position_no") is not None}
    plan_complete = (planned > 0 and len(completed_positions) >= planned
                     if positions else planned > 0 and len(completed) >= planned and not interrupted)
    if not plan_complete:
        codes.append("collection_incomplete")
    if plan_cut["numerator"] < plan_cut["denominator"]:
        codes.append("observation_missing")
    if processing["status"] == "failed":
        codes.append("technical_failure")
    messages = template["partial_result"]
    reason_messages = messages["reasons"]
    result = {
        "contract_version": "m8-partial-result/1.1.0",
        "is_incomplete": not plan_complete, "plan_completed": plan_complete,
        "plan_scope_limited": "plan_scope" in codes,
        "observation_limited": "observation_missing" in codes,
        "context_limited": "context_limited" in codes,
        "source_limited": bool(c56.get("limitations")),
        "technical_failure": "technical_failure" in codes,
        "close_reason": close_reason,
        "progress": {"completed": len(completed_positions) if positions else len(completed), "planned": planned,
                     "presented": presented_count, "interrupted": len(interrupted),
                     "not_presented": not_presented,
                     "formula": "completed AS with final handoff / immutable accepted plan route"},
        "plan_revision_id": (c46["payload_json"].get("plan") or {}).get("revision_id"),
        "limitation_reasons": [{"code": code, "message": reason_messages.get(code, messages.get("unknown_reason") or messages["not_inferred"])} for code in dict.fromkeys(codes)],
        "messages": {"title": (messages.get("completed_title") or "Оценка завершена") if plan_complete else messages["incomplete_title"],
                     "confirmed": messages["confirmed"], "not_inferred": messages["not_inferred"]},
    }
    return result


def _skill_presentation(skill: dict, c56: dict, c46: dict, processing: dict, template: dict) -> dict:
    """Explain an M6 outcome using saved composition and plan facts, without scoring."""
    copy = template["skill_result"]
    components = skill.get("components") or []
    required = {str(value) for component in components for value in component.get("required_indicator_ids") or []}
    included = {str(value) for component in components for value in component.get("included_indicator_ids") or []}
    planned = {str(value["indicator_id"]) for value in c56.get("planned_target_set") or []}
    outcome = skill.get("outcome")
    codes = []
    if required and required - planned:
        codes.append("plan_scope")
    if outcome == "partial_score":
        codes.append("partial_composition")
    elif outcome == "result_without_score":
        codes.append("numeric_not_admissible")
    elif outcome == "no_result":
        codes.append("no_justified_result")
    affected = {str(value) for value in processing.get("affected_indicator_ids") or []}
    if required & affected:
        codes.append("technical_failure")
    source_reasons = (c56.get("coverage") or {}).get("full_m2", {}).get("admissible_contributions", {}).get("missing_reasons") or {}
    source_codes = sorted({str(source_reasons[value]) for value in required - included if value in source_reasons})
    plan = c46["payload_json"].get("plan") or {}
    route = list(plan.get("untraversed_route") or [])
    positions = {int(value["position_no"]): value for value in (c46["payload_json"].get("route") or {}).get("positions") or []
                 if value.get("position_no") is not None}
    remaining_targets = set()
    targets_known = bool(route and required)
    for index, item in enumerate(route, 1):
        position = positions.get(index)
        if position and position.get("state") == "completed":
            continue
        target_ids = (position.get("expected_targets") if position else None) or item.get("purpose_target_ids")
        if not isinstance(target_ids, list):
            targets_known = False
            continue
        remaining_targets.update(str(value) for value in target_ids)
    return {
        "outcome": outcome,
        "label": copy["outcomes"].get(outcome, copy["unknown_outcome"]),
        "reasons": ([{"code": code, "message": copy["reasons"].get(code, copy["unknown_reason"])} for code in codes]
                    + [{"code": code, "message": copy["source_reasons"].get(code, copy["unknown_reason"])}
                       for code in source_codes]),
        "source_reason_codes": source_codes,
        "required_indicator_ids": sorted(required),
        "included_indicator_ids": sorted(included),
        "missing_indicator_ids": sorted(required - included),
        "planned_indicator_ids": sorted(required & planned),
        "remaining_plan_relevant": bool(required & remaining_targets) if targets_known else None,
    }


def _coverage_context(c46: dict, c56: dict) -> dict:
    """Describe coverage scopes without turning them into an assessment score."""
    full_ids = {str(item["indicator_id"]) for item in c56.get("full_target_set") or []}
    planned_ids = {str(item["indicator_id"]) for item in c56.get("planned_target_set") or []}
    plan = c46.get("payload_json", {}).get("plan") or {}
    catalog_ids = {
        str(indicator_id)
        for route_item in plan.get("untraversed_route") or []
        for indicator_id in route_item.get("purpose_target_ids") or []
    } & full_ids
    full_coverage = c56.get("coverage", {}).get("full_m2", {})

    def cut(ids: set[str], denominator: int) -> dict:
        return {
            "numerator": len(ids),
            "denominator": denominator,
            "ratio": (len(ids) / denominator) if denominator else None,
        }

    return {
        "contract_version": "m8-coverage-context/1.0.0",
        "not_a_score": True,
        "catalog_possibility": {
            **cut(catalog_ids, len(full_ids)),
            "meaning": "IndicatorID addressable by the immutable accepted Cycle route",
        },
        "cycle_plan": {
            **cut(planned_ids, len(full_ids)),
            "meaning": "IndicatorID selected for this Cycle; it does not guarantee an opportunity or Evidence",
        },
        "actual_trajectory": {
            "opportunities": full_coverage.get("opportunities"),
            "indicator_assessments": full_coverage.get("indicator_assessments"),
            "admissible_contributions": full_coverage.get("admissible_contributions"),
            "meaning": "Observed opportunities, final IA and admitted contributions are separate facts",
        },
        "result_sufficiency": {
            "skill_outcomes": [
                {"skill_id": item.get("skill_id"), "outcome": item.get("outcome")}
                for item in c56.get("skill_outcomes") or []
            ],
            "meaning": "Result sufficiency is determined by M6/M8 rules, not by catalog or plan coverage",
        },
    }


def _build_payload(cycle: dict, c46: dict, calculation: dict, target_profile: dict | None,
                   profile_snapshot: dict | None, report_template: dict | None = None) -> dict:
    display_snapshot = cycle.get("display_snapshot_json")
    if display_snapshot is not None and checksum(display_snapshot) != cycle.get("display_snapshot_checksum"):
        raise ValueError("CHECKSUM_MISMATCH")
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
    partial_result = _partial_result_projection(
        c46, c56, processing,
        report_template if report_template is not None else load_report_package()["template"],
    )
    skill_template = report_template if report_template is not None else load_report_package()["template"]
    if "skill_result" in skill_template:
        for skill in skills:
            skill["presentation"] = _skill_presentation(skill, c56, c46, processing, skill_template)
    limitations += [x["message"] for x in partial_result["limitation_reasons"]]
    plan = c46["payload_json"].get("plan") or {}
    return_policy = plan.get("return_policy_snapshot") or {}
    result = {
        "schema_version": 1, "results_version": RESULTS_VERSION, "cycle_id": str(cycle["cycle_id"]),
        "subject_user_id": cycle["owner_user_id"], "profile_ref": cycle["profile_ref_json"],
        "personalized_profile_snapshot": profile_snapshot,
        "display_snapshot": display_snapshot,
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
        "coverage": c56["coverage"], "coverage_context": _coverage_context(c46, c56),
        "admissions": c56["admissions"], "observations": c56["observations"],
        "confidence": c56["confidence"], "reliability": c56["reliability"],
        "limitations": list(dict.fromkeys(limitations)), "processing": processing,
        "partial_result": partial_result,
        "comparison_evidence": {
            "contract_version": "m8-comparison-evidence/1.0.0",
            "semantic_composition": {
                "full_target_set_checksum": checksum(c56["full_target_set"]),
            },
            "assessment_conditions": {
                "time_budget_seconds": c46["payload_json"]["time"].get("budget_seconds"),
                "calendar_window_seconds": c46["payload_json"]["time"].get("calendar_window_seconds"),
                "return_policy_checksum": return_policy.get("checksum"),
            },
        },
        "target_profile": target_profile, "sources": c56["sources"], "algorithm": c56["algorithm"],
    }
    if cycle["usage_scope"] == "qa":
        result["test_result"] = {"synthetic": True, "usage_scope": "qa",
                                 "participant_assessment": False}
    return result


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
    report_path = resolve_cycle_dependency(cycle, "m8_report_projection")
    source_set = resolve_cycle_dependency(cycle, "source_set")
    report_template = load_report_package(report_path, source_set / "manifest.json")["template"]
    payload = _build_payload(cycle, c46, calculation, target_profile, profile_snapshot, report_template)
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


def _report_content(results: dict, audience: str, target_profile: dict | None, *, connection=None, gateway=None,
                    descriptive_override: dict | None = None) -> dict:
    if connection is None:
        # Pure projection support for unit consumers; persisted report creation always
        # supplies a connection and therefore must resolve the frozen Cycle manifest.
        package = load_report_package()
        descriptive_path = None
    else:
        _, report_path, descriptive_path, source_set = _cycle_report_packages(connection, results["cycle_id"])
        package = load_report_package(report_path, source_set / "manifest.json")
    payload = results["results"]
    if audience not in ALLOWED_AUDIENCES:
        raise ValueError("M8_AUDIENCE_INVALID")
    detail = "full" if audience == "methodology_qa" else ("summary_with_coverage" if audience == "customer" else "personal")
    skills = []
    targets = {x["skill_id"]: x for x in (target_profile or {}).get("requirements", [])}
    for source in payload["assessed_skill_profile"]:
        item = dict(source)
        item["comparison"] = _comparison(source, targets.get(source["skill_id"])) if target_profile else source["comparison"]
        if audience == "assessee":
            item.pop("components", None)
        skills.append(item)
    admission_summary = [_admission_summary(d) for d in payload.get("admissions", []) if d.get("schema_version") == 2]
    descriptive = descriptive_override or {
        "contract_version":"m8-descriptive-report/1.2.0", "status":"failed",
        "failure_reason":"DESCRIPTION_GENERATION_FAILED", "summary":[], "claims":[]}
    if descriptive_override is None:
        try:
            from Api.m8_recommendation_basis import resolve
            from Api.m8_descriptive_report import generate
            kwargs = {"gateway": gateway}
            if descriptive_path is not None:
                kwargs["package_path"] = descriptive_path
            descriptive = generate(results, resolve(connection, results), **kwargs)
        except (ValueError, KeyError, OSError):
            pass
    report = {"schema_version": 1, "contract": "C-67", "message_version": "1.1", "owner": "PM-06", "consumer": "PM-07",
            "results_id": results["id"], "results_revision_id": results["revision_id"],
            "results_revision_no": results["revision_no"], "cycle_id": results["cycle_id"], "audience": audience,
            "disclosure": detail, "profile_ref": payload["profile_ref"], "role_ref": payload["role_ref"],
            "display": payload.get("display_snapshot"),
            "goal": payload["goal"], "time": payload["time"], "collection": payload["collection"],
            "sessions": payload["sessions"], "assessment_situations": payload["assessment_situations"],
            "skills": skills, "competencies": payload["competencies"], "coverage": payload["coverage"],
            "coverage_context": payload.get("coverage_context"),
            "confidence": payload["confidence"], "reliability": payload["reliability"],
            "limitations": payload["limitations"], "target_profile": target_profile or payload.get("target_profile"),
            "partial_result": payload.get("partial_result"),
            "provenance": {"composition_checksum": payload["composition_checksum"], "c46_ref": payload["c46_ref"],
                           "c56_ref": payload["c56_ref"], "sources": payload["sources"], "algorithm": payload["algorithm"],
                           "comparison_evidence": payload.get("comparison_evidence")},
            "admission_summary": admission_summary, "processing": payload.get("processing", {
                "contract_version":"m10-processing-recovery/1.0.0","status":"completed",
                "stage":"substantive_admission","error_code":None,"affected_indicator_ids":[],
                "message":"Обработка завершена.","allowed_actions":[]}),
            "report_mechanism": {"id": package["manifest"]["id"], "version": package["manifest"]["version"],
                                 "checksum": package["template_hash"]},
            "descriptive": descriptive, "recommendations": [], "recommendation_notices": []}
    if payload.get("test_result"):
        report["test_result"] = payload["test_result"]
    return report


def create_report(connection, *, results_revision_id: str, audience: str, key: str,
                  target_profile: dict | None, created_by: int, gateway=None,
                  descriptive_override: dict | None = None) -> dict:
    results = read_results_revision(connection, results_revision_id)
    _, report_path, _, source_set = _cycle_report_packages(connection, results["cycle_id"])
    package = load_report_package(report_path, source_set / "manifest.json")
    template_version = "m8-basic-report/" + package["manifest"]["version"]
    request = {"audience": audience, "target_profile": target_profile, "template_version": template_version}
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
    c67 = _report_content(results, audience, target_profile, connection=connection, gateway=gateway,
                          descriptive_override=descriptive_override)
    c67["report_id"] = str(report_id); c67["report_revision_no"] = revision_no
    c67["template_version"] = template_version
    target_hash = checksum(target_profile) if target_profile else None
    connection.execute("""INSERT INTO m8_reports
        (id,result_revision_id,revision_no,audience,target_profile_json,target_profile_checksum,template_version,c67_json,c67_checksum,status,request_key,request_hash,created_by)
        VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s,'ready',%s,%s,%s)""",
        (report_id, UUID(results_revision_id), revision_no, audience, json.dumps(target_profile) if target_profile else None,
         target_hash, template_version, json.dumps(c67, ensure_ascii=False), checksum(c67), key, request_hash, created_by))
    return read_report(connection, report_id)


def create_report_detached(*, results_revision_id: str, audience: str, key: str,
                           target_profile: dict | None, created_by: int, gateway=None,
                           connection_factory=None, service_recovery: bool = False,
                           claim_cycle_db_id: int | None = None, claim_token=None) -> dict:
    """Generate and validate descriptive content outside the DB transaction."""
    if connection_factory is None:
        from Api.database import get_connection as connection_factory
    from Api.m8_recommendation_basis import resolve
    from Api.m8_descriptive_report import generate
    with connection_factory() as connection:
        results = read_results_revision(connection, results_revision_id)
        _, report_path, _, source_set = _cycle_report_packages(connection, results["cycle_id"])
        template_version = "m8-basic-report/" + load_report_package(report_path, source_set / "manifest.json")["manifest"]["version"]
        request = {"audience": audience, "target_profile": target_profile,
                   "template_version": template_version}
        request_hash = checksum(request)
        prior = connection.execute(
            "SELECT id,request_hash FROM m8_reports WHERE result_revision_id=%s AND request_key=%s",
            (UUID(results_revision_id), key),
        ).fetchone()
        if prior:
            if prior["request_hash"] != request_hash:
                raise ValueError("IDEMPOTENCY_CONFLICT")
            return read_report(connection, prior["id"])
        if audience == "assessee" and not service_recovery:
            existing = connection.execute("""SELECT p.id FROM m8_results r
                JOIN m8_result_revisions rr ON rr.results_id=r.id
                JOIN m8_reports p ON p.result_revision_id=rr.id
                WHERE r.cycle_db_id=(SELECT cycle_db_id FROM m8_results WHERE id=%s)
                  AND p.audience='assessee' AND p.status='ready' LIMIT 1""",
                (UUID(results["id"]),)).fetchone()
            if existing:
                raise ValueError("M8_REPORT_ALREADY_PUBLISHED")
        _, _, descriptive_path, _ = _cycle_report_packages(connection, results["cycle_id"])
        resolved = resolve(connection, results)
        frozen_checksum = checksum({"revision_id": results["revision_id"], "results": results["results"]})
        connection.commit()
    descriptive = generate(results, resolved, gateway=gateway, package_path=descriptive_path)
    if audience == "assessee" and (descriptive.get("status") != "ready"
                                  or not (descriptive.get("summary") or descriptive.get("claims"))):
        raise ValueError("M8_REPORT_CONTENT_NOT_PUBLISHABLE")
    with connection_factory() as connection:
        if audience == "assessee":
            # Serialize publication across revisions and API callers on the
            # stable Cycle row, then recheck after detached generation.
            connection.execute("SELECT id FROM m5_cycles WHERE cycle_id=%s FOR UPDATE",
                               (UUID(results["cycle_id"]),)).fetchone()
        if claim_cycle_db_id is not None:
            claimed = connection.execute("""SELECT 1 FROM m10_report_claims
                WHERE cycle_db_id=%s AND token=%s AND lease_until > NOW()""",
                (claim_cycle_db_id, claim_token)).fetchone()
            if not claimed:
                raise ValueError("M10_REPORT_CLAIM_LOST")
        current = read_results_revision(connection, results_revision_id)
        if checksum({"revision_id": current["revision_id"], "results": current["results"]}) != frozen_checksum:
            raise ValueError("M8_RESULTS_REVISION_CHANGED")
        if audience == "assessee" and not service_recovery:
            existing = connection.execute("""SELECT p.id FROM m8_results r
                JOIN m8_result_revisions rr ON rr.results_id=r.id
                JOIN m8_reports p ON p.result_revision_id=rr.id
                WHERE r.cycle_db_id=(SELECT cycle_db_id FROM m8_results WHERE id=%s)
                  AND p.audience='assessee' AND p.status='ready' LIMIT 1""",
                (UUID(results["id"]),)).fetchone()
            if existing:
                raise ValueError("M8_REPORT_ALREADY_PUBLISHED")
        saved = create_report(
            connection, results_revision_id=results_revision_id, audience=audience, key=key,
            target_profile=target_profile, created_by=created_by,
            descriptive_override=descriptive,
        )
        connection.commit()
        return saved


OWNER_CYCLE_SCOPE = "c.owner_user_id=%s AND c.usage_scope='assessment'"


def owner_can_read_cycle(connection, cycle_id: str, user_id: int) -> bool:
    from Api.qa_orchestration import permits
    row = connection.execute("""SELECT c.id,c.usage_scope FROM m5_cycles c WHERE c.cycle_id=%s
        AND c.owner_user_id=%s""", (UUID(str(cycle_id)), user_id)).fetchone()
    return bool(row and permits(row["usage_scope"]))


def is_limited_report(status: str | None, partial: dict | None) -> bool:
    partial = partial if isinstance(partial, dict) else {}
    progress = partial.get("progress")
    progress = progress if isinstance(progress, dict) else {}
    completed, planned = progress.get("completed"), progress.get("planned")
    incomplete = (type(completed) is int and type(planned) is int and planned > 0
                  and (completed < planned or bool(progress.get("interrupted"))))
    return bool(status == "limited" or partial.get("plan_completed") is False
                or partial.get("limitation_reasons") or incomplete
                or any(partial.get(key) is True for key in (
                    "is_incomplete", "plan_scope_limited", "observation_limited",
                    "context_limited", "source_limited", "technical_failure")))


def list_owned_cycles(connection, user_id: int) -> list[dict]:
    """Read-only owner history; one card per Cycle, revisions never count as Cycles."""
    from Api.qa_orchestration import sql_scope
    owner_scope = OWNER_CYCLE_SCOPE.replace("c.usage_scope='assessment'", sql_scope("c"))
    rows = connection.execute("""SELECT c.cycle_id,c.status AS cycle_status,
        c.created_at AS cycle_created_at,c.started_at,c.collection_closed_at,
        COALESCE(p.c67_json->'display'->>'program_name',c.display_snapshot_json->>'program_name') AS program_name,
        pipeline.status AS processing_status,pipeline.stage AS processing_stage,
        (to_jsonb(pipeline)->>'error_code') AS processing_error,
        rr.id AS results_revision_id,rr.revision_no AS results_revision_no,
        p.id AS report_id,p.revision_no,p.created_at,to_jsonb(p)->>'status' AS report_status,
        p.c67_json->'partial_result' AS report_partial_result,
        to_jsonb(p)->'c67_json'->'processing'->>'status' AS report_processing_status
        FROM m5_cycles c
        LEFT JOIN m10_pipeline_runs pipeline ON pipeline.cycle_db_id=c.id
        LEFT JOIN m8_results r ON r.cycle_db_id=c.id
        LEFT JOIN m8_result_revisions rr ON rr.results_id=r.id
        LEFT JOIN m8_reports p ON p.result_revision_id=rr.id AND p.audience='assessee'
        WHERE """ + owner_scope + """
        ORDER BY COALESCE(c.collection_closed_at,c.created_at) DESC,c.id DESC,
                 (p.id=(SELECT current.report_id FROM m8_published_reports current
                        WHERE current.cycle_db_id=c.id)) DESC NULLS LAST,
                 rr.revision_no DESC NULLS LAST,
                 p.revision_no DESC NULLS LAST""", (user_id,)).fetchall()
    cycles = {}
    for row in rows:
        cid = str(row['cycle_id'])
        item = cycles.setdefault(cid, {
            'cycle_id':cid, 'cycle_status':row['cycle_status'],
            'program_name':row['program_name'],
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
            'report_id':None, 'revision_no':None, 'created_at':row['cycle_created_at'], 'versions':[],
            'report_processing_status':None})
        if (row['results_revision_no'] is not None and
                (item['latest_results_revision_no'] is None or
                 row['results_revision_no'] > item['latest_results_revision_no'])):
            item['latest_results_revision_id'] = str(row['results_revision_id'])
            item['latest_results_revision_no'] = row['results_revision_no']
        if row['report_id']:
            version = {'cycle_id':cid,'report_id':str(row['report_id']), 'revision_no':row['revision_no'],
                'created_at':row['created_at'],'results_revision_id':str(row['results_revision_id']),
                'results_revision_no':row['results_revision_no']}
            item['versions'].append(version)
            if item['report_id'] is None:
                item.update({k:version[k] for k in ('report_id','revision_no','created_at','results_revision_id','results_revision_no')})
                item['report_processing_status'] = row['report_processing_status']
                item['report_limited'] = is_limited_report(row['report_status'], row['report_partial_result'])
    for item in cycles.values():
        item['status'] = ('report_ready' if item['report_id'] and item['report_processing_status'] != 'failed' else
            'failed' if item['processing_status']=='failed' or item['cycle_status']=='failed' else
            'results_ready' if item['results_revision_id'] else
            'processing' if item['cycle_status'] in {'collection_closed','calculation_pending','calculated'} else 'collecting')
        if item['status'] == 'report_ready':
            item['processing_message'] = None
    return list(cycles.values())


def list_owned_reports(connection, user_id: int) -> list[dict]:
    return [item for item in list_owned_cycles(connection, user_id) if item['report_id']]


def read_report(connection, report_id) -> dict:
    row = connection.execute("""SELECT p.*,r.payload_json AS results_payload,x.cycle_db_id,c.cycle_id,c.owner_user_id,
        c.collection_closed_at,
        to_jsonb(participant)->>'full_name' AS participant_name
        FROM m8_reports p JOIN m8_result_revisions r ON r.id=p.result_revision_id
        JOIN m8_results x ON x.id=r.results_id JOIN m5_cycles c ON c.id=x.cycle_db_id
        LEFT JOIN users participant ON participant.id=c.owner_user_id
        WHERE p.id=%s""",
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
            "results_revision_id": str(row["result_revision_id"]), "created_at": row["created_at"],
            "program_name": (row["c67_json"].get("display") or {}).get("program_name"),
            "collection_closed_at": row.get("collection_closed_at"),
            "participant_name": row.get("participant_name"),
            "c67": presented}


def _present_report(saved: dict) -> dict:
    """Pure projection: immutable historical C-67 remains untouched; no generation on GET."""
    from copy import deepcopy
    from Api.m8_report_access import present_public_copy
    c67 = deepcopy(saved)
    partial = c67.get("partial_result")
    if isinstance(partial, dict) and "plan_completed" not in partial:
        progress = partial.get("progress") or {}
        completed, planned = progress.get("completed"), progress.get("planned")
        if isinstance(completed, int) and isinstance(planned, int) and planned > 0:
            partial["plan_completed"] = completed >= planned and not progress.get("interrupted")
            partial["is_incomplete"] = not partial["plan_completed"]
            partial.setdefault("messages", {})["title"] = (
                "Оценка завершена" if partial["plan_completed"] else "Оценка завершена не полностью")
        partial["plan_scope_limited"] = any(x.get("code") == "plan_scope" for x in partial.get("limitation_reasons") or [])
        partial["observation_limited"] = any(x.get("code") == "observation_missing" for x in partial.get("limitation_reasons") or [])
        partial["context_limited"] = any(x.get("code") == "context_limited" for x in partial.get("limitation_reasons") or [])
        partial["technical_failure"] = any(x.get("code") == "technical_failure" for x in partial.get("limitation_reasons") or [])
    if c67.get("recommendations") or c67.get("recommendation_generation"):
        c67["recommendations"] = []
        c67["recommendation_notices"] = []
        c67.pop("recommendation_generation", None)
        c67["recommendation_presentation"] = {
            "policy_version":"m8-descriptive-report/1.1.0", "status":"historical_hidden",
            "message":load_report_package()["template"]["states"]["historical"]}
    if "descriptive" not in c67:
        c67["descriptive"] = {"contract_version":"m8-descriptive-report/1.1.0",
            "status":"historical", "failure_reason":None, "summary":[], "claims":[]}
    return present_public_copy(c67)


def read_latest_report(connection, cycle_id: str, audience: str) -> dict:
    cycle = m7_completion._cycle(connection, cycle_id, lock=False)
    if audience == "assessee":
        row = connection.execute("SELECT report_id AS id FROM m8_published_reports WHERE cycle_db_id=%s",
                                 (cycle["id"],)).fetchone()
        if row:
            return read_report(connection, row["id"])
    row = connection.execute("""SELECT p.id FROM m8_reports p JOIN m8_result_revisions rr ON rr.id=p.result_revision_id
        JOIN m8_results r ON r.id=rr.results_id WHERE r.cycle_db_id=%s AND p.audience=%s
        ORDER BY rr.revision_no DESC,p.revision_no DESC LIMIT 1""", (cycle["id"], audience)).fetchone()
    if not row:
        raise ValueError("M8_REPORT_NOT_FOUND")
    return read_report(connection, row["id"])


def render_pdf(report: dict) -> bytes:
    from copy import deepcopy
    from Api.typst_pdf_renderer import TypstRenderError
    c67 = _present_report(report["c67"])
    # Explicitly supported saved C-67 readers. Never select a legacy PDF using the
    # mutable current template constant.
    if c67.get("template_version") not in {"m8-basic-report/1.4.1", "m8-basic-report/1.5.0"}:
        raise TypstRenderError("PDF_REPORT_VERSION_UNSUPPORTED")
    if (not isinstance(c67.get("skills"), list)
            or not isinstance(c67.get("limitations"), list)
            or not isinstance(c67.get("descriptive"), dict)
            or any(not isinstance(skill, dict) or skill.get("outcome") not in {
                "full_score", "partial_score", "result_without_score", "no_result"}
                or (skill.get("score") is not None and (
                    not isinstance(skill.get("score"), dict)
                    or type(skill["score"].get("value")) not in (int, float)))
                or not (skill.get("skill_name") or skill.get("skill_id"))
                for skill in c67["skills"])):
        raise TypstRenderError("PDF_REPORT_MODEL_UNSUPPORTED")
    participant_labels = {
        "full_score": "Результат по полному составу навыка",
        "partial_score": "Результат по части навыка",
        "result_without_score": "Есть наблюдения без общего балла по навыку",
        "no_result": "Недостаточно оснований для результата",
    }
    skills = []
    for skill in c67["skills"]:
        score = skill.get("score")
        skills.append({
            "name": skill.get("skill_name") or skill["skill_id"],
            "description": skill.get("skill_description") or "",
            "outcome": (skill.get("presentation") or {}).get("label") or participant_labels.get(skill["outcome"], "Неизвестный формат результата"),
            "reasons": [item.get("message") or "Причина ограничения требует уточнения."
                        for item in (skill.get("presentation") or {}).get("reasons") or []],
            "score": "—" if score is None else f"{score['value']:g}",
            "partial": skill["outcome"] == "partial_score",
            "value": None if score is None else score["value"],
            "competency_id": skill.get("competency_id") or skill.get("competency_name") or "Группа навыков",
            "competency": skill.get("competency_name") or "Группа навыков",
        })
    radars = []
    for competency_id in dict.fromkeys(skill["competency_id"] for skill in skills):
        group = [skill for skill in skills if skill["competency_id"] == competency_id]
        radars.append({"name": group[0]["competency"], "competency_id": competency_id, "axes": [
            {"name": skill["name"], "current": skill["value"], "partial": skill["partial"]}
            for skill in group]})
    payload = {
        "title": ("ТЕСТОВЫЙ РЕЗУЛЬТАТ — 4K" if c67.get("test_result")
                  else "4K — базовый индивидуальный отчёт"),
        "program_name": report.get("program_name") or (c67.get("display") or {}).get("program_name"),
        "closed_at": report.get("collection_closed_at") or (c67.get("collection") or {}).get("closed_at"),
        "participant_name": report.get("participant_name"),
        "correction": deepcopy(report.get("correction")),
        "skills": skills,
        "radars": radars,
        "limitations": c67["limitations"],
        "partial_result": c67.get("partial_result"),
        "processing": c67.get("processing", {"status":"completed","message":"Обработка завершена."}),
        "descriptive": c67.get("descriptive", {"status":"historical", "summary":[], "claims":[]}),
    }
    return render_typst_report(payload, "m8_participant_report_v3.typ")
