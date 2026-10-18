"""Server-owned W02 acquaintance readiness and participant answer persistence."""

from __future__ import annotations

import hashlib
import json

from Api import participant_profile
from Api.m7_parameter_resolution import resolve as resolve_parameters
from Api.questionnaire_sources import assignment_readiness
from Api.questionnaire_sources import PARTICIPANT_QUESTION_SCHEMA


REQUIRED_BRIEFING_FIELDS = ("purpose", "organizer", "results_usage", "result_recipients")


def _checksum(value: dict) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def early_readiness(connection, *, user_id: int) -> dict:
    memberships = connection.execute(
        """SELECT o.id,o.name FROM organization_memberships m
           JOIN organizations o ON o.id=m.organization_id
           WHERE m.user_id=%s AND o.is_active=TRUE ORDER BY o.id""",
        (user_id,),
    ).fetchall()
    if len(memberships) != 1:
        return _waiting("active_membership", university=False)
    organization = dict(memberships[0])
    assignment_rows = connection.execute(
        """SELECT DISTINCT oi.assignment_ref
           FROM organization_invitations oi
           JOIN users u ON LOWER(u.email)=LOWER(oi.recipient_email)
           WHERE u.id=%s AND oi.organization_id=%s AND oi.purpose='personal_registration'
             AND oi.assignment_ref IS NOT NULL AND oi.revoked_at IS NULL
           ORDER BY oi.assignment_ref""",
        (user_id, organization["id"]),
    ).fetchall()
    if not assignment_rows:
        assignment_rows = connection.execute(
            """SELECT DISTINCT assignment_ref FROM questionnaire_response_revisions
               WHERE organization_id=%s AND status='confirmed' ORDER BY assignment_ref""",
            (organization["id"],),
        ).fetchall()
    if len(assignment_rows) == 1:
        assignment = assignment_readiness(
            connection, organization_id=int(organization["id"]),
            assignment_ref=str(assignment_rows[0]["assignment_ref"]),
        )
        if assignment["status"] == "ready":
            briefing = assignment["briefing"]
            safe_briefing = {key: briefing[key] for key in REQUIRED_BRIEFING_FIELDS}
            safe_briefing.update({
                "provided_participant_fields": briefing["provided_participant_fields"],
                "questions": briefing["participant_questions"],
                "question_schema": briefing.get("participant_question_schema"),
                "consent_version": int(briefing.get("consent_version") or 1),
                "consent_text": str(briefing.get("consent_text") or ""),
            })
            return {
                "status": "ready", "reason": None, "message": "",
                "organization_id": int(organization["id"]),
                "organization_name": str(organization["name"]),
                "organization_context_version_id": assignment["organization_context_version_id"],
                "assignment_ref": assignment["assignment_ref"],
                "questionnaire_revision_id": assignment.get("questionnaire_revision_id"),
                "organization_kind": "organization",
                "responsible_contact": str(briefing.get("responsible_contact") or "").strip() or None,
                "briefing": safe_briefing, "briefing_checksum": _checksum(safe_briefing),
            }
    elif len(assignment_rows) > 1:
        return _waiting("assessment_assignment", university=False, organization=organization)
    row = connection.execute(
        """SELECT v.id,v.definition_json FROM assessment_organization_context_versions v
           JOIN assessment_organization_contexts c ON c.id=v.organization_context_id
           WHERE c.organization_id=%s AND v.status='published'
           ORDER BY v.version DESC,v.id DESC LIMIT 1""",
        (organization["id"],),
    ).fetchone()
    if row is None:
        return _waiting("published_organization_context", university=False, organization=organization)
    definition = dict(row["definition_json"] or {})
    university = str(definition.get("organization_type") or "").strip().lower() in {
        "университет", "вуз", "university",
    }
    briefing = dict(definition.get("participant_briefing") or {})
    missing = [field for field in REQUIRED_BRIEFING_FIELDS if not str(briefing.get(field) or "").strip()]
    questions = briefing.get("student_questions" if university else "participant_questions")
    if not isinstance(questions, list) or len([q for q in questions if str(q).strip()]) != 3:
        missing.append("participant_questions")
    provided = briefing.get("provided_participant_fields")
    if not isinstance(provided, list) or not provided:
        missing.append("provided_participant_fields")
    if missing:
        return _waiting(
            "participant_briefing:" + ",".join(sorted(set(missing))),
            university=university,
            organization=organization,
        )
    contact = str(briefing.get("responsible_contact") or "").strip() or None
    safe_briefing = {
        key: briefing[key]
        for key in REQUIRED_BRIEFING_FIELDS
    }
    safe_briefing.update({
        "provided_participant_fields": provided,
        "questions": [str(q).strip() for q in questions],
        "question_schema": briefing.get("participant_question_schema"),
        "consent_version": int(briefing.get("consent_version") or 1),
        "consent_text": str(briefing.get("consent_text") or "").strip(),
    })
    return {
        "status": "ready",
        "reason": None,
        "message": "",
        "organization_id": int(organization["id"]),
        "organization_name": str(organization["name"]),
        "organization_context_version_id": int(row["id"]),
        "assignment_ref": f"legacy-organization-context:{int(row['id'])}",
        "questionnaire_revision_id": None,
        "organization_kind": "university" if university else "organization",
        "responsible_contact": contact,
        "briefing": safe_briefing,
        "briefing_checksum": _checksum(safe_briefing),
    }


