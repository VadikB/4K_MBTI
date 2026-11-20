"""Versioned questionnaire intake shared by product, external and CSV adapters."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from Api.assessment_contexts import create_organization_context_draft, publish_organization_context

TEMPLATE_VARIANT = "corporate"
TEMPLATE_VERSION = "0.2"
COMPATIBLE_TEMPLATE_VERSIONS = {"0.1", TEMPLATE_VERSION}
HEADER = ("question_id", "field", "value")
FIELDS = {
    "C01": {"name", "organization_type", "industry", "activity_description"},
    "C02a": {"answer", "participant_text"},
    "C02b": {"answer"},
    "C03": {"answer", "participant_text"},
    "C17": {"case_reality_level", "organization_name_usage_rules", "restrictions"},
    "C21": {"organizer"},
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
    ("C03", "participant_text"),
    ("C17", "case_reality_level"), ("C17", "organization_name_usage_rules"),
}
ALLOWED_CHANNELS = {"csv", "product_form", "external_form"}
LEGACY_FIELDS = {("C04", "answer"), ("C21", "responsible_contact")}
MAX_SOURCE_BYTES = 1_048_576
ADMIN_CHOICES_PACKAGE = (Path(__file__).resolve().parents[1] / "assessment_definitions" /
                         "contexts" / "competencies_4k" / "1.1")


def _admin_choices_provenance() -> dict:
    path = ADMIN_CHOICES_PACKAGE / "admin_context_choices.json"
    content = path.read_bytes()
    checksum = hashlib.sha256(content).hexdigest()
    manifest = json.loads((ADMIN_CHOICES_PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    expected = {item["name"]: item["sha256"] for item in manifest["artifacts"]}.get(path.name)
    if expected != checksum:
        raise ValueError("ADMIN_CONTEXT_CHOICES_CHECKSUM_INVALID")
    metadata = json.loads(content)
    if metadata.get("status") != "approved_for_admin_form" or metadata.get("version") != "1.0":
        raise ValueError("ADMIN_CONTEXT_CHOICES_IDENTITY_INVALID")
    return {"id": metadata["id"], "version": metadata["version"], "sha256": checksum}


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
            if (question_id, field) in LEGACY_FIELDS:
                continue
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


def _current_revision_validation(row: dict) -> dict:
    """Revalidate old drafts under the current fields without hiding other errors."""
    if row.get("channel") == "csv" and row.get("raw_source_text"):
        return parse_csv(row["raw_source_text"])
    normalized = normalize_answers(answers=dict(row.get("answers_json") or {}), channel=str(row["channel"]))
    old_errors = (row.get("validation_json") or {}).get("errors") or []
    for error in old_errors:
        if (error.get("question_id"), error.get("field")) not in LEGACY_FIELDS and error not in normalized["errors"]:
            normalized["errors"].append(error)
    if normalized["errors"]:
        normalized["status"] = "invalid"
    return normalized


def save_preview(connection, *, organization_id: int, assignment_ref: str, channel: str,
                 template_variant: str, template_version: str, answers: dict,
                 raw_text: str | None, uploaded_by: int, source_author: str,
                 idempotency_key: str) -> dict:
    if template_variant != TEMPLATE_VARIANT or template_version not in COMPATIBLE_TEMPLATE_VERSIONS:
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
    organization = connection.execute(
        "SELECT name FROM organizations WHERE id=%s", (organization_id,),
    ).fetchone()
    if organization is None:
        raise ValueError("ORGANIZATION_NOT_FOUND")
    published = connection.execute(
        """SELECT v.id FROM assessment_organization_context_versions v
           JOIN assessment_organization_contexts c ON c.id=v.organization_context_id
           WHERE c.organization_id=%s AND v.status='published'
           ORDER BY v.version DESC,v.id DESC LIMIT 1""",
        (organization_id,),
    ).fetchone()
    row = connection.execute(
        """INSERT INTO questionnaire_response_revisions(
             organization_id,assignment_ref,template_variant,template_version,channel,status,
             answers_json,validation_json,raw_source_text,source_checksum,uploaded_by_user_id,
             source_author,idempotency_key,request_hash)
           VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s) RETURNING *""",
        (organization_id, assignment_ref, template_variant, template_version, channel,
         normalized["status"], json.dumps(normalized["answers"], ensure_ascii=False),
         json.dumps({"errors": normalized["errors"], "missing": normalized["missing"],
                     "expected_organization_name": organization["name"],
                     "expected_context_version_id": published["id"] if published else None}, ensure_ascii=False),
         raw_text, hashlib.sha256((raw_text or "").encode("utf-8")).hexdigest(), uploaded_by,
         source_author.strip(), idempotency_key, request_hash),
    ).fetchone()
    return dict(row)


def confirm(connection, *, revision_id: int, organization_id: int, confirmed_by: int) -> dict:
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
    normalized = _current_revision_validation(row)
    if normalized["errors"] or normalized["missing"]:
        raise ValueError("QUESTIONNAIRE_NOT_READY_FOR_CONFIRMATION")
    answers = normalized["answers"]
    organization = connection.execute(
        "SELECT name FROM organizations WHERE id=%s FOR UPDATE", (organization_id,),
    ).fetchone()
    if organization is None:
        raise ValueError("ORGANIZATION_NOT_FOUND")
    expected_name = (row.get("validation_json") or {}).get("expected_organization_name")
    if expected_name is not None and organization["name"] != expected_name:
        raise ValueError("QUESTIONNAIRE_ORGANIZATION_NAME_CONFLICT")
    current = connection.execute(
        """SELECT v.id,v.definition_json FROM assessment_organization_context_versions v
           JOIN assessment_organization_contexts c ON c.id=v.organization_context_id
           WHERE c.organization_id=%s AND v.status='published' ORDER BY v.version DESC,v.id DESC LIMIT 1""",
        (organization_id,),
    ).fetchone()
    validation = row.get("validation_json") or {}
    if "expected_context_version_id" in validation and validation["expected_context_version_id"] != (current["id"] if current else None):
        raise ValueError("QUESTIONNAIRE_CONTEXT_VERSION_CONFLICT")
    connection.execute(
        "UPDATE organizations SET name=%s,updated_at=NOW() WHERE id=%s",
        (answers["C01"]["name"], organization_id),
    )
    definition = dict(current["definition_json"] or {}) if current else {}
    definition.update(answers["C01"])
    definition.update({key: value for key, value in answers["C17"].items()
                       if key in {"case_reality_level", "organization_name_usage_rules", "restrictions"}})
    participant_briefing = {
        "purpose": answers["C02a"]["participant_text"],
        "customer_question": answers.get("C02b", {}).get("answer", ""),
        "organizer": answers.get("C21", {}).get("organizer", ""),
        "results_usage": answers["C03"]["participant_text"],
        "organization_type": answers["C01"]["organization_type"],
        "provided_participant_fields": PROVIDED_PARTICIPANT_FIELDS,
        "participant_questions": PARTICIPANT_QUESTIONS,
        "participant_question_schema": PARTICIPANT_QUESTION_SCHEMA,
        "consent_version": 1,
        "consent_text": "Подтвердите согласие на использование указанных сведений в рамках оценки.",
        "questionnaire_revision_id": int(row["id"]),
        "assignment_ref": str(row["assignment_ref"]),
    }
    definition.pop("participant_briefing", None)
    source_manifest = {"questionnaire_revision_id": int(row["id"]), "channel": row["channel"],
                       "template_variant": row["template_variant"], "template_version": row["template_version"],
                       "source_checksum": row["source_checksum"]}
    if row["channel"] == "product_form":
        source_manifest["admin_context_choices"] = _admin_choices_provenance()
    version_id = create_organization_context_draft(
        connection, organization_id=organization_id, definition=definition,
        source_manifest=source_manifest,
    )
    publish_organization_context(connection, version_id=version_id, confirmed_by_user_id=confirmed_by)
    saved = connection.execute(
        """UPDATE questionnaire_response_revisions SET status='confirmed',confirmed_by_user_id=%s,
           confirmed_at=NOW(),organization_context_version_id=%s,briefing_json=%s::jsonb,
           answers_json=%s::jsonb,validation_json=%s::jsonb
           WHERE id=%s RETURNING *""",
        (confirmed_by, version_id, json.dumps(participant_briefing, ensure_ascii=False),
         json.dumps(answers, ensure_ascii=False), json.dumps({"errors": [], "missing": []}),
         row["id"]),
    ).fetchone()
    return dict(saved)


def assignment_readiness(connection, *, organization_id: int, assignment_ref: str,
                         questionnaire_revision_id: int | None = None) -> dict:
    """Return the confirmed early minimum for one assessment preparation."""
    normalized_ref = str(assignment_ref or "").strip()
    if not normalized_ref:
        return {"status": "draft", "reason": "assignment_ref", "missing": ["assessment"]}
    # Admin/new assignment callers retain latest confirmed; participants pin the
    # immutable revision from their active source binding.
    exact = " AND id=%s" if questionnaire_revision_id is not None else ""
    params = (organization_id, normalized_ref)
    if questionnaire_revision_id is not None:
        params += (questionnaire_revision_id,)
    row = connection.execute(
        """SELECT id,assignment_ref,briefing_json,organization_context_version_id,confirmed_at
           FROM questionnaire_response_revisions
           WHERE organization_id=%s AND assignment_ref=%s AND status='confirmed'""" + exact + """
           ORDER BY confirmed_at DESC,id DESC LIMIT 1""",
        params,
    ).fetchone()
    if row is None:
        return {"status": "draft", "reason": "confirmed_questionnaire", "missing": ["confirmation"]}
    if row["organization_context_version_id"] is None:
        return {"status": "draft", "reason": "organization_context_version", "missing": ["context"]}
    briefing = dict(row["briefing_json"] or {})
    if str(briefing.get("organization_type") or "").strip().lower() in {
        "университет", "вуз", "university",
    }:
        return {"status": "draft", "reason": "university_admission_not_supported", "missing": ["admission"]}
    required = ("purpose", "results_usage")
    missing = [key for key in required if not str(briefing.get(key) or "").strip()]
    if missing:
        return {"status": "draft", "reason": "early_minimum", "missing": missing}
    return {
        "status": "ready", "reason": None, "missing": [], "assignment_ref": normalized_ref,
        "questionnaire_revision_id": int(row["id"]),
        "organization_context_version_id": int(row["organization_context_version_id"]),
        "briefing": briefing,
    }


_ASSIGNED_PARTICIPANTS_SQL = """
    SELECT DISTINCT u.id AS user_id
    FROM users u JOIN organization_memberships om ON om.user_id=u.id
    JOIN organizations o ON o.id=om.organization_id AND o.is_active=TRUE
    WHERE om.organization_id=%s AND u.id IN (
        SELECT oa.recipient_user_id FROM organization_assessment_assignments oa
        WHERE oa.organization_id=om.organization_id AND oa.assignment_ref=%s
          AND oa.status='active' AND oa.revoked_at IS NULL
        UNION
        SELECT legacy_user.id FROM organization_invitations oi
        JOIN users legacy_user ON LOWER(legacy_user.email)=LOWER(oi.recipient_email)
        WHERE oi.organization_id=om.organization_id AND oi.assignment_ref=%s
          AND oi.purpose='personal_registration' AND oi.revoked_at IS NULL
          AND oi.created_by_user_id IS DISTINCT FROM legacy_user.id
    )
