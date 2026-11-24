"""First and Next preparation on a frozen, explicitly selected QA route."""
from __future__ import annotations

from uuid import UUID

from Api import m5_functional_generation_service as preparation
from Api.cycle_execution_manifest import resolve_cycle_dependency
from Api.llm.provider_contract import load_provider_contract
from Api.m5_runtime_rules import resolve_preparation_binding
from Api.m5_storage import prepare_assessment_situation, resolve_cycle_base_role


def _selection(connection, cycle_id: str, actor: int, as_id: str, *, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    cycle = connection.execute("SELECT * FROM m5_cycles WHERE cycle_id=%s" + suffix, (UUID(cycle_id),)).fetchone()
    if not cycle or cycle["usage_scope"] != "qa" or cycle["created_by"] != actor:
        raise ValueError("M5_BATTERY_SCENARIO_REQUIRES_DIAGNOSTIC_CYCLE")
    catalog = cycle["catalog_ref_json"] or {}
    route = catalog.get("scenario_test_route")
    if not catalog.get("diagnostic_only") or not route:
        raise ValueError("M5_BATTERY_PREPARATION_NOT_ENABLED")
    if cycle["status"] not in {"prepared", "active"}:
        raise ValueError("M5_BATTERY_QA_CYCLE_UNAVAILABLE")
    session = connection.execute(
        "SELECT id,status FROM m5_cycle_sessions WHERE cycle_db_id=%s ORDER BY ordinal DESC LIMIT 1", (cycle["id"],),
    ).fetchone()
    if session is None or session["status"] not in {"prepared", "active"}:
        raise ValueError("M5_BATTERY_QA_SESSION_UNAVAILABLE")
    situations = connection.execute(
        """SELECT assessment_situation_id,status,snapshot_json,execution_payload_json FROM m5_assessment_situations
           WHERE cycle_db_id=%s ORDER BY id""", (cycle["id"],),
    ).fetchall()
    for saved in situations:
        if str(saved["assessment_situation_id"]) == as_id:
            return cycle, session, None, saved
    if situations and situations[-1]["status"] != "closed":
        raise ValueError("M5_BATTERY_WAITING_CURRENT_AS")
    ordinal = len(situations)
    if ordinal >= len(route):
        raise ValueError("M5_BATTERY_SCENARIO_ROUTE_EXHAUSTED")
    selected = route[ordinal]
    row = connection.execute(
        """SELECT cv.id,cv.content_json,cv.content_checksum,member.runtime_rule_version_id
           FROM m5_catalog_case_versions member JOIN m5_case_versions cv ON cv.id=member.case_version_id
           WHERE member.catalog_db_id=%s AND cv.case_id=%s AND cv.case_version=%s""",
        (catalog["db_id"], selected["case_id"], selected["case_version"]),
    ).fetchone()
    if not row or row["content_checksum"] != selected["content_checksum"]:
        raise ValueError("M5_BATTERY_SCENARIO_ROUTE_CASE_INVALID")
    return cycle, session, (ordinal, row), None


def prepare_next(connection_factory, *, cycle_id: str, assessment_situation_id: str, actor: int, gateway) -> dict:
    """Prepare the next exact Case via the production PM-03 service and shared C-34 persistence."""
    with connection_factory() as connection:
        cycle, session, selected, saved = _selection(connection, cycle_id, actor, assessment_situation_id)
        if saved:
            return {**saved, "idempotent": True, "technical_ready": True}
        ordinal, case = selected
        profile = connection.execute(
            "SELECT * FROM assessment_personalized_profiles WHERE id=%s", (cycle["personalized_profile_id"],),
        ).fetchone()
        if not profile or profile["status"] != "ready" or profile["checksum"] != cycle["profile_ref_json"]["checksum"]:
            raise ValueError("M4_PROFILE_NOT_READY")
        dependencies = cycle["execution_manifest_json"]["dependencies"]
        project_role = cycle["execution_manifest_json"]["runtime_refs"].get("project_role")
        snapshot = preparation.build_passport_snapshot(
            case_version=case["content_json"], profile=profile["content_json"], operation_id=assessment_situation_id,
            synthetic=True, profile_checksum=profile["checksum"], case_version_checksum=case["content_checksum"],
            selected_base_role=resolve_cycle_base_role(connection, cycle, profile["content_json"]),
            as_package=resolve_cycle_dependency(cycle, "m5_functional_as"),
            m2_path=resolve_cycle_dependency(cycle, "m2_methodology") / "methodology.json",
            m3_path=resolve_cycle_dependency(cycle, "m3_role_profiles") / "base_roles.json",
            runtime_rule_ref=resolve_preparation_binding(connection, case),
            battery_scenario_package=resolve_cycle_dependency(cycle, "m5_battery_scenario"),
            provider_contract=load_provider_contract(resolve_cycle_dependency(cycle, "provider_contract") / "manifest.json"),
            project_role=project_role,
            project_role_prompt=(resolve_cycle_dependency(cycle, "m5_educational_role_interactions")
                                 if "m5_educational_role_interactions" in dependencies else None),
        )
    prepared = preparation.prepare(snapshot, gateway)
    if not prepared["admitted_for_participant"]:
        return {"status": "preparation_rejected", "candidate_checksum": prepared["candidate_checksum"],
                "validation": prepared["deterministic_validation"]}
    generation = preparation.build_persistence_trace(snapshot, prepared)
    with connection_factory() as connection:
        current, current_session, latest, saved = _selection(connection, cycle_id, actor, assessment_situation_id, lock=True)
        if saved:
            return {**saved, "idempotent": True, "technical_ready": True}
        if (latest[0] != ordinal or latest[1]["id"] != case["id"] or current_session["id"] != session["id"]
                or current["execution_manifest_checksum"] != cycle["execution_manifest_checksum"]):
            raise ValueError("M5_BATTERY_PREPARATION_SUPERSEDED")
        result = prepare_assessment_situation(
            connection, assessment_situation_id=assessment_situation_id, cycle_db_id=cycle["id"],
            session_db_id=session["id"], personalized_profile_id=profile["id"],
            case_id=case["content_json"]["case_id"], case_version=case["content_json"]["version"],
            usage_scope="qa", qa_authorized_by=actor, substitutions=[],
            policy={"id": "m5-battery-scenario-qa", "version": "1",
                    "allowed_case_statuses": ["FROZEN"],
                    "required_evidence_scopes": ["case_format", "case_dialogue", "assessment_situation"]},
            case_value_override=prepared["compiled_case"], runtime_rules_override=prepared["execution_rules"],
            generation_trace=generation,
        )
        connection.commit()
        return {**result, "technical_ready": True}