def _waiting(reason: str, *, university: bool, organization: dict | None = None) -> dict:
    subject = "Университет" if university else "Организация"
    return {
        "status": "waiting_for_organization",
        "reason": reason,
        "message": (
            f"{subject} ещё готовит данные для вашей оценки. "
            "Когда подготовка будет завершена, здесь можно будет начать знакомство"
        ),
        "organization_id": int(organization["id"]) if organization else None,
        "organization_name": str(organization["name"]) if organization else None,
        "organization_kind": "university" if university else "organization",
        "responsible_contact": None,
        "briefing": None,
        "briefing_checksum": None,
        "organization_context_version_id": None,
    }


def read_state(connection, *, user_id: int) -> dict:
    readiness = early_readiness(connection, user_id=user_id)
    late = late_readiness(connection, user_id=user_id, readiness=readiness)
    assignment_ref = readiness.get("assignment_ref")
    row = connection.execute(
        "SELECT * FROM participant_acquaintance_states WHERE user_id=%s",
        (user_id,),
    ).fetchone()
    if readiness["status"] != "ready" or (
        row and assignment_ref and str(row.get("assignment_ref") or "") != str(assignment_ref)
    ):
        row = None
    state = dict(row) if row else {
        "status": "not_started", "current_step": 0, "answers_json": {},
        "answers_confirmed_at": None, "consent_accepted_at": None,
    }
    profile_id = late.get("personalized_profile_id")
    return {
        "readiness": readiness,
        "state": state,
        "late_readiness": late,
        "assigned_timing": resolve_display_timing(connection, personalized_profile_id=profile_id),
        "prepared_plan": _prepared_plan_snapshot(connection, personalized_profile_id=profile_id),
    }


def resolve_display_timing(connection, *, personalized_profile_id: int | None) -> dict:
    """Participant-safe projection of the assignment-level resolved timing."""
    if personalized_profile_id is None:
        return {"status": "unavailable"}
    resolved = resolve_parameters(
        connection,
        personalized_profile_id=int(personalized_profile_id),
        usage_scope="assessment",
    )
    return {
        "status": "resolved",
        "time_budget_seconds": resolved["values"]["time_budget_seconds"],
        "calendar_window_seconds": resolved["values"]["calendar_window_seconds"],
        "sources": resolved["sources"],
        "resolved_checksum": resolved["resolved_checksum"],
    }


def _prepared_plan_snapshot(connection, *, personalized_profile_id: int | None) -> dict | None:
    if personalized_profile_id is None:
        return None
    row = connection.execute(
        """SELECT cycle_id FROM m5_cycles
           WHERE personalized_profile_id=%s AND usage_scope='assessment' AND status='prepared'
           ORDER BY created_at DESC,id DESC LIMIT 1""",
        (int(personalized_profile_id),),
    ).fetchone()
    if row is None:
        return None
    from Api.m7_cycle_planner import read_plan
    snapshot = read_plan(connection, str(row["cycle_id"]))
    return {
        "cycle_id": str(snapshot["cycle_id"]),
        "revision_id": str(snapshot["revision_id"]),
        "revision_no": int(snapshot["revision_no"]),
        "plan": snapshot["plan"],
    }


