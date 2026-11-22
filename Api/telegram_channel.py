"""Telegram transport over current 4K admission, acquaintance and M10 services."""

from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

from fastapi.encoders import jsonable_encoder

from Api import (
    acquaintance,
    assessment_assignment_sources,
    assessment_programs,
    questionnaire_sources,
)
from Api.assessment_role_profiles import load_published_role_profile
from Api.integration_assessment_configurations import list_published_configurations
from Api import telegram_subjects


def checksum(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def ensure_schema(c) -> None:
    telegram_subjects.ensure_schema(c)
    c.execute("""CREATE TABLE IF NOT EXISTS external_educational_contexts (
        id BIGSERIAL PRIMARY KEY, source_system TEXT NOT NULL,
        assignment_ref TEXT NOT NULL UNIQUE, organization_id BIGINT NOT NULL REFERENCES organizations(id),
        recipient_user_id BIGINT NOT NULL REFERENCES users(id),
        external_subject_ref UUID NOT NULL REFERENCES telegram_assessment_subjects(external_subject_ref),
        runtime_assignment_ref TEXT NOT NULL,
        UNIQUE(organization_id,recipient_user_id,runtime_assignment_ref),
        assessment_assignment_id BIGINT REFERENCES organization_assessment_assignments(id),
        status TEXT NOT NULL CHECK(status IN ('awaiting_admission','preparing','prepared')),
        snapshot_json JSONB NOT NULL,snapshot_checksum TEXT NOT NULL,
        admission_reasons_json JSONB NOT NULL DEFAULT '[]'::jsonb,external_cycle_id TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    c.execute("""CREATE OR REPLACE FUNCTION protect_telegram_context() RETURNS trigger AS $$ BEGIN
        IF TG_OP='DELETE' OR NEW.source_system IS DISTINCT FROM OLD.source_system
          OR NEW.assignment_ref IS DISTINCT FROM OLD.assignment_ref
          OR NEW.external_subject_ref IS DISTINCT FROM OLD.external_subject_ref
          OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
          OR NEW.recipient_user_id IS DISTINCT FROM OLD.recipient_user_id
          OR NEW.runtime_assignment_ref IS DISTINCT FROM OLD.runtime_assignment_ref
          OR NEW.snapshot_json IS DISTINCT FROM OLD.snapshot_json
          OR NEW.snapshot_checksum IS DISTINCT FROM OLD.snapshot_checksum THEN
          RAISE EXCEPTION 'External assessment snapshots are immutable'; END IF; RETURN NEW;
        END $$ LANGUAGE plpgsql""")
    c.execute(
        "DROP TRIGGER IF EXISTS telegram_context_immutable ON external_educational_contexts"
    )
    c.execute("""CREATE TRIGGER telegram_context_immutable BEFORE UPDATE OR DELETE
        ON external_educational_contexts FOR EACH ROW EXECUTE FUNCTION protect_telegram_context()""")
    ensure_channel_operation_schema(c)


def ensure_channel_operation_schema(c) -> None:
    c.execute("""CREATE TABLE IF NOT EXISTS educational_channel_operations (
        id BIGSERIAL PRIMARY KEY,assignment_ref TEXT NOT NULL,idempotency_key TEXT NOT NULL,
        request_checksum TEXT NOT NULL,request_json JSONB NOT NULL,execution_json JSONB NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('processing','completed')),result_json JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),completed_at TIMESTAMPTZ,
        UNIQUE(assignment_ref,idempotency_key))""")


def reject_contacts(value) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in {
                "email",
                "full_name",
                "display_name",
                "username",
                "telegram_id",
                "telegram_user_id",
                "agent4k_user_id",
                "phone",
                "phone_number",
                "contacts",
            }:
                raise ValueError("EDUCATIONAL_CONTEXT_CONTACT_IDENTITY_FORBIDDEN")
            reject_contacts(nested)
    elif isinstance(value, list):
        for nested in value:
            reject_contacts(nested)


def service_actor(c, organization_id: int) -> int:
    subject = str(uuid5(NAMESPACE_URL, f"4k:telegram-service:{organization_id}"))
    telegram_subjects.resolve(
        c, external_subject_ref=subject, organization_id=organization_id
    )
    owner = telegram_subjects.load(c, subject, organization_id)["runtime_owner_id"]
    c.execute(
        "UPDATE organization_memberships SET role='admin',is_participant=FALSE WHERE organization_id=%s AND user_id=%s",
        (organization_id, owner),
    )
    return int(owner)


def context(c, assignment_ref: str) -> dict:
    row = c.execute(
        "SELECT * FROM external_educational_contexts WHERE source_system='4k_tg_bot' AND assignment_ref=%s",
        (assignment_ref,),
    ).fetchone()
    if not row:
        raise ValueError("EDUCATIONAL_ASSIGNMENT_NOT_FOUND")
    return dict(row)


def project_role_for_cycle(c, *, assignment_id: int, profile: dict) -> dict | None:
    """Read only the published role from the snapshot of this exact assignment."""
    if not c.execute(
        "SELECT to_regclass(current_schema()||'.external_educational_contexts') AS relation"
    ).fetchone()["relation"]:
        return None
    row = c.execute(
        """SELECT snapshot_json,snapshot_checksum FROM external_educational_contexts
           WHERE assessment_assignment_id=%s AND source_system='4k_tg_bot'
             AND organization_id=%s AND recipient_user_id=%s""",
        (assignment_id, profile["organization_id"], profile["user_id"]),
    ).fetchone()
    if row is None:
        return None
    snapshot = row["snapshot_json"]
    if checksum(snapshot) != row["snapshot_checksum"]:
        raise ValueError("EDUCATIONAL_CONTEXT_CHECKSUM_MISMATCH")
    role = snapshot["role"]
    if str(role["agent4k_role_profile_version_id"]) != str(profile["role_profile_version_id"]):
        raise ValueError("EDUCATIONAL_CONTEXT_ROLE_PROFILE_MISMATCH")
    definition = role.get("definition", {})
    interactions = definition.get("interactions", [])
    if not isinstance(interactions, list) or any(
        not isinstance(item, str) or not item.strip() for item in interactions
    ):
        raise ValueError("EDUCATIONAL_ROLE_INTERACTIONS_INVALID")
    if not interactions:
        return None
    if checksum(definition) != role["project_role_checksum"]:
        raise ValueError("EDUCATIONAL_ROLE_DEFINITION_CHECKSUM_MISMATCH")
    return {
        "code": role["code"],
        "version": role["project_role_version"],
        "checksum": role["project_role_checksum"],
        "snapshot_checksum": row["snapshot_checksum"],
        "interactions": interactions,
    }


def program_options(c, row: dict) -> list[dict]:
    snapshot = row["snapshot_json"]
    configuration_id = int(
        str(snapshot["assessment_spec"]["assessment_configuration_ref"]).split(":")[-1]
    )
    role_id = int(snapshot["role"]["agent4k_role_profile_version_id"])
    return [
        dict(r)
        for r in c.execute(
            """SELECT p.id,p.code,p.version,p.name,p.assignment_ref,p.definition_checksum
        FROM assessment_program_definitions p JOIN assessment_program_allowed_roles r ON r.program_definition_id=p.id
        WHERE p.status='published' AND p.assessment_configuration_id=%s AND r.role_profile_version_id=%s
        AND p.assignment_ref=%s ORDER BY p.id""",
            (configuration_id, role_id, row["runtime_assignment_ref"]),
        ).fetchall()
    ]


def prepare(c, *, snapshot: dict, snapshot_checksum: str, organization_id: int) -> dict:
    reject_contacts(snapshot)
    if (
        snapshot.get("schema_version") != 1
        or snapshot.get("kind") != "educational_project_assessment_context"
    ):
        raise ValueError("EDUCATIONAL_CONTEXT_SCHEMA_UNSUPPORTED")
    if checksum(snapshot) != snapshot_checksum:
        raise ValueError("EDUCATIONAL_CONTEXT_CHECKSUM_MISMATCH")
    if set(snapshot.get("participant") or {}) - {"local_ref", "external_subject_ref"}:
        raise ValueError("EDUCATIONAL_CONTEXT_CONTACT_IDENTITY_FORBIDDEN")
    subject = telegram_subjects.load(
        c, snapshot["participant"]["external_subject_ref"], organization_id
    )
    role = load_published_role_profile(
        c, int(snapshot["role"]["agent4k_role_profile_version_id"])
    )
    if role["checksum"] != snapshot["role"]["agent4k_role_profile_checksum"]:
        raise ValueError("EDUCATIONAL_CONTEXT_ROLE_CHECKSUM_MISMATCH")
    spec = snapshot["assessment_spec"]
    selected = next(
        (
            x
            for x in list_published_configurations(c)
            if x["ref"] == spec["assessment_configuration_ref"]
        ),
        None,
    )
    if (
        not selected
        or selected["reference_checksum"] != spec["assessment_configuration_checksum"]
    ):
        raise ValueError("EDUCATIONAL_CONTEXT_CONFIGURATION_UNAVAILABLE")
    ref = snapshot["assignment_ref"]
    c.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("tg-context:" + ref,)
    )
    previous = c.execute(
        "SELECT * FROM external_educational_contexts WHERE assignment_ref=%s FOR UPDATE",
        (ref,),
    ).fetchone()
    if previous:
        if previous["snapshot_checksum"] != snapshot_checksum:
            raise ValueError("EDUCATIONAL_CONTEXT_ASSIGNMENT_REF_CONFLICT")
    else:
        refs = c.execute(
            """SELECT DISTINCT p.assignment_ref FROM assessment_program_definitions p
            JOIN assessment_program_allowed_roles r ON r.program_definition_id=p.id
            WHERE p.status='published' AND p.assessment_configuration_id=%s AND r.role_profile_version_id=%s""",
            (selected["id"], role["id"]),
        ).fetchall()
        if len(refs) != 1:
            raise ValueError("EDUCATIONAL_PROGRAM_SCOPE_SELECTION_REQUIRED")
        c.execute(
            """INSERT INTO external_educational_contexts(source_system,assignment_ref,organization_id,
            recipient_user_id,external_subject_ref,runtime_assignment_ref,status,snapshot_json,snapshot_checksum)
            VALUES('4k_tg_bot',%s,%s,%s,%s,%s,'awaiting_admission',%s::jsonb,%s)""",
            (
                ref,
                organization_id,
                subject["runtime_owner_id"],
                subject["external_subject_ref"],
                refs[0]["assignment_ref"],
                json.dumps(snapshot, ensure_ascii=False),
                snapshot_checksum,
            ),
        )
    row = context(c, ref)
    reasons = []
    binding = None
    try:
        binding = assessment_programs.resolve(
            c,
            organization_id=organization_id,
            assignment_ref=row["runtime_assignment_ref"],
            role_profile_version_id=role["id"],
        )
        if int(binding["assessment_configuration_id"]) != selected["id"]:
            raise ValueError("PROGRAM_SOURCE_SELECTION_STALE")
    except ValueError as exc:
        reasons.append(str(exc))
    readiness = questionnaire_sources.assignment_readiness(
        c, organization_id=organization_id, assignment_ref=row["runtime_assignment_ref"]
    )
    if readiness["status"] != "ready":
        reasons.append("QUESTIONNAIRE_NOT_CONFIRMED")
    if not reasons:
        actor = service_actor(c, organization_id)
        c.execute(
            """INSERT INTO organization_assessment_assignments(organization_id,recipient_user_id,assignment_ref,
            created_by_user_id,questionnaire_revision_id,status,operation_id,request_fingerprint)
            VALUES(%s,%s,%s,%s,%s,'active',%s,%s)
            ON CONFLICT(organization_id,recipient_user_id,assignment_ref) WHERE status='active' AND revoked_at IS NULL
            DO NOTHING""",
            (
                organization_id,
                row["recipient_user_id"],
                row["runtime_assignment_ref"],
                actor,
                readiness["questionnaire_revision_id"],
                "tg:" + snapshot_checksum,
                snapshot_checksum,
            ),
        )
        assignment = c.execute(
            """SELECT id FROM organization_assessment_assignments WHERE organization_id=%s
            AND recipient_user_id=%s AND assignment_ref=%s AND status='active' AND revoked_at IS NULL""",
            (organization_id, row["recipient_user_id"], row["runtime_assignment_ref"]),
        ).fetchone()
        assessment_assignment_sources.bind(
            c,
            assignment_id=assignment["id"],
            organization_id=organization_id,
            configuration_id=selected["id"],
            role_version_id=role["id"],
            questionnaire_revision_id=readiness["questionnaire_revision_id"],
            actor_user_id=actor,
            operation_id="tg:" + snapshot_checksum,
        )
        c.execute(
            "UPDATE external_educational_contexts SET assessment_assignment_id=%s WHERE id=%s",
            (assignment["id"], row["id"]),
        )
    assignment_id = row.get("assessment_assignment_id")
    if not assignment_id:
        current = context(c, ref)
        assignment_id = current.get("assessment_assignment_id")
    scope = None
    if not reasons:
        try:
            scope = acquaintance.preparation_scope(c, user_id=row["recipient_user_id"])
        except ValueError as exc:
            reasons.append(str(exc))
    return {
        "operation_id": "telegram-context:" + str(row["id"]),
        "context_id": row["id"],
        "status": "preparing" if scope else "awaiting_admission",
        "organization_id": organization_id,
        "assignment_id": assignment_id,
        "assignment_ref": ref,
        "reasons": reasons,
        "cycle_id": row["external_cycle_id"],
        "preparation_request": scope,
        "recipient_user_id": row["recipient_user_id"],
    }


def preview_project_context(c, *, assignment_ref: str, terms: dict) -> dict:
    """Adapt the frozen project to existing Questionnaire, never a company fixture.

    Purpose/usage/case rules are supplied and approved by the project owner;
    there is no embedded substantive default in this adapter.
    """
    row = context(c, assignment_ref)
    snapshot = row["snapshot_json"]
    project, course = snapshot["project"], snapshot["course"]
    activity = {
        key: project[key]
        for key in (
            "code",
            "business_problem",
            "expected_result",
            "description",
            "stages",
        )
    }
    activity["course"] = course
    answers = {
        "C01": {
            "name": project["name"],
            "organization_type": terms["context_type"],
            "industry": course["name"],
            "activity_description": json.dumps(activity, ensure_ascii=False),
        },
        "C02a": {"participant_text": terms["purpose"]},
        "C03": {"participant_text": terms["results_usage"]},
        "C17": {
            "case_reality_level": terms["case_reality_level"],
            "organization_name_usage_rules": terms["name_usage_rules"],
        },
        "C21": {"organizer": project["name"]},
    }
    preview = questionnaire_sources.save_preview(
        c,
        organization_id=row["organization_id"],
        assignment_ref=row["runtime_assignment_ref"],
        channel="external_form",
        template_variant="corporate",
        template_version="0.2",
        answers=answers,
        raw_text=None,
        uploaded_by=service_actor(c, row["organization_id"]),
        source_author="project-snapshot:" + row["snapshot_checksum"],
        idempotency_key="tg-project:"
        + checksum({"snapshot": row["snapshot_checksum"], "terms": terms}),
    )
    return {
        "revision_id": preview["id"],
        "preview_checksum": checksum(dict(preview["answers_json"])),
        "project_snapshot_checksum": row["snapshot_checksum"],
        "preview": questionnaire_sources.public_revision(preview),
    }


def confirm_project_context(
    c, *, assignment_ref: str, revision_id: int, preview_checksum: str
) -> dict:
    row = context(c, assignment_ref)
    preview = c.execute(
        """SELECT * FROM questionnaire_response_revisions
        WHERE id=%s AND organization_id=%s AND assignment_ref=%s
        AND source_author=%s FOR UPDATE""",
        (
            revision_id,
            row["organization_id"],
            row["runtime_assignment_ref"],
            "project-snapshot:" + row["snapshot_checksum"],
        ),
    ).fetchone()
    if not preview or checksum(dict(preview["answers_json"])) != preview_checksum:
        raise ValueError("PROJECT_CONTEXT_PREVIEW_MISMATCH")
    confirmed = questionnaire_sources.confirm(
        c,
        revision_id=revision_id,
        organization_id=row["organization_id"],
        confirmed_by=service_actor(c, row["organization_id"]),
    )
    return {
        "revision_id": confirmed["id"],
        "status": confirmed["status"],
        "project_snapshot_checksum": row["snapshot_checksum"],
    }


def connect_program(
    c, *, assignment_ref: str, program_definition_id: int, operation_id: str
) -> dict:
    row = context(c, assignment_ref)
    if program_definition_id not in {x["id"] for x in program_options(c, row)}:
        raise ValueError("EDUCATIONAL_CONTEXT_PROGRAM_NOT_COMPATIBLE")
    value = assessment_programs.connect(
        c,
        organization_id=row["organization_id"],
        program_definition_id=program_definition_id,
        actor_user_id=service_actor(c, row["organization_id"]),
        operation_id=operation_id,
    )
    return {
        "program_definition_id": program_definition_id,
        "program_code": value["program_code"],
        "program_version": value["program_version"],
        "status": "connected",
    }


def _channel_action_id(*values: object) -> str:
    material = ":".join(str(value or "") for value in values)
    return "channel-action:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _channel_request(
    *, assignment_ref: str, action_id: str, expected_revision: int, action_input: dict
) -> tuple[dict, str]:
    request = {
        "assignment_ref": assignment_ref,
        "action_id": action_id,
        "expected_revision": int(expected_revision),
        "input": action_input,
    }
    return request, checksum(request)


def _reserve_channel_operation(
    connection,
    *,
    assignment_ref: str,
    idempotency_key: str,
    request: dict,
    request_checksum: str,
    execution: dict,
) -> dict:
    inserted = connection.execute(
        """INSERT INTO educational_channel_operations(
             assignment_ref,idempotency_key,request_checksum,request_json,execution_json,status)
           VALUES(%s,%s,%s,%s::jsonb,%s::jsonb,'processing')
           ON CONFLICT(assignment_ref,idempotency_key) DO NOTHING RETURNING *""",
        (
            assignment_ref,
            idempotency_key,
            request_checksum,
            json.dumps(request, ensure_ascii=False),
            json.dumps(execution, ensure_ascii=False),
        ),
    ).fetchone()
    row = (
        inserted
        or connection.execute(
            """SELECT * FROM educational_channel_operations
           WHERE assignment_ref=%s AND idempotency_key=%s FOR UPDATE""",
            (assignment_ref, idempotency_key),
        ).fetchone()
    )
    if row is None or str(row["request_checksum"]) != request_checksum:
        raise ValueError("IDEMPOTENCY_CONFLICT")
    return dict(row)


def _complete_channel_operation(connection, *, operation_id: int, result: dict) -> None:
    connection.execute(
        """UPDATE educational_channel_operations
           SET status='completed',result_json=%s::jsonb,completed_at=COALESCE(completed_at,NOW())
           WHERE id=%s""",
        (json.dumps(result, ensure_ascii=False), operation_id),
    )


def read_channel_state(connection, *, assignment_ref: str) -> dict:
    """Return a participant-safe, read-only projection for the Telegram channel."""
    context = connection.execute(
        """SELECT *
           FROM external_educational_contexts
           WHERE source_system='4k_tg_bot' AND assignment_ref=%s""",
        (assignment_ref,),
    ).fetchone()
    if context is None:
        raise ValueError("EDUCATIONAL_ASSIGNMENT_NOT_FOUND")

    base = {
        "schema_version": 1,
        "assignment_ref": str(context["assignment_ref"]),
        "cycle_id": str(context["external_cycle_id"])
        if context["external_cycle_id"]
        else None,
        "revision": 0,
        "next_action": None,
        "progress": None,
    }
    cycle_id = base["cycle_id"]
    if not cycle_id:
        from Api.product_cycle_preparation_queue import product_cycle_preparation_queue

        operation = product_cycle_preparation_queue.get_owned_status(
            preparation_key(dict(context)), int(context["recipient_user_id"])
        )
        if operation:
            if operation["status"] == "completed":
                cycle_id = (
                    str(
                        ((operation.get("result_json") or {}).get("plan") or {}).get(
                            "cycle_id"
                        )
                        or ""
                    )
                    or None
                )
                base["cycle_id"] = cycle_id
            elif operation["status"] in {"queued", "running"}:
                return {**base, "state": "preparing"}
            elif operation["status"] == "failed":
                return {**base, "state": "technical_failure"}
    if not cycle_id:
        if str(context["status"]) == "awaiting_admission":
            return _read_acquaintance_channel_state(
                connection,
                assignment_ref=assignment_ref,
                runtime_ref=str(context["runtime_assignment_ref"]),
                user_id=int(context["recipient_user_id"]),
                base=base,
            )
        state = str(context["status"])
        if state not in {"awaiting_admission", "preparing"}:
            state = "technical_failure"
        return {**base, "state": state}

    cycle = connection.execute(
        "SELECT owner_user_id,status FROM m5_cycles WHERE cycle_id=%s",
        (cycle_id,),
    ).fetchone()
    if cycle is None or int(cycle["owner_user_id"]) != int(
        context["recipient_user_id"]
    ):
        return {**base, "state": "technical_failure"}

    from Api import m10_product_flow

    runtime = m10_product_flow.read_runtime(connection, cycle_id=cycle_id)
    # Use the same saved-route projection as the participant dashboard.
    canonical = runtime.get("participant_progress") or {}
    total = canonical.get("planned_total")
    completed = canonical.get("last_completed_position_no") or 0
    progress = (
        None
        if total is None
        else {
            "status": str(cycle["status"]),
            "completed": completed,
            "required": total,
            "remaining": max(total - completed, 0),
            "next_available_at": None,
        }
    )
    if str(cycle["status"]) in {
        "collection_closed",
        "calculation_pending",
        "calculated",
    }:
        return {**base, "state": "cycle_completed", "progress": progress}
    if str(cycle["status"]) == "failed":
        return {**base, "state": "technical_failure", "progress": progress}

    current = runtime.get("current_situation")
    if (
        not current
        or runtime.get("blocking_system_wait")
        or str(cycle["status"]) == "paused"
        or current.get("status") not in {"admitted", "active"}
    ):
        return {**base, "state": "waiting", "progress": progress}
    situation_id = str(current["assessment_situation_id"])
    saved = connection.execute(
        """SELECT state.revision FROM m5_scenario_states state
           JOIN m5_assessment_situations situation
             ON situation.id=state.assessment_situation_db_id
           WHERE situation.assessment_situation_id=%s""",
        (situation_id,),
    ).fetchone()
    revision = int(saved["revision"]) if saved else 0
    last_applied_turn = connection.execute(
        """SELECT turn.turn_id FROM m5_dialogue_turns turn
           JOIN m5_assessment_situations situation
             ON situation.id=turn.assessment_situation_db_id
           LEFT JOIN m5_turn_operations operation
             ON operation.assessment_situation_db_id=turn.assessment_situation_db_id
            AND operation.request_id=turn.request_id
           WHERE situation.assessment_situation_id=%s
             AND turn.speaker_type='assessee'
             AND (operation.id IS NULL OR operation.status='applied')
           ORDER BY turn.sequence_no DESC LIMIT 1""",
        (situation_id,),
    ).fetchone()
    turn_marker = str(last_applied_turn["turn_id"]) if last_applied_turn else ""
    presented = bool(current.get("participant_payload"))
    action_type = "case_turn" if presented else "case_continue"
    next_action = {
        "action_id": _channel_action_id(
            assignment_ref, cycle_id, situation_id, revision, turn_marker, action_type
        ),
        "type": action_type,
        "presentation": {
            "participant_payload": current.get("participant_payload"),
            "trace": runtime.get("trace") if presented else None,
            "input": {"kind": "text", "required": True}
            if presented
            else {"kind": "confirm", "required": True},
        },
    }
    return {
        **base,
        "state": "action_required",
        "revision": revision,
        "next_action": next_action,
        "progress": progress,
    }


def _require_current_action(
    connection, *, assignment_ref: str, action_id: str, expected_revision: int
) -> dict:
    state = read_channel_state(connection, assignment_ref=assignment_ref)
    if int(state["revision"]) != int(expected_revision):
        raise ValueError("STALE_CHANNEL_REVISION")
    action = state.get("next_action")
    if not action or str(action["action_id"]) != action_id:
        raise ValueError("ACTION_NOT_CURRENT")
    return state


def _apply_channel_action(
    connection_factory,
    *,
    assignment_ref: str,
    action_id: str,
    expected_revision: int,
    action_input: dict,
    idempotency_key: str,
) -> dict:
    """Apply a channel command with durable replay before checking mutable state."""
    request, request_checksum = _channel_request(
        assignment_ref=assignment_ref,
        action_id=action_id,
        expected_revision=expected_revision,
        action_input=action_input,
    )
    with connection_factory() as connection:
        prior = connection.execute(
            """SELECT * FROM educational_channel_operations
               WHERE assignment_ref=%s AND idempotency_key=%s FOR UPDATE""",
            (assignment_ref, idempotency_key),
        ).fetchone()
        if prior is not None:
            if str(prior["request_checksum"]) != request_checksum:
                raise ValueError("IDEMPOTENCY_CONFLICT")
            if prior["status"] == "completed":
                return dict(prior["result_json"])
            execution = dict(prior["execution_json"])
        else:
            state = _require_current_action(
                connection,
                assignment_ref=assignment_ref,
                action_id=action_id,
                expected_revision=expected_revision,
            )
            action = state["next_action"]
            cycle_id = str(state["cycle_id"]) if state["cycle_id"] else None
            context = connection.execute(
                """SELECT recipient_user_id,runtime_assignment_ref FROM external_educational_contexts
                   WHERE source_system='4k_tg_bot' AND assignment_ref=%s""",
                (assignment_ref,),
            ).fetchone()
            if context is None:
                raise ValueError("EDUCATIONAL_ASSIGNMENT_NOT_FOUND")
            action_type = str(action["type"])
            execution = {
                "action_type": action_type,
                "user_id": int(context["recipient_user_id"]),
                "runtime_assignment_ref": str(context["runtime_assignment_ref"]),
                "cycle_id": cycle_id,
                "input": action_input,
            }
            if not cycle_id:
                payload = action["presentation"]["participant_payload"] or {}
                if action_type == "acquaintance_consent":
                    if action_input.get("kind") != "confirm":
                        raise ValueError("ACTION_INPUT_INVALID")
                    execution["consent_version"] = int(payload["consent_version"])
                elif action_type == "acquaintance_answer":
                    if (
                        action_input.get("kind") != "text"
                        or not str(action_input.get("text") or "").strip()
                    ):
                        raise ValueError("ACTION_INPUT_INVALID")
                    execution["question_index"] = int(payload["question_index"])
                    execution["content"] = str(action_input["text"]).strip()
                elif action_type in {
                    "personalized_profile_resolve",
                    "acquaintance_confirm",
                }:
                    if action_input.get("kind") != "confirm":
                        raise ValueError("ACTION_INPUT_INVALID")
                else:
                    raise ValueError("ACTION_NOT_CURRENT")
            else:
                current = connection.execute(
                    """SELECT situation.assessment_situation_id,cycle.status AS cycle_status
                       FROM m5_cycles cycle
                       LEFT JOIN m7_route_positions position ON position.cycle_db_id=cycle.id
                         AND position.state IN('not_presented','in_progress','awaiting_replacement')
                       LEFT JOIN m5_assessment_situations situation ON situation.id=position.current_as_db_id
                       WHERE cycle.cycle_id=%s AND cycle.owner_user_id=%s
                       ORDER BY position.position_no LIMIT 1""",
                    (cycle_id, execution["user_id"]),
                ).fetchone()
                if current is None or current.get("assessment_situation_id") is None:
                    raise ValueError("ACTION_NOT_CURRENT")
                execution.update(
                    situation_id=str(current["assessment_situation_id"]),
                    cycle_status=str(current["cycle_status"]),
                )
                if (
                    action_type == "case_continue"
                    and action_input.get("kind") != "confirm"
                ):
                    raise ValueError("ACTION_INPUT_INVALID")
                if action_type == "case_turn":
                    if (
                        action_input.get("kind") != "text"
                        or not str(action_input.get("text") or "").strip()
                    ):
                        raise ValueError("ACTION_INPUT_INVALID")
                    execution["content"] = str(action_input["text"]).strip()
                elif action_type != "case_continue":
                    raise ValueError("ACTION_NOT_CURRENT")
            operation = _reserve_channel_operation(
                connection,
                assignment_ref=assignment_ref,
                idempotency_key=idempotency_key,
                request=request,
                request_checksum=request_checksum,
                execution=execution,
            )
            execution = dict(operation["execution_json"])
            connection.commit()

    action_type = str(execution["action_type"])
    user_id = int(execution["user_id"])
    runtime_ref = str(execution["runtime_assignment_ref"])
    cycle_id = execution.get("cycle_id")
    if not cycle_id:
        with connection_factory() as connection:
            readiness = acquaintance.early_readiness(connection, user_id=user_id)
            if readiness.get("assignment_ref") != runtime_ref:
                raise ValueError("ACTION_NOT_CURRENT")
            if action_type == "acquaintance_consent":
                acquaintance.accept_consent(
                    connection,
                    user_id=user_id,
                    version=int(execution["consent_version"]),
                )
            elif action_type == "acquaintance_answer":
                question_index = int(execution["question_index"])
                acquaintance.save_answers(
                    connection,
                    user_id=user_id,
                    answers={f"answer_{question_index}": str(execution["content"])},
                    confirm=False,
                )
            elif action_type == "acquaintance_confirm":
                saved = acquaintance.read_state(connection, user_id=user_id)["state"]
                acquaintance.save_answers(
                    connection,
                    user_id=user_id,
                    answers=dict(saved["answers_json"]),
                    confirm=True,
                )
            elif action_type == "personalized_profile_resolve":
                acquaintance.resolve_confirmed_profile(connection, user_id=user_id)
            connection.commit()
    elif action_type == "case_continue":
        from Api import m10_product_flow, m5_scenario_runtime

        with connection_factory() as connection:
            if str(execution["cycle_status"]) == "prepared":
                m10_product_flow.start_prepared(
                    connection,
                    user_id=user_id,
                    cycle_id=str(cycle_id),
                    key=idempotency_key,
                )
            else:
                m5_scenario_runtime.start(connection, str(execution["situation_id"]))
            connection.commit()

    if action_type == "case_turn":
        from Api import m5_scenario_runtime

        try:
            m5_scenario_runtime.submit_turn_detached(
                assessment_situation_id=str(execution["situation_id"]),
                request_id=idempotency_key,
                turn_id=str(
                    uuid5(NAMESPACE_URL, f"{assignment_ref}:{idempotency_key}")
                ),
                content=str(execution["content"]),
                expected_revision=expected_revision,
                connection_factory=connection_factory,
            )
        except ValueError as exc:
            if str(exc) == "M5_STATE_REVISION_CONFLICT":
                raise ValueError("STALE_CHANNEL_REVISION") from exc
            if "IDEMPOTENCY" in str(exc) or "REQUEST_CONFLICT" in str(exc):
                raise ValueError("IDEMPOTENCY_CONFLICT") from exc
            raise

    if not cycle_id:
        refresh(connection_factory, assignment_ref)
    with connection_factory() as connection:
        result = read_channel_state(connection, assignment_ref=assignment_ref)
        operation = connection.execute(
            """SELECT id,request_checksum,status,result_json FROM educational_channel_operations
               WHERE assignment_ref=%s AND idempotency_key=%s FOR UPDATE""",
            (assignment_ref, idempotency_key),
        ).fetchone()
        if operation is None or str(operation["request_checksum"]) != request_checksum:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        if operation["status"] == "completed":
            return dict(operation["result_json"])
        result = jsonable_encoder(result)
        _complete_channel_operation(
            connection, operation_id=int(operation["id"]), result=result
        )
        connection.commit()
        return result


def preparation_key(row: dict) -> str:
    return (
        "telegram-prepare:" + str(row["id"]) + ":" + str(row["snapshot_checksum"])[:16]
    )


def _read_acquaintance_channel_state(
    connection, *, assignment_ref: str, runtime_ref: str, user_id: int, base: dict
) -> dict:
    value = acquaintance.read_state(connection, user_id=user_id)
    readiness = value["readiness"]
    if readiness["status"] != "ready" or readiness.get("assignment_ref") != runtime_ref:
        return {**base, "state": "awaiting_admission"}
    saved = value["state"]
    briefing = readiness["briefing"]
    answers = dict(saved.get("answers_json") or {})
    revision = int(saved.get("current_step") or 0) + len(answers)
    if not saved.get("consent_accepted_at"):
        kind = "acquaintance_consent"
        payload = {
            key: briefing[key]
            for key in (
                "purpose",
                "organizer",
                "results_usage",
                "consent_text",
                "consent_version",
            )
            if key in briefing
        }
        if "result_recipients" in briefing:
            payload["result_recipients"] = briefing["result_recipients"]
        input_kind = "confirm"
    else:
        missing = next(
            (i for i in (1, 2, 3) if not str(answers.get(f"answer_{i}") or "").strip()),
            None,
        )
        if missing:
            kind = "acquaintance_answer"
            input_kind = "text"
            payload = {
                "question_index": missing,
                "question": briefing["questions"][missing - 1],
            }
        elif not saved.get("answers_confirmed_at"):
            kind = "acquaintance_confirm"
            input_kind = "confirm"
            payload = {"answers": answers}
        elif value["late_readiness"]["status"] != "ready_to_prepare":
            kind = "personalized_profile_resolve"
            input_kind = "confirm"
            payload = {"answers_confirmed": True}
        else:
            # A distinct explicit action requests canonical preparation after the
            # participant has confirmed their profile; it may invoke the provider.
            kind = "personalized_profile_resolve"
            input_kind = "confirm"
            payload = {"profile_confirmed": True}
    return {
        **base,
        "state": "action_required",
        "revision": revision,
        "next_action": {
            "action_id": _channel_action_id(
                assignment_ref, revision, kind, checksum(answers)
            ),
            "type": kind,
            "presentation": {
                "participant_payload": payload,
                "trace": None,
                "input": {"kind": input_kind, "required": True},
            },
        },
    }


def refresh(factory, assignment_ref: str) -> dict:
    from Api.m10_contracts import ProductCycleStartRequest
    from Api.product_cycle_preparation_queue import product_cycle_preparation_queue

    with factory() as c:
        row = context(c, assignment_ref)
        value = prepare(
            c,
            snapshot=dict(row["snapshot_json"]),
            snapshot_checksum=row["snapshot_checksum"],
            organization_id=row["organization_id"],
        )
        c.commit()
    scope = value.pop("preparation_request", None)
    owner = value.pop("recipient_user_id")
    value.pop("context_id")
    if scope:
        request = ProductCycleStartRequest(
            idempotency_key=preparation_key(row)
        ).model_dump(mode="json")
        request.update(scope)
        operation = product_cycle_preparation_queue.enqueue(
            operation_id=request["idempotency_key"], user_id=int(owner), request=request
        )
        cycle_id = (
            str(
                ((operation.get("result_json") or {}).get("plan") or {}).get("cycle_id")
                or ""
            )
            or None
        )
        value.update(
            operation_id=str(operation["operation_id"]),
            cycle_id=cycle_id,
            status="prepared"
            if cycle_id
            else "awaiting_admission"
            if operation["status"] == "failed"
            else "preparing",
            reasons=["CYCLE_PREPARATION_FAILED"]
            if operation["status"] == "failed"
            else [],
        )
        with factory() as c:
            c.execute(
                """UPDATE external_educational_contexts SET external_cycle_id=%s,status=%s,
                admission_reasons_json=%s::jsonb,updated_at=NOW() WHERE id=%s""",
                (cycle_id, value["status"], json.dumps(value["reasons"]), row["id"]),
            )
            c.commit()
    return value


def apply_channel_action(connection_factory, *, assignment_ref: str, **kwargs) -> dict:
    # Serialize different keys for the same assignment too. The durable replay
    # still lives in educational_channel_operations and survives process restart.
    with connection_factory() as lock:
        lock.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("tg-channel-action:" + assignment_ref,),
        )
        return _apply_channel_action(
            connection_factory, assignment_ref=assignment_ref, **kwargs
        )
