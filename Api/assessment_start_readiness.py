"""One participant-safe start decision; read-only and repeated by start POST.

Coverage status is not admission. PM-03 remains the AS admission authority.
"""
from __future__ import annotations

from Api.m5_case_runtime import checksum
from Api.pilot_plan_admission import _require, pairs, project_plan, validate_snapshot

CONTRACT = "m7_start_readiness/1"


def plan_gate(content: dict, cycle: dict) -> dict | None:
    """Validate frozen design and timing; return its opt-in binding, if any."""
    _require(bool(content.get("route")) and content.get("status") in {"READY", "LIMITED"}, "NO_ROUTE")
    full = pairs(content["full_target_set"])
    planned = pairs(content["planned_target_set"])
    _require(pairs(cycle["target_set_json"]) == full and planned <= full, "TARGET_SET_MISMATCH")
    covered = set().union(*(set(row["target_ids"]) for row in content["route"]))
    missing = {indicator for indicator, _ in full} - covered
    _require(set(content["uncovered_target_ids"]) == missing
             and content["status"] == ("LIMITED" if missing else "READY"), "COVERAGE_STATUS_MISMATCH")
    _require(not ({indicator for indicator, _ in planned} - covered), "PLANNED_TARGET_GAP")
    for name in ("time_budget_seconds", "calendar_window_seconds"):
        _require(type(cycle.get(name)) is int and cycle[name] > 0 and content.get(name) == cycle[name],
                 "TIMING_MISMATCH")
    binding = content.get("pilot_plan_binding")
    if binding is None:
        _require(content["status"] == "READY" and planned == full, "APPROVED_BINDING_REQUIRED")
        return None
    _require(binding.get("contract") == "m7_pilot_plan_binding/1"
             and checksum({key: value for key, value in binding.items() if key != "binding_checksum"})
             == binding.get("binding_checksum"), "BINDING_CHECKSUM_MISMATCH")
    snapshot = binding["admission_snapshot"]
    design = validate_snapshot(snapshot)
    _require(full == pairs(design["full_m2_matrix"]), "FULL_M2_MISMATCH")
    _require({indicator for indicator, _ in planned} == set(design["proposed_target_ids"])
             and set(content.get("outside_plan_target_ids", [])) == set(design["absent_target_ids"])
             and content.get("uncovered_planned_target_ids") == [], "TARGET_SET_MISMATCH")
    projected = project_plan(snapshot, targets=content["full_target_set"], catalog=content["catalog"],
                             catalog_ref=content["catalog_ref"], role_ref=cycle["selected_role_ref_json"])
    _require(content["route"] == projected["route"], "ROUTE_MISMATCH")
    for name in ("time_budget_seconds", "calendar_window_seconds"):
        _require(cycle[name] == projected["timing"][name], "TIMING_MISMATCH")
    _require(binding["profile_ref"] == {"id": cycle["personalized_profile_id"],
             "checksum": cycle["profile_ref_json"]["checksum"]}, "PROFILE_SCOPE_MISMATCH")
    _require(binding["assignment_scope"]["assignment_id"] == cycle.get("assignment_id")
             and binding["assignment_scope"]["recipient_user_id"] == cycle["owner_user_id"]
             and binding["assignment_scope"]["organization_id"] == cycle["organization_id"],
             "ASSIGNMENT_SCOPE_MISMATCH")
    sources = cycle["parameter_sources_json"]
    _require(sources.get("resolution_checksum") == content.get("parameter_resolution_checksum"), "TIMING_MISMATCH")
    _require(checksum({"values": {name: cycle[name] for name in ("time_budget_seconds", "calendar_window_seconds")},
                       "sources": content["parameter_sources"]}) == content["parameter_resolution_checksum"],
             "TIMING_MISMATCH")
    for name, short in (("time_budget_seconds", "time_budget"), ("calendar_window_seconds", "calendar_window")):
        source = binding["timing_sources"][name]
        _require(content["parameter_sources"].get(name) == sources.get(short) == source
                 and source.get("kind") == "program" and bool(source.get("revision_id"))
                 and source.get("organization_id") == cycle["organization_id"]
                 and source.get("assessment_configuration_id") == design["configuration"]["id"],
                 "SCOPED_TIMING_REQUIRED")
    return binding