def save_answers(connection, *, user_id: int, answers: dict, confirm: bool = False) -> dict:
    readiness = early_readiness(connection, user_id=user_id)
    if readiness["status"] != "ready":
        raise ValueError("W02_ACQUAINTANCE_NOT_READY")
    allowed = {"answer_1", "answer_2", "answer_3"}
    normalized = {key: str(value).strip() for key, value in answers.items() if key in allowed}
    if not normalized or any(not value for value in normalized.values()):
        raise ValueError("W02_ANSWER_REQUIRED")
    existing = connection.execute(
        "SELECT * FROM participant_acquaintance_states WHERE user_id=%s FOR UPDATE",
        (user_id,),
    ).fetchone()
    if existing and str(existing.get("assignment_ref") or "") not in {"", str(readiness["assignment_ref"])}:
        raise ValueError("W02_ASSIGNMENT_SCOPE_MISMATCH")
    merged = dict(existing["answers_json"] or {}) if existing else {}
    merged.update(normalized)
    if confirm and (set(merged) != allowed or any(not merged[key] for key in allowed)):
        raise ValueError("W02_THREE_ANSWERS_REQUIRED")
    status = "answers_confirmed" if confirm else "in_progress"
    if existing:
        row = connection.execute(
            """UPDATE participant_acquaintance_states SET organization_id=%s,
               organization_context_version_id=%s,assignment_ref=%s,
               questionnaire_revision_id=%s,status=%s,current_step=GREATEST(current_step,4),
               answers_json=%s::jsonb,answers_confirmed_at=CASE WHEN %s THEN NOW() ELSE answers_confirmed_at END,
               briefing_checksum=%s,updated_at=NOW() WHERE user_id=%s RETURNING *""",
            (readiness["organization_id"], readiness["organization_context_version_id"],
             readiness["assignment_ref"], readiness.get("questionnaire_revision_id"), status,
             json.dumps(merged, ensure_ascii=False), confirm, readiness["briefing_checksum"], user_id),
        ).fetchone()
    else:
        row = connection.execute(
            """INSERT INTO participant_acquaintance_states(
               user_id,organization_id,organization_context_version_id,assignment_ref,
               questionnaire_revision_id,status,current_step,answers_json,answers_confirmed_at,briefing_checksum)
               VALUES(%s,%s,%s,%s,%s,%s,4,%s::jsonb,CASE WHEN %s THEN NOW() END,%s) RETURNING *""",
            (user_id, readiness["organization_id"], readiness["organization_context_version_id"],
             readiness["assignment_ref"], readiness.get("questionnaire_revision_id"), status,
             json.dumps(merged, ensure_ascii=False), confirm, readiness["briefing_checksum"]),
        ).fetchone()
    if confirm:
        _bind_confirmed_answers(connection, user_id=user_id, readiness=readiness, answers=merged)
    return dict(row)


def _question_schema(readiness: dict) -> dict | None:
    schema = (readiness.get("briefing") or {}).get("question_schema")
    if schema == PARTICIPANT_QUESTION_SCHEMA:
        return schema
    questions = (readiness.get("briefing") or {}).get("questions")
    if questions == [item["text"] for item in PARTICIPANT_QUESTION_SCHEMA["questions"]]:
        return PARTICIPANT_QUESTION_SCHEMA
    return None


