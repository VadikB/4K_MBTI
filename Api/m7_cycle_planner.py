from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from Api.m5_case_runtime import checksum
from Api.m5_cycle_runtime import create_cycle, create_session, read_cycle, start_session
from Api.m5_scenario_runtime import start as start_situation
from Api.m5_storage import prepare_assessment_situation
from Api.m7_planning_package import load_rules, methodology_targets
from Api import m7_planning_repository as repo
from Api.m5_catalog_integrity import (
    case_admission,
    resolve_configuration_catalog,
    resolve_profile_base_role,
)


def _profile_role(profile: dict) -> str:
    content=profile.get("content_json") or {}
    role=content.get("role_profile") if isinstance(content.get("role_profile"),dict) else {}
    return str(content.get("base_role") or content.get("base_role_code") or role.get("code") or "")


def _catalog(connection, *, role: str, rules: dict, planned_ids: set[str],
             catalog_db_id: int | None, usage_scope: str) -> list[dict]:
    if catalog_db_id is None:
        rows=connection.execute("""SELECT cv.id,cv.case_id,cv.case_version,cv.status,cv.base_role,cv.content_json,
            array_agg(t.indicator_id ORDER BY t.display_order) AS target_ids
            FROM m5_case_versions cv JOIN m5_case_targets t ON t.case_version_id=cv.id
            GROUP BY cv.id ORDER BY cv.case_id,cv.case_version""").fetchall()
    else:
        rows=connection.execute("""SELECT cv.id,cv.case_id,cv.case_version,cv.status,cv.base_role,cv.content_json,
        array_agg(t.indicator_id ORDER BY t.display_order) AS target_ids
        FROM m5_catalog_case_versions member
        JOIN m5_case_versions cv ON cv.id=member.case_version_id
        JOIN m5_case_targets t ON t.case_version_id=cv.id
        WHERE member.catalog_db_id=%s
        GROUP BY cv.id ORDER BY cv.case_id,cv.case_version""",(catalog_db_id,)).fetchall()
    result=[]
    for row in rows:
        content=row["content_json"];reasons=[]
        if row["base_role"] != role:reasons.append("ROLE_NOT_ALLOWED")
        if catalog_db_id is None:
            evidence={item["scope"]:item["result"] for item in connection.execute(
                "SELECT DISTINCT ON(scope) scope,result FROM m5_qa_evidence "
                "WHERE case_version_id=%s AND assessment_situation_id IS NULL ORDER BY scope,id DESC",
                (row["id"],)).fetchall()}
            if row["status"] != "FROZEN": reasons.append(f"CASE_STATUS_NOT_ADMITTED:{row['status']}")
            for scope in ("case_format","case_dialogue","assessment_situation"):
                if evidence.get(scope) != "PASS": reasons.append(f"QA_EVIDENCE_MISSING_OR_FAIL:{scope}")
        else:
            decision=case_admission(connection,case_version_id=int(row["id"]),usage_scope=usage_scope,
                                    catalog_db_id=catalog_db_id)
            reasons.extend(decision["reasons"])
        targets=sorted(set(row["target_ids"]) & planned_ids)
        if not targets:reasons.append("NO_PLAN_CONTRIBUTION")
        result.append({"case_id":row["case_id"],"case_version":row["case_version"],"base_role":row["base_role"],
            "planned_min_minutes":content["planned_min_minutes"],"planned_max_minutes":content["planned_max_minutes"],
            "target_ids":list(row["target_ids"]),"contribution_target_ids":targets,
            "eligible":not reasons,"reasons":reasons})
    return result


def _rank(candidates: list[dict], uncovered: set[str], target_meta: dict[str,dict]) -> list[dict]:
    def key(item):
        contribution=set(item["contribution_target_ids"]) & uncovered
        skills={target_meta[x]["skill_id"].split('.')[0] for x in contribution}
        return (-len(contribution),-len(skills),item["planned_max_minutes"],item["case_id"],item["case_version"])
    return sorted((x for x in candidates if x["eligible"] and set(x["contribution_target_ids"]) & uncovered),key=key)


