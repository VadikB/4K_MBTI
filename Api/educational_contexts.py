"""Admission adapter for immutable educational assessment contexts."""
from __future__ import annotations

import hashlib
import json

from Api import assessment_programs
from Api import acquaintance
from Api.assessment_role_profiles import load_published_role_profile


FORBIDDEN_IDENTITY_KEYS = frozenset({"email", "telegram_id", "telegram_user_id", "username", "display_name"})


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS external_educational_contexts (
        id BIGSERIAL PRIMARY KEY,
        source_system TEXT NOT NULL,
        assignment_ref TEXT NOT NULL UNIQUE,
        organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
        recipient_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        assessment_assignment_id BIGINT REFERENCES organization_assessment_assignments(id) ON DELETE RESTRICT,
        status TEXT NOT NULL CHECK (status IN ('awaiting_admission','preparing','prepared')),
        snapshot_json JSONB NOT NULL,
        snapshot_checksum TEXT NOT NULL,
        admission_reasons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        external_cycle_id TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(source_system,assignment_ref)
    )""")
    connection.execute("""CREATE OR REPLACE FUNCTION protect_external_educational_snapshot()
        RETURNS trigger AS $$ BEGIN
            IF TG_OP='DELETE' OR NEW.source_system IS DISTINCT FROM OLD.source_system
              OR NEW.assignment_ref IS DISTINCT FROM OLD.assignment_ref
              OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
              OR NEW.recipient_user_id IS DISTINCT FROM OLD.recipient_user_id
              OR NEW.snapshot_json IS DISTINCT FROM OLD.snapshot_json
              OR NEW.snapshot_checksum IS DISTINCT FROM OLD.snapshot_checksum
              OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'External educational context snapshots are immutable';
            END IF;
            RETURN NEW;
        END $$ LANGUAGE plpgsql""")
    connection.execute("DROP TRIGGER IF EXISTS trg_external_educational_snapshot ON external_educational_contexts")
    connection.execute("""CREATE TRIGGER trg_external_educational_snapshot
        BEFORE UPDATE OR DELETE ON external_educational_contexts
        FOR EACH ROW EXECUTE FUNCTION protect_external_educational_snapshot()""")


def _checksum(snapshot: dict) -> str:
    payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _assert_no_contact_identity(value) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in FORBIDDEN_IDENTITY_KEYS:
                raise ValueError("EDUCATIONAL_CONTEXT_CONTACT_IDENTITY_FORBIDDEN")
            _assert_no_contact_identity(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_contact_identity(nested)


def _organization_code(course_external_id: str) -> str:
    digest = hashlib.sha256(course_external_id.encode("utf-8")).hexdigest()[:24]
    return f"edu-{digest}"


def prepare(connection, *, snapshot: dict, snapshot_checksum: str) -> dict:
    ensure_schema(connection)
    if snapshot.get("schema_version") != 1 or snapshot.get("kind") != "educational_project_assessment_context":
        raise ValueError("EDUCATIONAL_CONTEXT_SCHEMA_UNSUPPORTED")
    _assert_no_contact_identity(snapshot)
    checksum = str(snapshot_checksum or "").strip().lower()
    if _checksum(snapshot) != checksum:
        raise ValueError("EDUCATIONAL_CONTEXT_CHECKSUM_MISMATCH")
    assignment_ref = str(snapshot.get("assignment_ref") or "").strip()
    course = snapshot.get("course") or {}
    participant = snapshot.get("participant") or {}
    role = snapshot.get("role") or {}
    course_external_id = str(course.get("external_id") or "").strip()
    user_id = participant.get("agent4k_user_id")
    role_version_id = role.get("agent4k_role_profile_version_id")
    if not assignment_ref or not course_external_id or not user_id or not role_version_id:
        raise ValueError("EDUCATIONAL_CONTEXT_REQUIRED_REFERENCE_MISSING")
    if connection.execute("SELECT id FROM users WHERE id=%s", (int(user_id),)).fetchone() is None:
        raise ValueError("EDUCATIONAL_CONTEXT_USER_NOT_FOUND")
    published_role = load_published_role_profile(connection, int(role_version_id))
    if str(published_role["checksum"]) != str(role.get("agent4k_role_profile_checksum") or ""):
        raise ValueError("EDUCATIONAL_CONTEXT_ROLE_CHECKSUM_MISMATCH")

    existing = connection.execute(
        "SELECT * FROM external_educational_contexts WHERE assignment_ref=%s FOR UPDATE",
        (assignment_ref,),
    ).fetchone()
    if existing and str(existing["snapshot_checksum"]) != checksum:
        raise ValueError("EDUCATIONAL_CONTEXT_ASSIGNMENT_REF_CONFLICT")
    if existing:
        organization_id = int(existing["organization_id"])
    else:
        organization = connection.execute(
            """INSERT INTO organizations(code,name) VALUES(%s,%s)
               ON CONFLICT(code) DO UPDATE SET name=EXCLUDED.name
               RETURNING id""",
            (
                _organization_code(course_external_id),
                " · ".join(str(value).strip() for value in (course.get("name"), course.get("cohort")) if value),
            ),
        ).fetchone()
        organization_id = int(organization["id"])
    connection.execute(
        """INSERT INTO organization_memberships(
             organization_id,user_id,role,admission_source,admitted_at)
           VALUES(%s,%s,'member','integration_api',NOW())
           ON CONFLICT(organization_id,user_id) DO NOTHING""",
        (organization_id, int(user_id)),
    )

    reasons: list[str] = []
    readiness = connection.execute(
        """SELECT id FROM questionnaire_response_revisions
           WHERE organization_id=%s AND assignment_ref=%s AND status='confirmed'
           ORDER BY id DESC LIMIT 1""",
        (organization_id, assignment_ref),
    ).fetchone()
    if readiness is None:
        reasons.append("QUESTIONNAIRE_NOT_CONFIRMED")
    program_binding = None
    try:
        program_binding = assessment_programs.resolve(
            connection,
            organization_id=organization_id,
            assignment_ref=assignment_ref,
            role_profile_version_id=int(role_version_id),
        )
    except ValueError as exc:
        reasons.append(str(exc))
    profile = None
    if program_binding is not None:
        profile = connection.execute(
            """SELECT id FROM assessment_personalized_profiles
               WHERE user_id=%s AND organization_id=%s
                 AND assessment_configuration_id=%s AND role_profile_version_id=%s
                 AND status='ready' ORDER BY id DESC LIMIT 1""",
            (int(user_id), organization_id,
             int(program_binding["assessment_configuration_id"]), int(role_version_id)),
        ).fetchone()
    if profile is None:
        reasons.append("PERSONALIZED_PROFILE_NOT_CONFIRMED")

    assignment = connection.execute(
        """SELECT id,status FROM organization_assessment_assignments
           WHERE organization_id=%s AND recipient_user_id=%s AND assignment_ref=%s
             AND (status='active' AND revoked_at IS NULL OR status='pending_admission')
           ORDER BY (status='active') DESC,id DESC LIMIT 1 FOR UPDATE""",
        (organization_id, int(user_id), assignment_ref),
    ).fetchone()
    if assignment is None:
        assignment = connection.execute(
            """INSERT INTO organization_assessment_assignments(
                 organization_id,recipient_user_id,assignment_ref,status,operation_id,request_fingerprint)
               VALUES(%s,%s,%s,'pending_admission',%s,%s) RETURNING id,status""",
            (organization_id, int(user_id), assignment_ref, f"tg:{checksum}", checksum),
        ).fetchone()
    assignment_id = int(assignment["id"])
    if assignment["status"] != "active":
        reasons.append("ASSIGNMENT_NOT_ACTIVE")

    preparation_scope = None
    if not reasons:
        try:
            preparation_scope = acquaintance.preparation_scope(
                connection, user_id=int(user_id), profile_id=int(profile["id"])
            )
        except ValueError as exc:
            reasons.append(str(exc))
    target_status = "preparing" if preparation_scope is not None else "awaiting_admission"
    if existing is None:
        row = connection.execute(
            """INSERT INTO external_educational_contexts(
                 source_system,assignment_ref,organization_id,recipient_user_id,
                 assessment_assignment_id,status,snapshot_json,snapshot_checksum,admission_reasons_json)
               VALUES('4k_tg_bot',%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb)
               RETURNING id""",
            (assignment_ref, organization_id, int(user_id), assignment_id, target_status,
             json.dumps(snapshot, ensure_ascii=False), checksum, json.dumps(reasons)),
        ).fetchone()
        context_id = int(row["id"])
    else:
        context_id = int(existing["id"])
        connection.execute(
            """UPDATE external_educational_contexts
               SET assessment_assignment_id=%s,status=%s,
                   admission_reasons_json=%s::jsonb,updated_at=NOW() WHERE id=%s""",
            (assignment_id, target_status, json.dumps(reasons), context_id),
        )
    result = {
        "operation_id": f"educational-context:{context_id}",
        "status": target_status,
        "organization_id": organization_id,
        "assignment_id": assignment_id,
        "assignment_ref": assignment_ref,
        "reasons": reasons,
        "cycle_id": None,
    }
    if preparation_scope is not None:
        result["preparation_request"] = {
            "personalized_profile_id": int(profile["id"]),
            "idempotency_key": f"educational-cycle:{context_id}:{checksum[:16]}",
            "selected_skills": ["K1", "K2", "K3", "K4"],
            **preparation_scope,
        }
        result["recipient_user_id"] = int(user_id)
        result["context_id"] = context_id
    return result


def record_preparation(
    connection, *, context_id: int, operation_id: str, status: str, cycle_id: str | None,
    reasons: list[str] | None = None,
) -> None:
    del operation_id
    target = (
        "prepared" if status == "completed" and cycle_id
        else "awaiting_admission" if status == "failed"
        else "preparing"
    )
    connection.execute(
        """UPDATE external_educational_contexts
           SET status=%s,external_cycle_id=%s,admission_reasons_json=%s::jsonb,updated_at=NOW()
           WHERE id=%s""",
        (target, cycle_id, json.dumps(reasons or []), context_id),
    )


def compatible_programs(connection, *, assignment_ref: str) -> list[dict]:
    context = connection.execute(
        "SELECT snapshot_json FROM external_educational_contexts WHERE assignment_ref=%s",
        (assignment_ref,),
    ).fetchone()
    if context is None:
        raise ValueError("EDUCATIONAL_CONTEXT_NOT_FOUND")
    role_version_id = int(context["snapshot_json"]["role"]["agent4k_role_profile_version_id"])
    rows = connection.execute(
        """SELECT p.id,p.code,p.version,p.name,p.assignment_ref,p.definition_checksum
           FROM assessment_program_definitions p
           JOIN assessment_program_allowed_roles role ON role.program_definition_id=p.id
           WHERE p.status='published' AND p.assignment_ref=%s
             AND role.role_profile_version_id=%s
           ORDER BY p.code,p.version,p.id""",
        (assignment_ref, role_version_id),
    ).fetchall()
    return [dict(row) for row in rows]


def connect_program(
    connection, *, assignment_ref: str, program_definition_id: int, operation_id: str
) -> dict:
    context = connection.execute(
        """SELECT id,organization_id,snapshot_json FROM external_educational_contexts
           WHERE assignment_ref=%s FOR UPDATE""",
        (assignment_ref,),
    ).fetchone()
    if context is None:
        raise ValueError("EDUCATIONAL_CONTEXT_NOT_FOUND")
    role_version_id = int(context["snapshot_json"]["role"]["agent4k_role_profile_version_id"])
    compatible = connection.execute(
        """SELECT p.id FROM assessment_program_definitions p
           JOIN assessment_program_allowed_roles role ON role.program_definition_id=p.id
           WHERE p.id=%s AND p.status='published' AND p.assignment_ref=%s
             AND role.role_profile_version_id=%s""",
        (program_definition_id, assignment_ref, role_version_id),
    ).fetchone()
    if compatible is None:
        raise ValueError("EDUCATIONAL_CONTEXT_PROGRAM_NOT_COMPATIBLE")
    connected = assessment_programs.connect(
        connection,
        organization_id=int(context["organization_id"]),
        program_definition_id=program_definition_id,
        actor_user_id=None,
        operation_id=operation_id,
    )
    return {
        "assignment_ref": assignment_ref,
        "organization_id": int(context["organization_id"]),
        "program_definition_id": int(connected["program_definition_id"]),
        "program_code": str(connected["program_code"]),
        "program_version": str(connected["program_version"]),
        "status": "connected",
    }
