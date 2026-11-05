"""Read-only resolution and freezing of a published program's pilot opt-in."""
from __future__ import annotations

from copy import deepcopy

from Api.assessment_programs import definition_checksum
from Api.m5_case_runtime import checksum
from Api.pilot_plan_admission import _require, validate_program, validate_snapshot


def program_for_profile(connection, profile: dict) -> dict | None:
    available = connection.execute(
        "SELECT to_regclass(current_schema()||'.assessment_program_definitions') AS relation"
    ).fetchone()
    if not available or not available.get("relation"):
        return None
    rows = connection.execute("""SELECT program.*,link.id AS connection_id,link.organization_id
        FROM organization_assessment_program_connections link
        JOIN assessment_program_definitions program ON program.id=link.program_definition_id
        WHERE link.organization_id=%s AND link.is_current=TRUE
          AND program.assessment_configuration_id=%s""",
        (profile["organization_id"], profile["assessment_configuration_id"])).fetchall()
    _require(len(rows) <= 1, "PROGRAM_SCOPE_AMBIGUOUS")
    return dict(rows[0]) if rows else None


def validate_published_program(connection, program: dict) -> dict:
    _require(program.get("status") == "published", "PROGRAM_NOT_PUBLISHED")
    roles = [int(row["role_profile_version_id"]) for row in connection.execute(
        "SELECT role_profile_version_id FROM assessment_program_allowed_roles WHERE program_definition_id=%s",
        (program["id"],)).fetchall()]
    actual = definition_checksum(code=program["code"], version=program["version"], name=program["name"],
        assignment_ref=program["assignment_ref"], mode=program["mode"],
        configuration_id=program["assessment_configuration_id"], role_version_ids=roles,
        catalog_version_id=program["catalog_version_id"], source_refs=program["source_refs_json"])
    _require(actual == program["definition_checksum"], "PROGRAM_CHECKSUM_MISMATCH")
    snapshot = program["source_refs_json"].get("pilot_plan_admission")
    _require(isinstance(snapshot, dict), "APPROVED_BINDING_REQUIRED")
    design = validate_program(program, roles, snapshot)
    configuration = connection.execute("""SELECT id,code,status,catalog_version_id,methodology_version_id,
        scenario_version_id,prompt_bundle_checksum FROM assessment_configurations WHERE id=%s""",
        (program["assessment_configuration_id"],)).fetchone()
    _require(configuration is not None and configuration["status"] == "published"
             and configuration["code"] == design["configuration"]["code"]
             and configuration["catalog_version_id"] == program["catalog_version_id"]
             and all(configuration[name] == design["configuration"][name]
                     for name in ("methodology_version_id", "scenario_version_id", "prompt_bundle_checksum")),
             "CONFIGURATION_SCOPE_MISMATCH")
    return snapshot


def validate_case_sources(connection, snapshot: dict, catalog_db_id: int) -> None:
    design = validate_snapshot(snapshot)
    rows = connection.execute("""SELECT cv.id,cv.case_id,cv.case_version,cv.content_checksum,cv.content_json
        FROM m5_case_versions cv JOIN m5_catalog_case_versions member ON member.case_version_id=cv.id
        WHERE member.catalog_db_id=%s""", (catalog_db_id,)).fetchall()
    by_ref = {(row["case_id"], row["case_version"]): row for row in rows}
    _require(set(by_ref) == {(row["case_id"], row["version"]) for row in design["cases"]},
             "CATALOG_CASE_SET_MISMATCH")
    for expected in design["cases"]:
        row = by_ref[(expected["case_id"], expected["version"])]
        _require(checksum(row["content_json"]) == row["content_checksum"] == expected["admitted_checksum"],
                 "CASE_CHECKSUM_MISMATCH")
        evidence = connection.execute("""SELECT evidence_checksum FROM m5_qa_evidence
            WHERE case_version_id=%s AND assessment_situation_id IS NULL AND result='PASS'""", (row["id"],)).fetchall()
        _require(set(expected["qa_checksums"]) <= {item["evidence_checksum"] for item in evidence},
                 "CASE_QA_SOURCE_MISMATCH")


def assignment_scope(connection, *, profile: dict, assignment_id: int | None,
                     assignment_ref: str) -> dict:
    _require(assignment_id is not None, "ASSIGNMENT_REQUIRED")
    rows = connection.execute("""SELECT binding.id AS binding_id,binding.questionnaire_revision_id,
            assignment.id AS assignment_id,assignment.organization_id,assignment.recipient_user_id,
            assignment.created_by_user_id AS assigning_actor_id,binding.assigned_by_user_id AS source_actor_id
        FROM organization_assessment_assignments assignment
        JOIN LATERAL (SELECT * FROM organization_assessment_source_bindings b
            WHERE b.assignment_id=assignment.id ORDER BY b.id DESC LIMIT 1) binding ON TRUE
        JOIN questionnaire_response_revisions q ON q.id=binding.questionnaire_revision_id
            AND q.organization_id=assignment.organization_id AND q.assignment_ref=assignment.assignment_ref
        JOIN participant_acquaintance_confirmations confirmation
          ON confirmation.personalized_profile_id=%s
         AND confirmation.user_id=assignment.recipient_user_id
         AND confirmation.organization_id=assignment.organization_id
         AND confirmation.assignment_ref=assignment.assignment_ref
         AND confirmation.questionnaire_revision_id=q.id
        WHERE assignment.id=%s AND assignment.organization_id=%s AND assignment.recipient_user_id=%s
          AND assignment.assignment_ref=%s AND assignment.status='active' AND assignment.revoked_at IS NULL
          AND binding.assessment_configuration_id=%s AND binding.role_profile_version_id=%s
          AND q.status='confirmed' AND q.organization_context_version_id=%s""",
        (profile["id"], assignment_id, profile["organization_id"], profile["user_id"], assignment_ref,
         profile["assessment_configuration_id"], profile["role_profile_version_id"],
         profile["organization_context_version_id"])).fetchall()
    _require(len(rows) == 1 and profile.get("frozen_at") is not None, "ASSIGNMENT_SCOPE_MISMATCH")
    return dict(rows[0])


def freeze(connection, *, program: dict, profile: dict, cycle: dict,
           snapshot: dict, resolved: dict) -> dict:
    scope = assignment_scope(connection, profile=profile, assignment_id=cycle.get("assignment_id"),
                             assignment_ref=program["assignment_ref"])
    design = validate_snapshot(snapshot)
    _require(profile["role_profile_version_id"] in {row["id"] for row in design["role_refs"]}, "ROLE_SCOPE_MISMATCH")
    for name in ("time_budget_seconds", "calendar_window_seconds"):
        source = resolved["sources"][name]
        _require(resolved["values"][name] == design["timing_basis"][name]
                 and source.get("kind") == "program" and source.get("revision_id")
                 and source.get("organization_id") == profile["organization_id"]
                 and source.get("assessment_configuration_id") == profile["assessment_configuration_id"],
                 "SCOPED_TIMING_REQUIRED")
    content = {"contract": "m7_pilot_plan_binding/1", "admission_snapshot": deepcopy(snapshot),
               "program_ref": {"id": program["id"], "code": program["code"], "version": program["version"],
                               "checksum": program["definition_checksum"], "connection_id": program["connection_id"]},
               "profile_ref": {"id": profile["id"], "checksum": profile["checksum"]},
               "assignment_scope": scope, "timing_sources": deepcopy(resolved["sources"])}
    return {**content, "binding_checksum": checksum(content)}