def functional_gate(trace: dict, *, operation_id: str | None = None) -> None:
    """Check mandatory stages and the terminal candidate; never alter admission."""
    from Api.m5_functional_generation_service import checksum as candidate_checksum
    from Api.m5_functional_tester import aggregate
    candidate = trace.get("accepted_as")
    _require(isinstance(candidate, dict) and candidate_checksum(candidate) == trace.get("candidate_checksum"),
             "FINAL_CANDIDATE_MISMATCH")
    tester = trace.get("tester") or {}
    _require(trace.get("tester_input_checksum") == (tester.get("provider_operation") or {}).get("input_checksum")
             and bool(trace.get("tester_input_checksum")), "STAGE_INPUT_MISMATCH")
    aggregation = tester.get("aggregation") or {}
    _require(trace.get("admitted_for_participant") is True
             and aggregation.get("admitted_for_participant") is True
             and aggregation.get("status") in {"PASS", "PASS_WITH_WARNINGS"}, "AS_NOT_ADMITTED")
    recomputed = aggregate(trace.get("deterministic_validation") or {}, tester.get("checks") or [])
    _require(recomputed["admitted_for_participant"] is True and recomputed["status"] == aggregation["status"],
             "AS_NOT_ADMITTED")
    generation = trace.get("generation_operation") or {}
    repair = trace.get("repair")
    _require(bool(generation.get("operation_id")) and bool(generation.get("input_checksum"))
             and generation.get("kind") == ("generation_repair" if repair else "generation"), "GENERATION_STAGE_MISSING")
    if repair:
        _require((repair.get("repair_generation_operation") or {}).get("operation_id") == generation["operation_id"],
                 "FINAL_REPAIR_MISMATCH")
    batch_ids = [generation["operation_id"]]
    for name in ("provider_operation", "challenger_operation"):
        operation = tester.get(name) or {}
        batches = operation.get("batches") or []
        _require(bool(batches) and all(batch.get("operation_id") and batch.get("input_checksum")
                 and batch.get("required_check_ids") for batch in batches), "REQUIRED_STAGE_MISSING")
        _require(candidate_checksum([row["input_checksum"] for row in batches]) == operation.get("input_checksum"),
                 "STAGE_INPUT_MISMATCH")
        required = [check for batch in batches for check in batch["required_check_ids"]]
        expected = [check["check_id"] for check in tester["checks"]
                    if check.get("status") != "NOT_APPLICABLE"
                    and (name == "provider_operation" or check.get("protected"))]
        _require(len(required) == len(set(required)) and set(required) == set(expected), "REQUIRED_CHECKS_MISSING")
        batch_ids.extend(batch["operation_id"] for batch in batches)
    _require(len(batch_ids) == len(set(batch_ids)), "DUPLICATE_STAGE_OPERATION")
    if operation_id is not None:
        _require(all(item.startswith(operation_id + ":") for item in batch_ids), "OPERATION_SCOPE_MISMATCH")