"""


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

    participant_params = (organization_id, normalized_ref, normalized_ref)
    participant_rows = connection.execute(
        _ASSIGNED_PARTICIPANTS_SQL + " ORDER BY u.id", participant_params,
    ).fetchall()
    total_roles = len(participant_rows)
    ready_roles = 0
    reason_counts: dict[str, int] = {}
    in_progress = 0
    from Api import assessment_assignment_sources as assignment_sources
    from Api.acquaintance import late_readiness
    from Api.admin_assignment_projection import preparation_for_assignment
    managed = assignment_sources.schema_available(connection)
    for row in participant_rows:
        user_id = int(row["user_id"])
        binding = assignment_sources.participant_binding(
            connection, user_id=user_id, organization_id=organization_id,
            assignment_ref=normalized_ref,
        ) if managed else None
        if managed and binding is None:
            selected_readiness = {"status": "draft", "reason": "assignment_sources"}
        else:
            selected_readiness = assignment_readiness(
                connection, organization_id=organization_id, assignment_ref=normalized_ref,
                **({"questionnaire_revision_id": binding["questionnaire_revision_id"]} if binding else {}),
            )
            selected_readiness.update(organization_id=organization_id,
                assignment_id=binding["assignment_id"] if binding else None)
        late = late_readiness(connection, user_id=user_id, readiness=selected_readiness)
        if late["status"] == "ready_to_prepare":
            ready_roles += 1
        else:
            reason = str(late.get("reason") or "READINESS_CHECK_FAILED").split(":", 1)[0]
            category = (
                "acquaintance_wait" if reason == "W02_ANSWERS_NOT_BOUND" else
                "profile_binding" if reason.startswith(("M4_PROFILE_", "W02_PROFILE_"))
                    or reason == "assignment_sources" else "verification_error"
            )
            reason_counts[category] = reason_counts.get(category, 0) + 1
        if binding:
            preparation = preparation_for_assignment(connection, assignment_id=int(binding["assignment_id"]))
            if preparation.get("status") in {"queued", "running"}:
                in_progress += 1
    if total_roles == 0:
        roles_state = "not_started"
        roles_message = "Для выбранной оценки ещё нет назначенных участников."
        roles_action = "people"
    elif ready_roles < total_roles:
        roles_state = "incomplete"
        waiting = reason_counts.get("acquaintance_wait", 0)
        profile = reason_counts.get("profile_binding", 0)
        verification = reason_counts.get("verification_error", 0)
        details = []
        if waiting:
            details.append(f"ожидается завершение знакомства: {waiting}")
        if profile:
            details.append(f"нужно проверить связку профиля и роли: {profile}")
        if verification:
            details.append(f"ошибка проверки готовности: {verification}")
        roles_message = (
            f"К подготовке готовы {ready_roles} из {total_roles}. " + "; ".join(details) + "."
        )
        roles_action = "people" if profile else None
    else:
        roles_state = "ready"
        roles_message = f"К подготовке готовы все участники выбранной оценки: {ready_roles}."
        roles_action = None

    context_state = "ready" if early["status"] == "ready" else early_state
    context_message = (
        "Контекст выбранной оценки подтверждён и закреплён сервером."
        if context_state == "ready" else
        "Контекст появится после подтверждения раннего минимума для выбранной оценки."
    )
    overall = "preparing" if in_progress else (
        "ready" if roles_state == "ready" else "incomplete"
    )
    return {
        "status": overall,
        "assignment_ref": normalized_ref,
        "early": {"status": early_state, "message": early_message, "missing": list(early.get("missing") or [])},
        "context": {"status": context_state, "message": context_message},
        "roles": {
            "status": roles_state, "message": roles_message, "ready": ready_roles,
            "total": total_roles, "reasons": reason_counts, "action_view": roles_action,
        },
        "preparation": {
            "status": "in_progress" if in_progress else "idle",
            "message": f"Идёт подготовка для {in_progress} участников." if in_progress else "Активной подготовки сейчас нет.",
        },
    }


def template_csv() -> str:
    rows = [(qid, field, "") for qid, fields in FIELDS.items() for field in sorted(fields)]
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(HEADER); writer.writerows(rows)
    return output.getvalue()


def _participant_projection(answers: dict) -> dict:
    """Fields that a participant may see before starting an assessment."""
    return {
        "organization_name": str(answers.get("C01", {}).get("name") or ""),
        "organization_type": str(answers.get("C01", {}).get("organization_type") or ""),
        "industry": str(answers.get("C01", {}).get("industry") or ""),
        "activity_description": str(answers.get("C01", {}).get("activity_description") or ""),
        "purpose": str(answers.get("C02a", {}).get("participant_text") or ""),
        "results_usage": str(answers.get("C03", {}).get("participant_text") or ""),
        "organizer": str(answers.get("C21", {}).get("organizer") or ""),
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
    normalized = _current_revision_validation(item)
    answers = normalized["answers"]
    participant_preview = _participant_projection(answers)
    current_projection = _participant_projection(
        dict((confirmed_row or {}).get("answers_json") or {}),
    )
    effective = item if item["status"] == "confirmed" else confirmed_row
    return {
        "id": int(item["id"]), "assignment_ref": str(item["assignment_ref"]),
        "status": str(item["status"]) if item["status"] == "confirmed" else normalized["status"],
        "channel": str(item["channel"]),
        "source_author": str(item.get("source_author") or ""),
        "uploaded_by_user_id": int(item["uploaded_by_user_id"]) if item.get("uploaded_by_user_id") is not None else None,
        "uploaded_by_email": item.get("uploaded_by_email"),
        "uploaded_by_name": item.get("uploaded_by_name"),
        "validation_json": {"errors": normalized["errors"], "missing": normalized["missing"]},
        "answers_json": answers,
        "participant_preview": participant_preview,
        "changes": _projection_changes(current_projection, participant_preview),
        "is_first_publication": confirmed_row is None,
        "confirmed_at": item.get("confirmed_at"),
        "effective_confirmed": {
            "id": int(effective["id"]),
            "assignment_ref": str(effective["assignment_ref"]),
            "confirmed_at": effective.get("confirmed_at"),
        } if effective is not None else None,
    }
