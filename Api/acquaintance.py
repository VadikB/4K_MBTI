"""Server-owned W02 acquaintance readiness and participant answer persistence."""

from __future__ import annotations

import hashlib
import json

from Api import participant_profile
from Api.m7_parameter_resolution import resolve as resolve_parameters


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
    late = late_readiness(connection, user_id=user_id)
    row = connection.execute(
        "SELECT * FROM participant_acquaintance_states WHERE user_id=%s",
        (user_id,),
    ).fetchone()
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
        "SELECT answers_json FROM participant_acquaintance_states WHERE user_id=%s",
        (user_id,),
    ).fetchone()
    merged = dict(existing["answers_json"] or {}) if existing else {}
    merged.update(normalized)
    if confirm and (set(merged) != allowed or any(not merged[key] for key in allowed)):
        raise ValueError("W02_THREE_ANSWERS_REQUIRED")
    status = "answers_confirmed" if confirm else "in_progress"
    row = connection.execute(
        """INSERT INTO participant_acquaintance_states(
             user_id,organization_id,organization_context_version_id,status,current_step,
             answers_json,answers_confirmed_at,briefing_checksum,updated_at)
           VALUES(%s,%s,%s,%s,4,%s::jsonb,CASE WHEN %s THEN NOW() END,%s,NOW())
           ON CONFLICT(user_id) DO UPDATE SET
             organization_id=EXCLUDED.organization_id,
             organization_context_version_id=EXCLUDED.organization_context_version_id,
             status=CASE WHEN participant_acquaintance_states.answers_confirmed_at IS NOT NULL
                    THEN participant_acquaintance_states.status ELSE EXCLUDED.status END,
             current_step=GREATEST(participant_acquaintance_states.current_step,EXCLUDED.current_step),
             answers_json=CASE WHEN participant_acquaintance_states.answers_confirmed_at IS NULL
                    THEN participant_acquaintance_states.answers_json || EXCLUDED.answers_json
                    ELSE participant_acquaintance_states.answers_json END,
             answers_confirmed_at=COALESCE(participant_acquaintance_states.answers_confirmed_at,EXCLUDED.answers_confirmed_at),
             briefing_checksum=EXCLUDED.briefing_checksum,updated_at=NOW()
           RETURNING *""",
        (user_id, readiness["organization_id"], readiness["organization_context_version_id"],
         status, json.dumps(normalized, ensure_ascii=False), confirm, readiness["briefing_checksum"]),
    ).fetchone()
    return dict(row)


def accept_consent(connection, *, user_id: int, version: int) -> dict:
    readiness = early_readiness(connection, user_id=user_id)
    expected = int((readiness.get("briefing") or {}).get("consent_version") or 0)
    if readiness["status"] != "ready" or version != expected:
        raise ValueError("W02_CONSENT_VERSION_MISMATCH")
    row = connection.execute(
        """INSERT INTO participant_acquaintance_states(
             user_id,organization_id,organization_context_version_id,status,current_step,
             briefing_checksum,consent_version,consent_accepted_at)
           VALUES(%s,%s,%s,'in_progress',1,%s,%s,NOW())
           ON CONFLICT(user_id) DO UPDATE SET
             consent_version=EXCLUDED.consent_version,
             consent_accepted_at=COALESCE(participant_acquaintance_states.consent_accepted_at,NOW()),
             updated_at=NOW() RETURNING *""",
        (user_id, readiness["organization_id"], readiness["organization_context_version_id"],
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


def late_readiness(connection, *, user_id: int) -> dict:
    try:
        profile = participant_profile.profile_for_start(connection, user_id=user_id)
        return {"status": "ready_to_prepare", "reason": None, "personalized_profile_id": int(profile["id"])}
    except ValueError as exc:
        return {"status": "waiting_for_assessment_data", "reason": str(exc), "personalized_profile_id": None}