def read(connection, *, cycle_id: str, user_id: int) -> dict:
    """No schema/bootstrap calls and no PII/raw prompts in the public decision."""
    from Api import m7_planning_repository as repo, participant_profile, pilot_plan_binding
    result = {"contract": CONTRACT, "can_start": False, "reasons": [], "cycle_id": str(cycle_id)}
    try:
        cycle = connection.execute("SELECT * FROM m5_cycles WHERE cycle_id=%s", (cycle_id,)).fetchone()
        _require(cycle is not None and cycle["owner_user_id"] == user_id, "CYCLE_NOT_FOUND")
        cycle = dict(cycle)
        _require(cycle["status"] == "prepared" and cycle.get("started_at") is None, "CYCLE_NOT_PREPARED")
        plan = repo.read_plan(connection, cycle_id)
        _require(plan["profile_ref_json"] == cycle["profile_ref_json"], "PROFILE_SCOPE_MISMATCH")
        result.update(plan_revision_id=str(plan["revision_id"]), plan_checksum=plan["content_checksum"],
                      coverage_status=plan["content_json"].get("status"))
        binding = plan_gate(plan["content_json"], cycle)
        profile = participant_profile.profile_for_start(connection, user_id=user_id,
                                                        profile_id=cycle["personalized_profile_id"])
        _require(profile["checksum"] == cycle["profile_ref_json"]["checksum"], "PROFILE_SCOPE_MISMATCH")
        if cycle.get("assignment_id") is not None:
            from Api import acquaintance
            scope = acquaintance.preparation_scope(connection, user_id=user_id, profile_id=profile["id"])
            _require(scope is not None, "ASSIGNMENT_SCOPE_MISMATCH")
            operations = connection.execute("""SELECT operation_id,status,request_json,result_json
                FROM product_cycle_preparation_operations
                WHERE user_id=%s AND request_json->>'personalized_profile_id'=%s
                  AND request_json->>'assignment_ref'=%s
                ORDER BY created_at DESC,id DESC LIMIT 1""",
                (user_id, str(profile["id"]), scope["assignment_ref"])).fetchall()
            _require(len(operations) == 1, "PREPARATION_OPERATION_MISSING")
            op = operations[0]
            _require(op["status"] == "completed"
                     and all(op["request_json"].get(key) == value for key, value in scope.items())
                     and str((op.get("result_json") or {}).get("plan", {}).get("cycle_id")) == str(cycle_id),
                     "PREPARATION_SCOPE_MISMATCH")
            result["preparation_operation_id"] = str(op["operation_id"])
        if binding:
            current = pilot_plan_binding.program_for_profile(connection, profile)
            _require(current is not None and current["id"] == binding["program_ref"]["id"]
                     and current["connection_id"] == binding["program_ref"]["connection_id"]
                     and current["definition_checksum"] == binding["program_ref"]["checksum"], "PROGRAM_SCOPE_MISMATCH")
            snapshot = pilot_plan_binding.validate_published_program(connection, current)
            _require(snapshot == binding["admission_snapshot"], "PROGRAM_SCOPE_MISMATCH")
            actual_scope = pilot_plan_binding.assignment_scope(connection, profile=profile,
                assignment_id=cycle["assignment_id"], assignment_ref=current["assignment_ref"])
            _require(actual_scope == binding["assignment_scope"], "ASSIGNMENT_SCOPE_MISMATCH")
            for source in binding["timing_sources"].values():
                revision = connection.execute("SELECT * FROM m7_parameter_revisions WHERE id=%s", (source["revision_id"],)).fetchone()
                _require(revision is not None and revision["status"] == "published"
                         and revision["organization_id"] == cycle["organization_id"]
                         and revision["assessment_configuration_id"] == profile["assessment_configuration_id"]
                         and revision["source_scope"] == "program"
                         and checksum(revision["values_json"]) == source["checksum"] == revision["values_checksum"],
                         "SCOPED_TIMING_REQUIRED")
            result["pilot_admission"] = {"snapshot_checksum": snapshot["snapshot_checksum"],
                "proposal_checksum": snapshot["review"]["proposal_payload_checksum"],
                "human_decision_id": snapshot["owner_decision"]["decision_id"],
                "binding_checksum": binding["binding_checksum"], "program_ref": binding["program_ref"]}
        selected = connection.execute("""SELECT s.assessment_situation_id,d.plan_revision_id,d.selected_case_id,
                d.selected_case_version,d.session_db_id,s.cycle_db_id,s.session_db_id AS as_session_db_id
            FROM m7_route_decisions d JOIN m7_route_assignments a ON a.decision_id=d.id
            JOIN m5_assessment_situations s ON s.id=a.assessment_situation_db_id
            JOIN m5_cycle_sessions session ON session.id=s.session_db_id
            WHERE d.cycle_db_id=%s AND d.status='SELECTED' AND s.status='admitted'
              AND session.cycle_db_id=d.cycle_db_id AND session.status='prepared'
            ORDER BY d.created_at DESC LIMIT 1""", (cycle["id"],)).fetchone()
        _require(selected is not None and selected["cycle_db_id"] == cycle["id"]
                 and selected["session_db_id"] == selected["as_session_db_id"]
                 and selected["plan_revision_id"] == plan["revision_id"], "AS_PLAN_REVISION_MISMATCH")
        from Api.m5_scenario_runtime import _as_row
        situation = _as_row(connection, str(selected["assessment_situation_id"]), lock=False)
        _require(situation["snapshot_json"]["admission"].get("admitted") is True, "AS_NOT_ADMITTED")
        _require(situation["personalized_profile_id"] == profile["id"]
                 and situation["snapshot_json"]["case_ref"]["id"] == selected["selected_case_id"]
                 and str(situation["snapshot_json"]["case_ref"]["version"]) == str(selected["selected_case_version"]),
                 "AS_SCOPE_MISMATCH")
        if binding:
            _require((selected["selected_case_id"], selected["selected_case_version"]) == (
                plan["content_json"]["route"][0]["case_id"], plan["content_json"]["route"][0]["case_version"]),
                "INITIAL_ROUTE_MISMATCH")
            trace = ((situation["execution_payload_json"].get("ai_operations") or {}).get("functional_personalization") or {})
            functional_gate(trace, operation_id=result.get("preparation_operation_id"))
            _require(trace.get("compiled_case_checksum") == situation["snapshot_json"]["case_ref"]["checksum"]
                     and trace["accepted_as"].get("CaseID") == selected["selected_case_id"]
                     and str(trace["accepted_as"].get("CaseVersion")) == str(selected["selected_case_version"])
                     and (trace.get("source_snapshot") or {}).get("profile_checksum") == profile["checksum"],
                     "FINAL_CANDIDATE_SCOPE_MISMATCH")
            design = validate_snapshot(binding["admission_snapshot"])
            expected_case = next(row for row in design["cases"] if row["case_id"] == selected["selected_case_id"])
            versions = {row["indicator_id"]: row["m2_version"] for row in design["full_m2_matrix"]}
            _require(pairs(situation["snapshot_json"]["indicator_targets"]) == {
                (indicator, versions[indicator]) for indicator in expected_case["target_ids"]}, "AS_TARGET_SET_MISMATCH")
        # Before the first start there must be no running Session/calendar.
        started = connection.execute("SELECT 1 FROM m5_cycle_sessions WHERE cycle_db_id=%s AND started_at IS NOT NULL",
                                     (cycle["id"],)).fetchone()
        _require(started is None and cycle.get("calendar_deadline") is None, "TIME_ALREADY_STARTED")
        answered = connection.execute("""SELECT 1 FROM m5_dialogue_turns turn
            JOIN m5_assessment_situations situation ON situation.id=turn.assessment_situation_db_id
            WHERE situation.cycle_db_id=%s AND turn.speaker_type='assessee' LIMIT 1""", (cycle["id"],)).fetchone()
        _require(answered is None, "ANSWERS_BEFORE_START")
        result.update(can_start=True, assessment_situation_id=str(selected["assessment_situation_id"]),
                      as_snapshot_checksum=situation["snapshot_checksum"],
                      profile_checksum=profile["checksum"])
    except ValueError as exc:
        # Domain codes only; never expose exception text containing profile data.
        code = str(exc).split(":", 1)[0]
        if not code or not all(ch.isupper() or ch.isdigit() or ch == "_" for ch in code):
            code = "START_DEPENDENCY_INVALID"
        result["reasons"] = [code]
    except (KeyError, TypeError, AttributeError):
        result["reasons"] = ["START_SNAPSHOT_INVALID"]
    return result