def _bind_confirmed_answers(connection, *, user_id: int, readiness: dict, answers: dict) -> dict:
    """Persist provenance and, when M3/M4 inputs are unambiguous, freeze a profile."""
    schema = _question_schema(readiness)
    if schema is None or readiness.get("organization_kind") != "organization":
        return {"status": "waiting_for_supported_question_schema"}
    items = []
    for index, question in enumerate(schema["questions"], 1):
        raw = str(answers[f"answer_{index}"]).strip()
        items.append({"key": question["key"], "question_version": schema["version"],
                      "question_text": question["text"], "raw_answer": raw,
                      "normalized": raw, "normalization_source": "identity/1.0"})
    answer_set = {"schema_variant": schema["variant"], "schema_version": schema["version"],
                  "assignment_ref": readiness["assignment_ref"], "items": items}
    checksum = _checksum(answer_set)
    prior = connection.execute(
        """SELECT * FROM participant_acquaintance_confirmations
           WHERE user_id=%s AND organization_id=%s AND assignment_ref=%s AND answers_checksum=%s""",
        (user_id, readiness["organization_id"], readiness["assignment_ref"], checksum),
    ).fetchone()
    if prior and prior.get("personalized_profile_id"):
        return dict(prior)
    connection.execute("SELECT id FROM users WHERE id=%s FOR UPDATE", (user_id,))
    user = connection.execute("SELECT full_name FROM users WHERE id=%s", (user_id,)).fetchone()
    from Api.assessment_role_profiles import get_selected_role_profile
    role = get_selected_role_profile(connection, user_id=user_id)
    configs = connection.execute(
        """SELECT c.id FROM assessment_configurations c
           JOIN assessment_methodology_versions m ON m.id=c.methodology_version_id
           WHERE c.status='published' AND m.status='published'
             AND m.definition_json->>'methodology_version'='1.1' ORDER BY c.id"""
    ).fetchall()
    professional = {
        "position_or_status": ((role or {}).get("definition") or {}).get("description", {}).get("name", ""),
        "regular_tasks": items[0]["raw_answer"],
        "decision_situations": items[1]["raw_answer"],
        "constraints_and_interactions": items[2]["raw_answer"],
        "acquaintance_answers": answer_set,
    }
    user_context_version_id = None
    profile_id = None
    if role is not None and len(configs) == 1 and str((user or {}).get("full_name") or "").strip():
        identity = {"full_name": str(user["full_name"]).strip()}
        expected = participant_profile.contexts.context_checksum({"identity": identity, "professional": professional})
        found = connection.execute(
            """SELECT v.id FROM assessment_user_context_versions v
               JOIN assessment_user_contexts u ON u.id=v.user_context_id
               WHERE u.user_id=%s AND u.organization_id=%s AND v.status='confirmed' AND v.checksum=%s
               ORDER BY v.id DESC LIMIT 1""",
            (user_id, readiness["organization_id"], expected),
        ).fetchone()
        user_context_version_id = int(found["id"]) if found else participant_profile.contexts.create_user_context_draft(
            connection, user_id=user_id, identity=identity, professional=professional)
        if not found:
            participant_profile.contexts.confirm_user_context(connection, version_id=user_context_version_id, user_id=user_id)
        profile = participant_profile.contexts.create_personalized_profile(
            connection, user_id=user_id, assessment_configuration_id=int(configs[0]["id"]),
            organization_context_version_id=int(readiness["organization_context_version_id"]),
            role_profile_version_id=int(role["id"]), user_context_version_id=user_context_version_id, conflicts=[])
        profile_id = int(profile["id"])
    row = connection.execute(
        """INSERT INTO participant_acquaintance_confirmations(
           user_id,organization_id,assignment_ref,questionnaire_revision_id,question_schema_json,
           answers_json,answers_checksum,user_context_version_id,personalized_profile_id)
           VALUES(%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
           ON CONFLICT(user_id,organization_id,assignment_ref,answers_checksum) DO UPDATE SET
             user_context_version_id=COALESCE(participant_acquaintance_confirmations.user_context_version_id,EXCLUDED.user_context_version_id),
             personalized_profile_id=COALESCE(participant_acquaintance_confirmations.personalized_profile_id,EXCLUDED.personalized_profile_id)
           RETURNING *""",
        (user_id, readiness["organization_id"], readiness["assignment_ref"],
         readiness.get("questionnaire_revision_id"), json.dumps(schema, ensure_ascii=False),
         json.dumps(answer_set, ensure_ascii=False), checksum, user_context_version_id, profile_id),
    ).fetchone()
    return dict(row)