def create_plan(connection, *, personalized_profile_id: int, selected_skills: list[str], created_by: int,
                key: str, time_budget_seconds: int|None=None, calendar_window_seconds: int|None=None,
                usage_scope: str = "qa") -> dict:
    if usage_scope not in {"qa", "assessment"}:
        raise ValueError("M7_USAGE_SCOPE_INVALID")
    request={"personalized_profile_id":personalized_profile_id,"selected_skills":sorted(set(selected_skills)),
             "time_budget_seconds":time_budget_seconds,"calendar_window_seconds":calendar_window_seconds,
             "usage_scope":usage_scope}
    request_hash=checksum(request)
    existing=connection.execute("SELECT plan_id,request_hash FROM m7_plan_request_keys WHERE created_by=%s AND key=%s",(created_by,key)).fetchone()
    if existing:
        if existing["request_hash"]!=request_hash:raise ValueError("IDEMPOTENCY_CONFLICT")
        cycle_id=connection.execute("SELECT c.cycle_id FROM m7_cycle_plans p JOIN m5_cycles c ON c.id=p.cycle_db_id WHERE p.id=%s",(existing["plan_id"],)).fetchone()["cycle_id"]
        return read_plan(connection,str(cycle_id))
    rules=load_rules();targets=methodology_targets(request["selected_skills"]);target_ids={x["indicator_id"] for x in targets}
    profile=connection.execute("SELECT to_jsonb(p) AS value FROM assessment_personalized_profiles p WHERE id=%s",(personalized_profile_id,)).fetchone()
    if not profile or profile["value"].get("status")!="ready":raise ValueError("M4_PROFILE_NOT_READY")
    profile=dict(profile["value"])
    if profile.get("role_profile_version_id") is None:
        role=_profile_role(profile)
        role_ref={"id":role,"version":"0","checksum":"legacy","code":role}
    else:
        role_ref=resolve_profile_base_role(connection,role_profile_version_id=int(profile["role_profile_version_id"]))
        role=role_ref["code"]
    catalog_ref=resolve_configuration_catalog(connection,
        configuration_id=int(profile.get("assessment_configuration_id") or 0),usage_scope=usage_scope)
    if catalog_ref["organization_id"] is not None and int(catalog_ref["organization_id"]) != int(profile["organization_id"]):
        raise ValueError("M5_CATALOG_ORGANIZATION_MISMATCH")
    if catalog_ref["m2_checksum"] != "legacy" and catalog_ref["m2_checksum"] != profile.get("provenance_json",{}).get("m2_checksum",catalog_ref["m2_checksum"]):
        raise ValueError("M5_CATALOG_M2_DEPENDENCY_MISMATCH")
    catalog=_catalog(connection,role=role,rules=rules,planned_ids=target_ids,
                     catalog_db_id=catalog_ref["db_id"],usage_scope=usage_scope)
    uncovered=set(target_ids);route=[]
    while True:
        ranked=_rank(catalog,uncovered,{x["indicator_id"]:x for x in targets})
        if not ranked:break
        chosen=ranked[0];contribution=sorted(set(chosen["contribution_target_ids"])&uncovered)
        route.append({**chosen,"purpose_target_ids":contribution,"duration_source":"M5 CaseVersion planned range",
                      "conditional":True,"reserve_for":[]})
        uncovered-=set(contribution)
    budget=time_budget_seconds or rules["default_time_budget_seconds"]
    calendar=calendar_window_seconds or rules["default_calendar_window_seconds"]
    profile_ref={"id":f"assessment_personalized_profiles:{personalized_profile_id}","version":"1","checksum":profile["checksum"]}
    cycle=create_cycle(connection,personalized_profile_id=personalized_profile_id,selected_role_ref=role_ref,
        target_set=[{"indicator_id":x["indicator_id"],"m2_version":x["m2_version"]} for x in targets],created_by=created_by,
        time_budget_seconds=budget,calendar_window_seconds=calendar,
        parameter_sources={"time_budget":"m7_cycle_plan/1.0.0:"+("request" if time_budget_seconds else "method_default"),
                           "calendar_window":"m7_cycle_plan/1.0.0:"+("request" if calendar_window_seconds else "method_default")},usage_scope=usage_scope,
        catalog_ref={key:catalog_ref[key] for key in ("id","version","checksum","package_checksum","m2_checksum","db_id")})
    session=create_session(connection,cycle_id=str(cycle["cycle_id"]),created_by=created_by)
    total=sum(x["planned_max_minutes"]*60 for x in route)
    status="READY" if not uncovered and total<=budget else ("LIMITED" if route else "NO_ROUTE")
    requirements=[{"indicator_id":x["indicator_id"],"m2_version":x["m2_version"],"required_final_ia_count":1,
                   "distinct_as_required":1} for x in targets]
    content={"schema_version":1,"status":status,"goal":{"kind":"skills","selected_skills":request["selected_skills"]},
        "full_target_set":targets,"planned_target_set":targets,"route":route,"reserves":[],
        "uncovered_target_ids":sorted(uncovered),"planned_max_seconds":total,"time_budget_seconds":budget,
        "calendar_window_seconds":calendar,"catalog_ref":{key:catalog_ref[key] for key in ("id","version","checksum","package_checksum","m2_checksum")},
        "known_limitations":["Cases are conditional opportunities; not guaranteed Evidence"]+
            (["Route exceeds time budget"] if total>budget else []),"catalog":catalog,"algorithm_version":rules["algorithm_version"]}
    repo.save_plan(connection,cycle=cycle,profile_ref=profile_ref,full_targets=targets,planned_targets=targets,
                   requirements=requirements,rules=rules,content=content,created_by=created_by,key=key,request_hash=request_hash)
    return read_plan(connection,str(cycle["cycle_id"]))


