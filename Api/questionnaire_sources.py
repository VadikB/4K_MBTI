"""Versioned questionnaire intake shared by product, external and CSV adapters."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from Api.assessment_contexts import create_organization_context_draft, publish_organization_context

TEMPLATE_VARIANT = "corporate"
TEMPLATE_VERSION = "0.1"
HEADER = ("question_id", "field", "value")
FIELDS = {
    "C01": {"name", "organization_type", "industry", "activity_description"},
    "C02a": {"answer", "participant_text"},
    "C02b": {"answer"},
    "C03": {"answer", "participant_text"},
    "C04": {"answer"},
    "C17": {"case_reality_level", "organization_name_usage_rules", "restrictions"},
    "C21": {"organizer", "responsible_contact"},
    # C22 is retained as source material only. It never replaces the separate,
    # authenticated confirmation event performed by an organization admin.
    "C22": {"answer"},
    **{key: {"answer"} for key in (
        "C05", "C06", "C07a", "C07b", "C08", "C09", "C10", "C11", "C12",
        "C13", "C14", "C15", "C16", "C18", "C20",
    )},
}
EARLY_REQUIRED = {
    ("C01", "name"), ("C01", "organization_type"), ("C01", "industry"),
    ("C01", "activity_description"), ("C02a", "participant_text"),
    ("C03", "participant_text"), ("C04", "answer"),
    ("C17", "case_reality_level"), ("C17", "organization_name_usage_rules"),
    ("C21", "organizer"), ("C21", "responsible_contact"),
}
ALLOWED_CHANNELS = {"csv", "product_form", "external_form"}
ALLOWED_RECIPIENTS = {"participant", "organization_admin"}
MAX_SOURCE_BYTES = 1_048_576


def _load_participant_question_schema() -> dict:
    path = (Path(__file__).resolve().parents[1] / "assessment_definitions" / "questionnaires"
            / "participant_context" / "corporate" / "1.0" / "definition.json")
    manifest = json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
    expected = manifest.get("artifacts", [{}])[0].get("sha256")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("PARTICIPANT_CONTEXT_ARTIFACT_CHECKSUM_INVALID")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("variant") != "corporate" or value.get("version") != "1.0":
        raise ValueError("PARTICIPANT_CONTEXT_ARTIFACT_IDENTITY_INVALID")
    questions = value.get("questions")
    if not isinstance(questions, list) or [item.get("key") for item in questions] != [
        "work_situations", "decision_situations", "constraints_interactions",
    ] or any(not str(item.get("text") or "").strip() for item in questions):
        raise ValueError("PARTICIPANT_CONTEXT_ARTIFACT_QUESTIONS_INVALID")
    return {"variant": value["variant"], "version": value["version"], "questions": questions}


PARTICIPANT_QUESTION_SCHEMA = _load_participant_question_schema()
PARTICIPANT_QUESTIONS = [item["text"] for item in PARTICIPANT_QUESTION_SCHEMA["questions"]]
PROVIDED_PARTICIPANT_FIELDS = ["role", "position", "duties"]


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_csv(text: str) -> dict:
    if not isinstance(text, str) or not text.strip("\ufeff\r\n "):
        raise ValueError("QUESTIONNAIRE_EMPTY_FILE")
    try:
        clean = text.lstrip("\ufeff")
        first = clean.splitlines()[0]
        delimiter = "," if first == ",".join(HEADER) else ";" if first == ";".join(HEADER) else None
        if delimiter is None:
            raise ValueError("QUESTIONNAIRE_HEADER_INVALID")
        reader = csv.DictReader(io.StringIO(clean), delimiter=delimiter)
        if tuple(reader.fieldnames or ()) != HEADER:
            raise ValueError("QUESTIONNAIRE_HEADER_INVALID")
        rows = []
        values: dict[str, dict[str, str]] = {}
        seen: dict[tuple[str, str], str] = {}
        errors = []
        for line, raw in enumerate(reader, start=2):
            question_id = str(raw.get("question_id") or "").strip()
            field = str(raw.get("field") or "").strip()
            value = str(raw.get("value") or "").strip()
            if question_id not in FIELDS or field not in FIELDS.get(question_id, set()):
                errors.append({"line": line, "code": "UNKNOWN_FIELD", "question_id": question_id, "field": field})
                continue
            key = (question_id, field)
            if key in seen and seen[key] != value:
                errors.append({"line": line, "code": "CONFLICTING_VALUE", "question_id": question_id, "field": field})
                continue
            seen[key] = value
            values.setdefault(question_id, {})[field] = value
            rows.append({"question_id": question_id, "field": field, "value": value})
    except UnicodeError as exc:
        raise ValueError("QUESTIONNAIRE_ENCODING_INVALID") from exc
    missing = [f"{qid}.{field}" for qid, field in sorted(EARLY_REQUIRED)
               if not values.get(qid, {}).get(field)]
    return {"rows": rows, "answers": values, "errors": errors, "missing": missing,
            "delimiter": delimiter, "status": "invalid" if errors else "draft" if missing else "ready_for_confirmation"}


def normalize_answers(*, answers: dict, channel: str) -> dict:
    if channel not in ALLOWED_CHANNELS:
        raise ValueError("QUESTIONNAIRE_CHANNEL_UNSUPPORTED")
    rows = [{"question_id": qid, "field": field, "value": str(value).strip()}
            for qid, fields in answers.items() for field, value in fields.items()]
    csv_text = ",".join(HEADER) + "\n" + "\n".join(
        ",".join('"' + item[key].replace('"', '""') + '"' for key in HEADER) for item in rows
    )
    return parse_csv(csv_text)


def save_preview(connection, *, organization_id: int, assignment_ref: str, channel: str,
                 template_variant: str, template_version: str, answers: dict,
                 raw_text: str | None, uploaded_by: int, source_author: str,
                 idempotency_key: str) -> dict:
    if template_variant != TEMPLATE_VARIANT or template_version != TEMPLATE_VERSION:
        raise ValueError("QUESTIONNAIRE_TEMPLATE_MISMATCH")
    if channel not in ALLOWED_CHANNELS:
        raise ValueError("QUESTIONNAIRE_CHANNEL_UNSUPPORTED")
    if raw_text is not None and len(raw_text.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("QUESTIONNAIRE_FILE_TOO_LARGE")
    normalized = parse_csv(raw_text or "") if channel == "csv" else normalize_answers(answers=answers, channel=channel)
    request = {"organization_id": organization_id, "assignment_ref": assignment_ref,
               "channel": channel, "template_variant": template_variant,
               "template_version": template_version, "answers": normalized["answers"]}
    request_hash = _digest(request)
    prior = connection.execute(
        "SELECT * FROM questionnaire_response_revisions WHERE uploaded_by_user_id=%s AND idempotency_key=%s",
        (uploaded_by, idempotency_key),
    ).fetchone()
    if prior:
        if prior["request_hash"] != request_hash:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return dict(prior)
    row = connection.execute(
        """INSERT INTO questionnaire_response_revisions(
             organization_id,assignment_ref,template_variant,template_version,channel,status,
             answers_json,validation_json,raw_source_text,source_checksum,uploaded_by_user_id,
             source_author,idempotency_key,request_hash)
           VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s) RETURNING *""",
        (organization_id, assignment_ref, template_variant, template_version, channel,
         normalized["status"], json.dumps(normalized["answers"], ensure_ascii=False),
         json.dumps({"errors": normalized["errors"], "missing": normalized["missing"]}, ensure_ascii=False),
         raw_text, hashlib.sha256((raw_text or "").encode("utf-8")).hexdigest(), uploaded_by,
         source_author.strip(), idempotency_key, request_hash),
    ).fetchone()
    return dict(row)


def confirm(connection, *, revision_id: int, organization_id: int, confirmed_by: int,
            recipients: list[str], recipient_user_ids: list[int] | None = None) -> dict:
    candidate = connection.execute(
        "SELECT assignment_ref FROM questionnaire_response_revisions WHERE id=%s AND organization_id=%s",
        (revision_id, organization_id),
    ).fetchone()
    if candidate is None:
        raise ValueError("QUESTIONNAIRE_REVISION_NOT_FOUND")
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"{organization_id}:{candidate['assignment_ref']}",),
    )
    row = connection.execute(
        "SELECT * FROM questionnaire_response_revisions WHERE id=%s AND organization_id=%s FOR UPDATE",
        (revision_id, organization_id),
    ).fetchone()
    if row is None:
        raise ValueError("QUESTIONNAIRE_REVISION_NOT_FOUND")
    if row["status"] == "confirmed":
        return dict(row)
    newer_confirmed = connection.execute(
        """SELECT id FROM questionnaire_response_revisions
           WHERE organization_id=%s AND assignment_ref=%s AND status='confirmed' AND id>%s
           ORDER BY id DESC LIMIT 1""",
        (organization_id, row["assignment_ref"], row["id"]),
    ).fetchone()
    if newer_confirmed is not None:
        raise ValueError("QUESTIONNAIRE_REVISION_CONFLICT")
    validation = dict(row["validation_json"] or {})
    if validation.get("errors") or validation.get("missing"):
        raise ValueError("QUESTIONNAIRE_NOT_READY_FOR_CONFIRMATION")
    mapped = sorted(set(recipients))
    if "participant" not in mapped or any(item not in ALLOWED_RECIPIENTS for item in mapped):
        raise ValueError("QUESTIONNAIRE_RECIPIENTS_CONFLICT")
    selected_users = sorted(set(int(value) for value in (recipient_user_ids or [])))
    if ("organization_admin" in mapped) != bool(selected_users):
        raise ValueError("QUESTIONNAIRE_RECIPIENTS_CONFLICT")
    answers = dict(row["answers_json"] or {})
    current = connection.execute(
        """SELECT v.definition_json FROM assessment_organization_context_versions v
           JOIN assessment_organization_contexts c ON c.id=v.organization_context_id
           WHERE c.organization_id=%s AND v.status='published' ORDER BY v.version DESC,v.id DESC LIMIT 1""",
        (organization_id,),
    ).fetchone()
    definition = dict(current["definition_json"] or {}) if current else {}
    definition.update(answers["C01"])
    definition.update({key: value for key, value in answers["C17"].items()
                       if key in {"case_reality_level", "organization_name_usage_rules", "restrictions"}})
    authorized_recipients = []
    if selected_users:
        recipient_rows = connection.execute("""SELECT u.id,u.full_name,u.email
            FROM organization_memberships om JOIN users u ON u.id=om.user_id
            JOIN organizations o ON o.id=om.organization_id
            WHERE om.organization_id=%s AND om.role='admin' AND o.is_active=TRUE AND u.id=ANY(%s)
            ORDER BY LOWER(u.email)""", (organization_id, selected_users)).fetchall()
        if {int(item["id"]) for item in recipient_rows} != set(selected_users):
            raise ValueError("REPORT_RECIPIENT_SCOPE_CONFLICT")
        authorized_recipients = [
            {"user_id": int(item["id"]), "name": item["full_name"], "email": item["email"]}
            for item in recipient_rows
        ]
    access_projection = recipient_access_projection(mapped)
    participant_briefing = {
        "purpose": answers["C02a"]["participant_text"],
        "customer_question": answers["C02b"].get("answer", ""),
        "organizer": answers["C21"]["organizer"],
        "responsible_contact": answers["C21"]["responsible_contact"],
        "results_usage": answers["C03"]["participant_text"],
        "result_recipients": access_projection["result_recipients"],
        "recipient_mapping": access_projection["recipient_mapping"],
        "organization_type": answers["C01"]["organization_type"],
        "provided_participant_fields": PROVIDED_PARTICIPANT_FIELDS,
        "participant_questions": PARTICIPANT_QUESTIONS,
        "participant_question_schema": PARTICIPANT_QUESTION_SCHEMA,
        "consent_version": 1,
        "consent_text": "Подтвердите согласие на использование указанных сведений в рамках оценки.",
        "questionnaire_revision_id": int(row["id"]),
        "assignment_ref": str(row["assignment_ref"]),
    }
    if authorized_recipients:
        participant_briefing["authorized_recipients"] = authorized_recipients
    definition.pop("participant_briefing", None)
    version_id = create_organization_context_draft(
        connection, organization_id=organization_id, definition=definition,
        source_manifest={"questionnaire_revision_id": int(row["id"]), "channel": row["channel"],
                         "template_variant": row["template_variant"], "template_version": row["template_version"],
                         "source_checksum": row["source_checksum"]},
    )
    publish_organization_context(connection, version_id=version_id, confirmed_by_user_id=confirmed_by)
    from Api import m8_report_access
    m8_report_access.create_revision(
        connection, questionnaire_revision_id=int(row["id"]), organization_id=organization_id,
        assignment_ref=str(row["assignment_ref"]), recipient_user_ids=selected_users,
        source_author=str(row["source_author"]), confirmed_by=confirmed_by,
    )
    saved = connection.execute(
        """UPDATE questionnaire_response_revisions SET status='confirmed',confirmed_by_user_id=%s,
           confirmed_at=NOW(),organization_context_version_id=%s,briefing_json=%s::jsonb,
           recipient_mapping_json=%s::jsonb
           WHERE id=%s RETURNING *""",
        (confirmed_by, version_id, json.dumps(participant_briefing, ensure_ascii=False),
         json.dumps(mapped), row["id"]),
    ).fetchone()
    return dict(saved)


def assignment_readiness(connection, *, organization_id: int, assignment_ref: str) -> dict:
    """Return the confirmed early minimum for one assessment preparation."""
    normalized_ref = str(assignment_ref or "").strip()
    if not normalized_ref:
        return {"status": "draft", "reason": "assignment_ref", "missing": ["assessment"]}
    row = connection.execute(
        """SELECT id,assignment_ref,briefing_json,organization_context_version_id,confirmed_at
           FROM questionnaire_response_revisions
           WHERE organization_id=%s AND assignment_ref=%s AND status='confirmed'
           ORDER BY confirmed_at DESC,id DESC LIMIT 1""",
        (organization_id, normalized_ref),
    ).fetchone()
    if row is None:
        return {"status": "draft", "reason": "confirmed_questionnaire", "missing": ["confirmation"]}
    briefing = dict(row["briefing_json"] or {})
    if str(briefing.get("organization_type") or "").strip().lower() in {
        "университет", "вуз", "university",
    }:
        return {"status": "draft", "reason": "university_admission_not_supported", "missing": ["admission"]}
    required = ("purpose", "organizer", "responsible_contact", "results_usage", "result_recipients")
    missing = [key for key in required if not str(briefing.get(key) or "").strip()]
    if missing:
        return {"status": "draft", "reason": "early_minimum", "missing": missing}
    return {
        "status": "ready", "reason": None, "missing": [], "assignment_ref": normalized_ref,
        "questionnaire_revision_id": int(row["id"]),
        "organization_context_version_id": int(row["organization_context_version_id"]),
        "briefing": briefing,
    }


def admin_assignment_readiness(connection, *, organization_id: int, assignment_ref: str) -> dict:
    """Admin-safe explanation of server-owned gates for one assessment preparation."""
    normalized_ref = str(assignment_ref or "").strip()
    early = assignment_readiness(
        connection, organization_id=organization_id, assignment_ref=normalized_ref,
    )
    latest = None
    if normalized_ref:
        latest = connection.execute(
            """SELECT status FROM questionnaire_response_revisions
               WHERE organization_id=%s AND assignment_ref=%s
               ORDER BY created_at DESC,id DESC LIMIT 1""",
            (organization_id, normalized_ref),
        ).fetchone()
    if early["status"] == "ready":
        early_state = "ready"
        early_message = "Ранний минимум подтверждён. Участников можно приглашать."
    elif latest is not None:
        early_state = "draft_unconfirmed"
        early_message = "Есть черновик, но он не подтверждён. Откройте анкету и подтвердите сведения."
    else:
        early_state = "data_missing"
        early_message = "Для выбранной оценки ещё нет подтверждённых сведений. Заполните данные организации или загрузите анкету."

    member_rows = connection.execute(
        """SELECT user_id FROM organization_memberships
           WHERE organization_id=%s AND role='member' ORDER BY user_id""",
        (organization_id,),
    ).fetchall()
    total_roles = len(member_rows)
    ready_roles = 0
    if early["status"] == "ready":
        # Reuse the participant late gate with the selected assignment instead of
        # reconstructing profile readiness from client-facing fields.
        from Api.acquaintance import late_readiness
        selected_readiness = {
            "status": "ready", "reason": None, "organization_id": organization_id,
            "assignment_ref": normalized_ref,
        }
        ready_roles = sum(
            late_readiness(
                connection, user_id=int(row["user_id"]), readiness=selected_readiness,
            )["status"] == "ready_to_prepare"
            for row in member_rows
        )
    if total_roles == 0:
        roles_state = "not_started"
        roles_message = "Участники ещё не добавлены. Их можно добавить до заполнения анкеты."
    elif ready_roles < total_roles:
        roles_state = "incomplete"
        roles_message = f"Роли готовы у {ready_roles} из {total_roles} участников. Заполните недостающие роли в списке участников."
    else:
        roles_state = "ready"
        roles_message = f"Роли подтверждены для всех участников: {ready_roles}."

    preparation = connection.execute(
        """SELECT COUNT(*) FILTER (WHERE latest.status IN ('queued','running'))::int AS in_progress
           FROM organization_memberships om
           LEFT JOIN LATERAL (
             SELECT status FROM assessment_preparation_jobs
             WHERE user_id=om.user_id ORDER BY created_at DESC LIMIT 1
           ) latest ON TRUE
           WHERE om.organization_id=%s AND om.role='member'""",
        (organization_id,),
    ).fetchone() or {"in_progress": 0}
    in_progress = int(preparation.get("in_progress") or 0)
    context_state = "ready" if early["status"] == "ready" else early_state
    context_message = (
        "Контекст выбранной оценки подтверждён и закреплён сервером."
        if context_state == "ready" else
        "Контекст появится после подтверждения раннего минимума для выбранной оценки."
    )
    overall = "preparing" if in_progress else (
        "ready" if early["status"] == "ready" and roles_state == "ready" else "incomplete"
    )
    return {
        "status": overall,
        "assignment_ref": normalized_ref,
        "early": {"status": early_state, "message": early_message, "missing": list(early.get("missing") or [])},
        "context": {"status": context_state, "message": context_message},
        "roles": {"status": roles_state, "message": roles_message, "ready": ready_roles, "total": total_roles},
        "preparation": {
            "status": "in_progress" if in_progress else "idle",
            "message": f"Идёт подготовка для {in_progress} участников." if in_progress else "Активной подготовки сейчас нет.",
        },
    }


def template_csv() -> str:
    rows = [(qid, field, "") for qid, fields in FIELDS.items() for field in sorted(fields)]
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(HEADER); writer.writerows(rows)
    return output.getvalue()


def recipient_access_projection(recipient_mapping: list[str] | None = None) -> dict:
    """Participant-safe explanation derived only from the effective access mapping."""
    mapped = sorted(set(recipient_mapping or ["participant"]))
    return {
        "recipient_mapping": mapped,
        "result_recipients": (
            "Результаты доступны участнику и выбранным представителям заказчика."
            if "organization_admin" in mapped else
            "Результаты доступны только участнику."
        ),
    }


def _participant_projection(answers: dict, *, recipient_mapping: list[str] | None = None) -> dict:
    """Fields that a participant may see before starting an assessment."""
    access = recipient_access_projection(recipient_mapping)
    return {
        "organization_name": str(answers.get("C01", {}).get("name") or ""),
        "organization_type": str(answers.get("C01", {}).get("organization_type") or ""),
        "industry": str(answers.get("C01", {}).get("industry") or ""),
        "activity_description": str(answers.get("C01", {}).get("activity_description") or ""),
        "purpose": str(answers.get("C02a", {}).get("participant_text") or ""),
        "results_usage": str(answers.get("C03", {}).get("participant_text") or ""),
        "result_recipients": access["result_recipients"],
        "organizer": str(answers.get("C21", {}).get("organizer") or ""),
        "responsible_contact": str(answers.get("C21", {}).get("responsible_contact") or ""),
    }


def _projection_changes(current: dict, proposed: dict) -> list[dict]:
    return [
        {"field": key, "before": str(current.get(key) or ""), "after": str(value or "")}
        for key, value in proposed.items()
        if str(current.get(key) or "") != str(value or "")
    ]


def public_revision(row: dict, *, confirmed_row: dict | None = None) -> dict:
    """Admin-safe projection without raw source, checksums or internal request metadata."""
    item = dict(row)
    answers = dict(item.get("answers_json") or {})
    recipient_mapping = list(item.get("recipient_mapping_json") or ["participant"])
    current_mapping = list((confirmed_row or {}).get("recipient_mapping_json") or ["participant"])
    participant_preview = _participant_projection(answers, recipient_mapping=recipient_mapping)
    current_projection = _participant_projection(
        dict((confirmed_row or {}).get("answers_json") or {}), recipient_mapping=current_mapping,
    )
    return {
        "id": int(item["id"]), "assignment_ref": str(item["assignment_ref"]),
        "status": str(item["status"]), "channel": str(item["channel"]),
        "validation_json": dict(item.get("validation_json") or {}),
        "answers_json": answers,
        "participant_preview": participant_preview,
        "changes": _projection_changes(current_projection, participant_preview),
        "is_first_publication": confirmed_row is None,
        "recipient_options": ["participant", "organization_admin"],
        "recipient_projections": {
            "participant": recipient_access_projection(["participant"])["result_recipients"],
            "organization_admin": recipient_access_projection(
                ["participant", "organization_admin"],
            )["result_recipients"],
        },
        "confirmed_at": item.get("confirmed_at"),
    }
