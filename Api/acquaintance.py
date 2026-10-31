"""Server-owned W02 acquaintance readiness and participant answer persistence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from Api import participant_profile
from Api import assessment_assignment_sources as assignment_sources
from Api import acquaintance_state_store as state_store
from Api.m7_parameter_resolution import resolve as resolve_parameters
from Api.questionnaire_sources import assignment_readiness
from Api.questionnaire_sources import PARTICIPANT_QUESTION_SCHEMA


REQUIRED_BRIEFING_FIELDS = ("purpose", "organizer", "results_usage", "result_recipients")


def _participant_fields(connection, *, user_id: int, organization_id: int,
                        assignment_ref: str, questionnaire_revision_id: int | None) -> list[dict]:
    row = connection.execute("""SELECT to_jsonb(u)->>'full_name' AS full_name,
        to_jsonb(u)->>'email' AS email,to_jsonb(u)->>'job_description' AS position
        FROM users u WHERE u.id=%s""", (user_id,)).fetchone() or {}
    binding = assignment_sources.current_binding(connection, user_id=user_id,
        organization_id=organization_id, assignment_ref=assignment_ref,
        questionnaire_revision_id=questionnaire_revision_id)
    role_name = None
    if binding:
        from Api.assessment_role_profiles import load_published_role_profile
        role = load_published_role_profile(connection, binding['role_profile_version_id'])
        role_name = role['definition']['description']['name']
    elif questionnaire_revision_id is None:
        from Api.assessment_role_profiles import get_selected_role_profile
        role = get_selected_role_profile(connection, user_id=user_id)
        if role:
            role_name = role['definition']['description']['name']
    return [{'key': key, 'label': label, 'value': str(value).strip() if value else None,
             'source': source, 'readonly': True} for key, label, value, source in (
        ('full_name', 'ФИО', row.get('full_name'), 'organization_participant_record'),
        ('email', 'Email', row.get('email'), 'organization_participant_record'),
        ('position', 'Должность', row.get('position'), 'organization_participant_record'),
        ('role', 'Роль в оценке', role_name, 'assessment_assignment'),
    )]


def _checksum(value: dict) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def early_readiness(connection, *, user_id: int) -> dict:
    memberships = connection.execute(
        """SELECT o.id,o.name,m.role FROM organization_memberships m
           JOIN organizations o ON o.id=m.organization_id
           WHERE m.user_id=%s AND o.is_active=TRUE ORDER BY o.id""",
        (user_id,),
    ).fetchall()
    if len(memberships) != 1:
        return _waiting("active_membership", university=False)
    organization = dict(memberships[0])
    assignment_rows = connection.execute(
        """SELECT DISTINCT assignment_ref FROM (
             SELECT oa.assignment_ref
             FROM organization_assessment_assignments oa
             WHERE oa.recipient_user_id=%s AND oa.organization_id=%s
               AND oa.status='active' AND oa.revoked_at IS NULL
             UNION
             SELECT oi.assignment_ref
             FROM organization_invitations oi
             JOIN users u ON LOWER(u.email)=LOWER(oi.recipient_email)
             WHERE u.id=%s AND oi.organization_id=%s AND oi.purpose='personal_registration'
               AND oi.assignment_ref IS NOT NULL AND oi.revoked_at IS NULL
               AND oi.created_by_user_id IS DISTINCT FROM u.id
           ) assignments ORDER BY assignment_ref""",
        (user_id, organization["id"], user_id, organization["id"]),
    ).fetchall()
    if not assignment_rows:
        if str(organization.get("role") or "") == "admin":
            return _waiting_assignment(organization)
        assignment_rows = connection.execute(
            """SELECT DISTINCT assignment_ref FROM questionnaire_response_revisions
               WHERE organization_id=%s AND status='confirmed' ORDER BY assignment_ref""",
            (organization["id"],),
        ).fetchall()
        if assignment_rows and assignment_sources.schema_available(connection):
            return _waiting_assignment(organization)
    if len(assignment_rows) == 1:
        assignment = assignment_readiness(
            connection, organization_id=int(organization["id"]),
            assignment_ref=str(assignment_rows[0]["assignment_ref"]),
        )
        if assignment["status"] == "ready":
            briefing = assignment["briefing"]
            provided = _participant_fields(connection, user_id=user_id,
                organization_id=int(organization['id']), assignment_ref=assignment['assignment_ref'],
                questionnaire_revision_id=assignment.get('questionnaire_revision_id'))
            missing = [item['key'] for item in provided if item['key'] in {'full_name', 'email', 'position'} and not item['value']]
            if briefing.get('participant_question_schema') == PARTICIPANT_QUESTION_SCHEMA and missing:
                waiting = _waiting('participant_fields:' + ','.join(missing), university=False, organization=organization)
                waiting['responsible_contact'] = str(briefing.get('responsible_contact') or '').strip() or None
                return waiting
            safe_briefing = {key: briefing[key] for key in REQUIRED_BRIEFING_FIELDS}
            safe_briefing.update({
                "provided_participant_fields": provided,
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
    if any(not isinstance(item, dict) for item in provided):
        provided = _participant_fields(connection, user_id=user_id, organization_id=organization['id'],
            assignment_ref=f"legacy-organization-context:{int(row['id'])}", questionnaire_revision_id=None)
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


def _waiting_assignment(organization: dict) -> dict:
    return {
        "status": "waiting_for_assignment",
        "reason": "assessment_assignment",
        "message": "Оценка пока не назначена. Обратитесь к уполномоченному назначающему.",
        "organization_id": int(organization["id"]),
        "organization_name": str(organization["name"]),
        "organization_kind": "organization",
        "responsible_contact": None,
        "briefing": None,
        "briefing_checksum": None,
        "organization_context_version_id": None,
    }


def read_state(connection, *, user_id: int) -> dict:
    readiness = early_readiness(connection, user_id=user_id)
    late = late_readiness(connection, user_id=user_id, readiness=readiness)
    row = state_store.read(connection, user_id=user_id, readiness=readiness) if readiness['status'] == 'ready' else None
    state = dict(row) if row else {
        "status": "not_started", "current_step": 0, "answers_json": {},
        "answers_confirmed_at": None, "consent_accepted_at": None,
    }
    if not mandatory_complete(readiness, state):
        late = {'status': 'waiting_for_assessment_data', 'reason': 'W02_MANDATORY_STEPS_REQUIRED',
                'personalized_profile_id': None}
    profile_id = late.get("personalized_profile_id")
    from Api.product_cycle_preparation_queue import latest_scope_operation
    return {
        "readiness": readiness,
        "state": state,
        "mandatory_complete": mandatory_complete(readiness, state),
        "late_readiness": late,
        "assigned_timing": resolve_display_timing(connection, personalized_profile_id=profile_id),
        "prepared_plan": _prepared_plan_snapshot(connection, personalized_profile_id=profile_id),
        "preparation_operation": latest_scope_operation(connection, user_id=user_id, profile_id=profile_id,
            assignment_ref=readiness['assignment_ref'], questionnaire_revision_id=readiness.get('questionnaire_revision_id'))
            if profile_id is not None else None,
        "competency_explanation": _competency_explanation(connection, user_id=user_id, readiness=readiness,
            profile_id=profile_id),
        "onboarding": _onboarding_progress(connection, user_id=user_id),
    }


def _onboarding_progress(connection, *, user_id: int) -> dict:
    available = connection.execute("SELECT to_regclass(current_schema()||'.user_onboarding_state') AS relation").fetchone()
    row = connection.execute('SELECT status,current_step FROM user_onboarding_state WHERE user_id=%s',
        (user_id,)).fetchone() if available and available.get('relation') else None
    return dict(row) if row else {'status': 'not_started', 'current_step': 0}


def _competency_explanation(connection, *, user_id: int, readiness: dict, profile_id: int | None) -> dict:
    binding = assignment_sources.current_binding(connection, user_id=user_id,
        organization_id=readiness.get('organization_id'), assignment_ref=readiness.get('assignment_ref'),
        questionnaire_revision_id=readiness.get('questionnaire_revision_id'))
    if not binding:
        return {'status': 'unavailable', 'items': []}
    row = connection.execute('''SELECT m.id,m.version,m.checksum,m.definition_json
        FROM assessment_configurations c JOIN assessment_methodology_versions m ON m.id=c.methodology_version_id
        WHERE c.id=%s AND c.status='published' AND m.status='published' ''',
        (binding['assessment_configuration_id'],)).fetchone()
    if not row:
        return {'status': 'unavailable', 'items': []}
    from Api.assessment_configuration import definition_checksum
    if definition_checksum(row['definition_json']) != row['checksum']:
        raise ValueError('METHODOLOGY_CHECKSUM_MISMATCH')
    return {'status': 'ready', 'source': {'version_id': row['id'], 'version': row['version'], 'checksum': row['checksum']},
            'items': [{'name': item['name'], 'definition': item['definition']}
                      for item in row['definition_json'].get('competencies', [])]}


def mandatory_complete(readiness: dict, state: dict) -> bool:
    answers = state.get('answers_json') or {}
    return bool(readiness.get('status') == 'ready' and state.get('consent_accepted_at')
        and state.get('consent_version') == (readiness.get('briefing') or {}).get('consent_version')
        and state.get('answers_confirmed_at')
        and all(str(answers.get(f'answer_{index}') or '').strip() for index in (1, 2, 3)))


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
    from Api.qa_orchestration import usage_scope
    row = connection.execute(
        """SELECT cycle_id FROM m5_cycles
           WHERE personalized_profile_id=%s AND usage_scope=%s AND status='prepared'
             AND EXISTS (SELECT 1 FROM m5_assessment_situations s
                         WHERE s.cycle_db_id=m5_cycles.id AND s.status='admitted')
           ORDER BY created_at DESC,id DESC LIMIT 1""",
        (int(personalized_profile_id), usage_scope()),
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
    normalized = {key: str(value) for key, value in answers.items() if key in allowed}
    if not normalized or any(not value.strip() for value in normalized.values()):
        raise ValueError("W02_ANSWER_REQUIRED")
    existing = state_store.activate(connection, user_id=user_id, readiness=readiness)
    if existing and (existing['organization_id'] != readiness['organization_id']
            or str(existing.get("assignment_ref") or "") not in {"", str(readiness["assignment_ref"])}
            or existing.get('questionnaire_revision_id') != readiness.get('questionnaire_revision_id')):
        raise ValueError("W02_ASSIGNMENT_SCOPE_MISMATCH")
    if (not existing or not existing.get('consent_accepted_at')
            or existing.get('consent_version') != readiness['briefing']['consent_version']):
        raise ValueError('W02_CONSENT_REQUIRED')
    merged = dict(existing["answers_json"] or {}) if existing else {}
    merged.update(normalized)
    frozen = connection.execute('''SELECT 1 FROM participant_acquaintance_confirmations
        WHERE user_id=%s AND organization_id=%s AND assignment_ref=%s
          AND questionnaire_revision_id IS NOT DISTINCT FROM %s
          AND personalized_profile_id IS NOT NULL LIMIT 1''',
        (user_id, readiness['organization_id'], readiness['assignment_ref'],
         readiness.get('questionnaire_revision_id'))).fetchone()
    if frozen or existing.get('answers_confirmed_at'):
        if merged != existing['answers_json']:
            raise ValueError('W02_ANSWERS_FROZEN: Ответы уже подтверждены; для изменения нужно новое назначение.')
        return dict(existing)  # Transport replay must not unconfirm an already frozen profile.
    if confirm and (set(merged) != allowed or any(not merged[key] for key in allowed)):
        raise ValueError("W02_THREE_ANSWERS_REQUIRED")
    row = state_store.write(connection, user_id=user_id, readiness=readiness, state={
        **existing, 'status': 'answers_confirmed' if confirm else 'in_progress',
        'current_step': max(int(existing.get('current_step') or 0), 4), 'answers_json': merged,
        'answers_confirmed_at': datetime.now(timezone.utc).replace(tzinfo=None) if confirm else None,
    })
    if confirm:
        _bind_confirmed_answers(connection, user_id=user_id, readiness=readiness, answers=merged, bind_profile=False)
    return dict(row)


def _question_schema(readiness: dict) -> dict | None:
    schema = (readiness.get("briefing") or {}).get("question_schema")
    if schema == PARTICIPANT_QUESTION_SCHEMA:
        return schema
    questions = (readiness.get("briefing") or {}).get("questions")
    if questions == [item["text"] for item in PARTICIPANT_QUESTION_SCHEMA["questions"]]:
        return PARTICIPANT_QUESTION_SCHEMA
    return None


def _bind_confirmed_answers(connection, *, user_id: int, readiness: dict, answers: dict,
                            bind_profile: bool = True) -> dict:
    """Persist provenance and, when M3/M4 inputs are unambiguous, freeze a profile."""
    schema = _question_schema(readiness)
    if schema is None or readiness.get("organization_kind") != "organization":
        return {"status": "waiting_for_supported_question_schema"}
    items = []
    for index, question in enumerate(schema["questions"], 1):
        raw = str(answers[f"answer_{index}"])
        items.append({"key": question["key"], "question_version": schema["version"],
                      "question_text": question["text"], "raw_answer": raw,
                      "normalized": raw, "normalization_source": "identity/1.0"})
    answer_set = {"schema_variant": schema["variant"], "schema_version": schema["version"],
                  "assignment_ref": readiness["assignment_ref"],
                  "questionnaire_revision_id": readiness.get('questionnaire_revision_id'), "items": items}
    checksum = _checksum(answer_set)
    binding = assignment_sources.current_binding(connection, user_id=user_id,
        organization_id=readiness['organization_id'], assignment_ref=readiness['assignment_ref'],
        questionnaire_revision_id=readiness.get('questionnaire_revision_id')) if bind_profile else None
    if binding:
        connection.execute('SELECT id FROM organization_assessment_assignments WHERE id=%s FOR UPDATE',
                           (binding['assignment_id'],))
        binding = assignment_sources.current_binding(connection, user_id=user_id,
            organization_id=readiness['organization_id'], assignment_ref=readiness['assignment_ref'],
            questionnaire_revision_id=readiness.get('questionnaire_revision_id'))
    connection.execute("SELECT id FROM users WHERE id=%s FOR UPDATE", (user_id,))
    # Re-read after the common user lock: two resolves must not create two M4s,
    # and an answer edit that won the lock invalidates a stale resolve request.
    prior = connection.execute('''SELECT * FROM participant_acquaintance_confirmations
        WHERE user_id=%s AND organization_id=%s AND assignment_ref=%s AND answers_checksum=%s''',
        (user_id, readiness['organization_id'], readiness['assignment_ref'], checksum)).fetchone()
    if prior and prior.get('personalized_profile_id'):
        return dict(prior)
    if bind_profile:
        state = state_store.read(connection, user_id=user_id, readiness=readiness) or {}
        if not mandatory_complete(readiness, state) or state.get('answers_json') != answers:
            raise ValueError('W02_CONFIRMATION_REQUIRED')
    user = connection.execute("SELECT full_name,to_jsonb(users)->>'job_description' AS position FROM users WHERE id=%s", (user_id,)).fetchone()
    professional = {
        "position_or_status": str((user or {}).get('position') or '').strip(),
        "regular_tasks": items[0]["raw_answer"],
        "decision_situations": items[1]["raw_answer"],
        "constraints_and_interactions": items[2]["raw_answer"],
        "acquaintance_answers": answer_set,
    }
    user_context_version_id = None
    profile_id = None
    if binding is not None and str((user or {}).get("full_name") or "").strip():
        previous = connection.execute('''SELECT conflicts_json FROM assessment_personalized_profiles
            WHERE user_id=%s AND organization_id=%s AND assessment_configuration_id=%s
            ORDER BY frozen_at DESC,id DESC LIMIT 1''',
            (user_id, readiness['organization_id'], binding['assessment_configuration_id'])).fetchone()
        conflicts = previous['conflicts_json'] if previous else []
        if any(item.get('type') in participant_profile.contexts.BLOCKING_CONFLICTS and not item.get('resolved')
               for item in conflicts):
            raise ValueError('W02_PROFILE_CONFLICT_REQUIRES_RESPONSIBLE')
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
            connection, user_id=user_id, assessment_configuration_id=int(binding['assessment_configuration_id']),
            organization_context_version_id=int(readiness["organization_context_version_id"]),
            role_profile_version_id=int(binding['role_profile_version_id']), user_context_version_id=user_context_version_id, conflicts=conflicts)
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


def resolve_confirmed_profile(connection, *, user_id: int) -> dict:
    """Explicit idempotent command; never infer consent or rewrite confirmed answers."""
    readiness = early_readiness(connection, user_id=user_id)
    if readiness['status'] != 'ready':
        raise ValueError('W02_ACQUAINTANCE_NOT_READY')
    state = state_store.read(connection, user_id=user_id, readiness=readiness)
    if (not state or state['organization_id'] != readiness['organization_id']
            or state.get('assignment_ref') != readiness['assignment_ref']
            or state.get('questionnaire_revision_id') != readiness.get('questionnaire_revision_id')
            or not state.get('consent_accepted_at') or not state.get('answers_confirmed_at')
            or state.get('consent_version') != readiness['briefing']['consent_version']):
        raise ValueError('W02_CONFIRMATION_REQUIRED')
    confirmation = connection.execute('''SELECT answers_json FROM participant_acquaintance_confirmations
        WHERE user_id=%s AND organization_id=%s AND assignment_ref=%s
          AND questionnaire_revision_id IS NOT DISTINCT FROM %s
        ORDER BY confirmed_at DESC,id DESC LIMIT 1''',
        (user_id, readiness['organization_id'], readiness['assignment_ref'],
         readiness.get('questionnaire_revision_id'))).fetchone()
    if not confirmation:
        raise ValueError('W02_CONFIRMATION_REQUIRED')
    items = confirmation['answers_json']['items']
    answers = {f'answer_{index}': item['raw_answer'] for index, item in enumerate(items, 1)}
    return _bind_confirmed_answers(connection, user_id=user_id, readiness=readiness, answers=answers)


def preparation_scope(connection, *, user_id: int, profile_id: int | None = None) -> dict | None:
    """Gate the canonical assignment, preserving genuinely historical legacy callers."""
    readiness = early_readiness(connection, user_id=user_id)
    managed = assignment_sources.has_managed_assignment(connection, user_id=user_id)
    if readiness.get('questionnaire_revision_id') is None and not managed:
        return None
    if readiness['status'] != 'ready':
        raise ValueError('W02_ORGANIZATION_DATA_REQUIRED')
    state = state_store.read(connection, user_id=user_id, readiness=readiness) or {}
    if not mandatory_complete(readiness, state):
        raise ValueError('W02_MANDATORY_STEPS_REQUIRED')
    late = late_readiness(connection, user_id=user_id, readiness=readiness)
    if late['status'] != 'ready_to_prepare':
        raise ValueError('W02_ASSIGNMENT_SOURCES_REQUIRED')
    effective_id = int(late['personalized_profile_id'])
    if profile_id is not None and profile_id != effective_id:
        raise ValueError('W02_PROFILE_ASSIGNMENT_SCOPE_MISMATCH')
    profile = participant_profile.profile_for_start(connection, user_id=user_id, profile_id=effective_id)
    return {'personalized_profile_id': effective_id, 'profile_checksum': profile['checksum'],
            'organization_id': readiness['organization_id'], 'assignment_ref': readiness['assignment_ref'],
            'questionnaire_revision_id': readiness['questionnaire_revision_id']}


def accept_consent(connection, *, user_id: int, version: int) -> dict:
    readiness = early_readiness(connection, user_id=user_id)
    expected = int((readiness.get("briefing") or {}).get("consent_version") or 0)
    if readiness["status"] != "ready" or version != expected:
        raise ValueError("W02_CONSENT_VERSION_MISMATCH")
    prior = state_store.activate(connection, user_id=user_id, readiness=readiness) or {}
    accepted = prior.get('consent_accepted_at') if prior.get('consent_version') == version else None
    return state_store.write(connection, user_id=user_id, readiness=readiness, state={
        **prior, 'status': prior.get('status') or 'in_progress',
        'current_step': max(int(prior.get('current_step') or 0), 1), 'consent_version': version,
        'consent_accepted_at': accepted or datetime.now(timezone.utc).replace(tzinfo=None),
    })


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
             AND questionnaire_revision_id IS NOT DISTINCT FROM %s
           ORDER BY confirmed_at DESC,id DESC LIMIT 1""",
        (user_id, readiness["organization_id"], readiness["assignment_ref"], readiness.get('questionnaire_revision_id')),
    ).fetchone()
    if confirmation is None or confirmation["personalized_profile_id"] is None:
        return {"status": "waiting_for_assessment_data", "reason": "W02_ANSWERS_NOT_BOUND",
                "personalized_profile_id": None}
    try:
        profile = participant_profile.profile_for_start(
            connection, user_id=user_id, profile_id=int(confirmation["personalized_profile_id"]),
        )
        return {"status": "ready_to_prepare", "reason": None, "personalized_profile_id": int(profile["id"])}
    except ValueError as exc:
        return {"status": "waiting_for_assessment_data", "reason": str(exc), "personalized_profile_id": None}