def _facts(connection, cycle_db_id:int, target_ids:set[str]) -> dict:
    rows=connection.execute("""SELECT DISTINCT ON(r.indicator_id) r.indicator_id,r.status,r.payload_json,r.created_at
        FROM m5_c54_receipts r JOIN m5_assessment_situations s ON s.id=r.assessment_situation_db_id
        WHERE s.cycle_db_id=%s ORDER BY r.indicator_id,r.created_at DESC""",(cycle_db_id,)).fetchall()
    final_ia=set();opportunity=set();pending=[];failures=[]
    for row in rows:
        target=(row["payload_json"] or {}).get("target") or {}
        if row["status"]=="technical_failure":failures.append(row["indicator_id"]);continue
        if target.get("opportunity")=="PRESENT":opportunity.add(row["indicator_id"])
        if target.get("status")=="ASSESSED" and target.get("outcome") in {"L0","L1","L2","L3"}:final_ia.add(row["indicator_id"])
    return {"opportunity_target_ids":sorted(opportunity&target_ids),"final_ia_target_ids":sorted(final_ia&target_ids),
            "pending_target_ids":pending,"technical_failure_target_ids":sorted(set(failures)&target_ids),
            "aggregate_contribution_coverage":"NOT_CALCULATED","component_score_coverage":"NOT_CALCULATED"}


def choose_next(connection, *, cycle_id:str, expected_plan_revision_id:str, key:str, created_by:int, policy:dict) -> dict:
    plan=repo.read_plan(connection,cycle_id)
    connection.execute("SELECT id FROM m5_cycles WHERE id=%s FOR UPDATE",(plan["cycle_db_id"],)).fetchone()
    request_hash=checksum({"cycle_id":cycle_id,"revision":expected_plan_revision_id})
    existing=repo.existing_next(connection,plan["cycle_db_id"],key,request_hash)
    if existing:return existing
    if str(plan["revision_id"])!=expected_plan_revision_id:raise ValueError("M7_STALE_PLAN_REVISION")
    cycle=read_cycle(connection,cycle_id);session=cycle["sessions"][-1]
    facts=_facts(connection,plan["cycle_db_id"],{x["indicator_id"] for x in plan["planned_target_set_json"]})
    open_as=connection.execute("SELECT assessment_situation_id,status FROM m5_assessment_situations WHERE cycle_db_id=%s AND status NOT IN ('closed','terminated','rejected') ORDER BY id DESC LIMIT 1",(plan["cycle_db_id"],)).fetchone()
    decision={"trigger":{"kind":"next_as_request","created_by":created_by},"facts":facts,"considered":[],"expected_targets":[],"explanation":{}}
    if cycle["status"] in {"collection_closed","calculation_pending","calculated","failed"}:
        decision.update(status="COLLECTION_CLOSED",explanation={"code":"M7_COLLECTION_CLOSED"})
    elif open_as:
        decision.update(status="WAITING_CURRENT_AS",explanation={"code":"M7_CURRENT_AS_UNFINISHED","assessment_situation_id":str(open_as["assessment_situation_id"]),"status":open_as["status"]})
    elif cycle["started_at"] and (cycle["remaining_seconds"]<=0 or datetime.now(timezone.utc)>=cycle["calendar_deadline"]):
        decision.update(status="OUT_OF_TIME",explanation={"code":"M7_TIME_LIMIT_REACHED"})
    else:
        completed=set(facts["final_ia_target_ids"]);needed={x["indicator_id"] for x in plan["planned_target_set_json"]}-completed
        used={x["case_id"] for x in connection.execute("SELECT snapshot_json->'case_ref'->>'id' AS case_id FROM m5_assessment_situations WHERE cycle_db_id=%s",(plan["cycle_db_id"],)).fetchall()}
        candidates=[]
        for item in plan["content_json"]["route"]:
            reasons=[]
            contribution=sorted(set(item["purpose_target_ids"])&needed)
            if item["case_id"] in used:reasons.append("CASE_ALREADY_USED_IN_CYCLE")
            if not contribution:reasons.append("REQUIREMENT_ALREADY_MET")
            required=item["planned_max_minutes"]*60
            if cycle["started_at"] and required>cycle["remaining_seconds"]:reasons.append("DOES_NOT_FIT_REMAINING_TIME")
            candidates.append({"case_id":item["case_id"],"case_version":item["case_version"],"contribution":contribution,"reasons":reasons})
        decision["considered"]=candidates
        selected=next((x for x in candidates if not x["reasons"]),None)
        if not selected:
            decision.update(status="NO_ADMISSIBLE_CASE",explanation={"code":"M7_NO_ADMISSIBLE_CASE","needed_target_ids":sorted(needed)})
        else:
            decision.update(status="SELECTED",selected_case_id=selected["case_id"],selected_case_version=selected["case_version"],
                            expected_targets=selected["contribution"],explanation={"code":"M7_NEXT_AS_SELECTED","algorithm":plan["rules_json"]["algorithm_version"]})
    saved=repo.save_decision(connection,plan=plan,session_db_id=session["id"],key=key,request_hash=request_hash,decision=decision)
    if decision["status"]=="SELECTED":
        profile_id=connection.execute("SELECT personalized_profile_id FROM m5_cycles WHERE id=%s",(plan["cycle_db_id"],)).fetchone()["personalized_profile_id"]
        usage_scope=connection.execute("SELECT usage_scope FROM m5_cycles WHERE id=%s",(plan["cycle_db_id"],)).fetchone()["usage_scope"]
        prepared=prepare_assessment_situation(connection,assessment_situation_id=str(uuid4()),case_id=decision["selected_case_id"],
            case_version=decision["selected_case_version"],personalized_profile_id=profile_id,
            cycle_db_id=plan["cycle_db_id"],session_db_id=session["id"],substitutions=[],policy=policy,
            usage_scope=usage_scope,qa_authorized_by=created_by if usage_scope=="qa" else None)
        if prepared["snapshot"]["admission"]["admitted"] is not True:raise ValueError("AS_NOT_ADMITTED")
        repo.attach_prepared_as(connection,saved["id"],prepared["id"])
    return repo.read_decision(connection,saved["id"])