def require(connection, *, cycle_id: str, user_id: int) -> dict:
    result = read(connection, cycle_id=cycle_id, user_id=user_id)
    if not result["can_start"]:
        raise ValueError("M7_START_NOT_ADMITTED:" + ",".join(result["reasons"]))
    # Callers already hold the Cycle lock. Keep the existing Cycle -> assignment
    # order; no late user/organization advisory locks that could invert it.
    # The UI read remains entirely read-only; only start holds mutable authority
    # rows until commit and repeats the decision after obtaining these locks.
    cycle = connection.execute("SELECT * FROM m5_cycles WHERE cycle_id=%s", (cycle_id,)).fetchone()
    if cycle.get("assignment_id") is not None:
        connection.execute("SELECT id FROM organization_assessment_assignments WHERE id=%s FOR SHARE",
                           (cycle["assignment_id"],)).fetchone()
        connection.execute("""SELECT operation_id FROM product_cycle_preparation_operations
            WHERE operation_id=%s FOR SHARE""", (result["preparation_operation_id"],)).fetchone()
    if result.get("pilot_admission"):
        connection.execute("""SELECT link.id FROM organization_assessment_program_connections link
            JOIN assessment_program_definitions program ON program.id=link.program_definition_id
            WHERE link.organization_id=%s AND link.is_current=TRUE FOR SHARE OF link,program""",
            (cycle["organization_id"],)).fetchall()
        from Api.m7_planning_repository import read_plan
        binding = read_plan(connection, cycle_id)["content_json"]["pilot_plan_binding"]
        for source in binding["timing_sources"].values():
            connection.execute("SELECT id FROM m7_parameter_revisions WHERE id=%s FOR SHARE",
                               (source["revision_id"],)).fetchone()
    result = read(connection, cycle_id=cycle_id, user_id=user_id)
    if not result["can_start"]:
        raise ValueError("M7_START_NOT_ADMITTED:" + ",".join(result["reasons"]))
    return result