def accept_consent(connection, *, user_id: int, version: int) -> dict:
    readiness = early_readiness(connection, user_id=user_id)
    expected = int((readiness.get("briefing") or {}).get("consent_version") or 0)
    if readiness["status"] != "ready" or version != expected:
        raise ValueError("W02_CONSENT_VERSION_MISMATCH")
    row = connection.execute(
        """INSERT INTO participant_acquaintance_states(
             user_id,organization_id,organization_context_version_id,assignment_ref,
             questionnaire_revision_id,status,current_step,
             briefing_checksum,consent_version,consent_accepted_at)
           VALUES(%s,%s,%s,%s,%s,'in_progress',1,%s,%s,NOW())
           ON CONFLICT(user_id) DO UPDATE SET
             organization_id=EXCLUDED.organization_id,
             organization_context_version_id=EXCLUDED.organization_context_version_id,
             answers_json=CASE
               WHEN participant_acquaintance_states.assignment_ref IS DISTINCT FROM EXCLUDED.assignment_ref
               THEN '{}'::jsonb ELSE participant_acquaintance_states.answers_json END,
             answers_confirmed_at=CASE
               WHEN participant_acquaintance_states.assignment_ref IS DISTINCT FROM EXCLUDED.assignment_ref
               THEN NULL ELSE participant_acquaintance_states.answers_confirmed_at END,
             status=CASE
               WHEN participant_acquaintance_states.assignment_ref IS DISTINCT FROM EXCLUDED.assignment_ref
               THEN 'in_progress' ELSE participant_acquaintance_states.status END,
             current_step=CASE
               WHEN participant_acquaintance_states.assignment_ref IS DISTINCT FROM EXCLUDED.assignment_ref
               THEN 1 ELSE participant_acquaintance_states.current_step END,
             assignment_ref=EXCLUDED.assignment_ref,
             questionnaire_revision_id=EXCLUDED.questionnaire_revision_id,
             briefing_checksum=EXCLUDED.briefing_checksum,
             consent_version=EXCLUDED.consent_version,
             consent_accepted_at=COALESCE(participant_acquaintance_states.consent_accepted_at,NOW()),
             updated_at=NOW() RETURNING *""",
        (user_id, readiness["organization_id"], readiness["organization_context_version_id"],
         readiness["assignment_ref"], readiness.get("questionnaire_revision_id"),
         readiness["briefing_checksum"], version),
    ).fetchone()
    return dict(row)


def report_issue(connection, *, user_id: int, message: str) -> dict:
    readiness = early_readiness(connection, user_id=user_id)
    if readiness["status"] != "ready":
        raise ValueError("W02_ACQUAINTANCE_NOT_READY")
    normalized = str(message or "").strip()
    if not normalized:
        raise ValueError("W02_ISSUE_MESSAGE_REQUIRED")
    admin = connection.execute(
        "SELECT 1 FROM organization_memberships WHERE organization_id=%s AND role='admin' LIMIT 1",
        (readiness["organization_id"],),
    ).fetchone()
    if admin is None:
        raise ValueError("W02_RESPONSIBLE_NOT_CONFIGURED")
    row = connection.execute(
        """INSERT INTO participant_data_issue_reports(user_id,organization_id,message)
           VALUES(%s,%s,%s) ON CONFLICT(user_id,organization_id,message)
           DO UPDATE SET message=EXCLUDED.message RETURNING id,status,created_at""",
        (user_id, readiness["organization_id"], normalized),
    ).fetchone()
    return dict(row)


def late_readiness(connection, *, user_id: int, readiness: dict | None = None) -> dict:
    readiness = readiness or early_readiness(connection, user_id=user_id)
    if readiness["status"] != "ready":
        return {"status": "waiting_for_assessment_data", "reason": readiness["reason"],
                "personalized_profile_id": None}
    confirmation = connection.execute(
        """SELECT personalized_profile_id FROM participant_acquaintance_confirmations
           WHERE user_id=%s AND organization_id=%s AND assignment_ref=%s
             AND personalized_profile_id IS NOT NULL
           ORDER BY confirmed_at DESC,id DESC LIMIT 1""",
        (user_id, readiness["organization_id"], readiness["assignment_ref"]),
    ).fetchone()
    if confirmation is None:
        return {"status": "waiting_for_assessment_data", "reason": "W02_ANSWERS_NOT_BOUND",
                "personalized_profile_id": None}
    try:
        profile = participant_profile.profile_for_start(
            connection, user_id=user_id, profile_id=int(confirmation["personalized_profile_id"]),
        )
        return {"status": "ready_to_prepare", "reason": None, "personalized_profile_id": int(profile["id"])}
    except ValueError as exc:
        return {"status": "waiting_for_assessment_data", "reason": str(exc), "personalized_profile_id": None}