def present(connection, *, decision_id:str, expected_revision:int) -> dict:
    decision=repo.read_decision(connection,decision_id)
    if decision["revision_no"]!=expected_revision:raise ValueError("M7_STALE_DECISION")
    if decision["status"]!="SELECTED" or not decision["assigned_as_db_id"]:raise ValueError("M7_DECISION_NOT_PRESENTABLE")
    cycle=read_cycle(connection,str(connection.execute("SELECT cycle_id FROM m5_cycles WHERE id=%s",(decision["cycle_db_id"],)).fetchone()["cycle_id"]))
    if cycle["started_at"] and (cycle["remaining_seconds"]<=0 or datetime.now(timezone.utc)>=cycle["calendar_deadline"]):
        raise ValueError("M7_TIME_LIMIT_REACHED")
    if cycle["status"] in {"prepared","interrupted"}:
        start_session(connection,session_id=str(cycle["sessions"][-1]["session_id"]))
    elif cycle["status"]!="active":raise ValueError("M7_COLLECTION_CLOSED")
    current=connection.execute("SELECT status,assessment_situation_id FROM m5_assessment_situations WHERE id=%s FOR UPDATE",(decision["assigned_as_db_id"],)).fetchone()
    if current["status"]=="active":return {"decision":decision,"presentation":{"assessment_situation_id":current["assessment_situation_id"],"status":"active","idempotent":True}}
    if current["status"]!="admitted":raise ValueError("AS_NOT_ADMITTED")
    presentation=start_situation(connection,str(current["assessment_situation_id"]))
    connection.execute("UPDATE m7_route_assignments SET presented_at=NOW() WHERE decision_id=%s AND presented_at IS NULL",(decision["id"],))
    return {"decision":repo.read_decision(connection,decision_id),"presentation":presentation}


def read_plan(connection, cycle_id:str) -> dict:
    row=repo.read_plan(connection,cycle_id)
    decisions=connection.execute("SELECT id FROM m7_route_decisions WHERE cycle_db_id=%s ORDER BY created_at",(row["cycle_db_id"],)).fetchall()
    return {"cycle_id":row["cycle_id"],"cycle_status":row["cycle_status"],"plan_id":row["id"],"revision_id":row["revision_id"],
            "revision_no":row["revision_no"],"plan":row["content_json"],"profile_ref":row["profile_ref_json"],
            "rules_ref":{"checksum":row["rules_checksum"],"algorithm_version":row["rules_json"]["algorithm_version"]},
            "decisions":[repo.read_decision(connection,x["id"]) for x in decisions]}
