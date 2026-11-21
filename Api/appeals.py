"""Participant data appeals. Authorization is performed by the HTTP boundary."""
import json

from Api import assessment_assignment_sources


def read_operation(connection, *, user_id, operation_id, assignment_id,
                   questionnaire_revision_id, message=None):
    row = connection.execute("""SELECT request_json,receipt_json FROM participant_data_issue_operations
        WHERE user_id=%s AND operation_id=%s""", (user_id, operation_id)).fetchone()
    if row is None:
        return None
    request = row['request_json']
    if (request['assignment_id'] != assignment_id
            or request['questionnaire_revision_id'] != questionnaire_revision_id
            or (message is not None and request['message'] != message)):
        raise ValueError('W02_ISSUE_OPERATION_MISMATCH')
    return dict(row['receipt_json'])


def save_operation(connection, *, user_id, operation_id, request, receipt):
    connection.execute("""INSERT INTO participant_data_issue_operations
        (user_id,operation_id,issue_id,request_json,receipt_json) VALUES(%s,%s,%s,%s::jsonb,%s::jsonb)""",
        (user_id, operation_id, receipt['id'], json.dumps(request, ensure_ascii=False),
         json.dumps(receipt, ensure_ascii=False)))


def list_issues(connection, *, organization_id: int | None, user_id: int) -> list[dict]:
    organization_filter = "AND issue.organization_id=%s" if organization_id is not None else ""
    params = (user_id, organization_id) if organization_id is not None else (user_id,)
    rows = connection.execute(
        f"""SELECT issue.id, issue.user_id, issue.organization_id, issue.message,
                  issue.status, issue.created_at, issue.assignment_ref,
                  issue.questionnaire_revision_id, issue.assignment_id, issue.claimed_by_user_id,
                  issue.claimed_at, reply.message AS reply_message,
                  EXISTS (SELECT 1 FROM organization_memberships owner
                    WHERE owner.organization_id=issue.organization_id
                      AND owner.user_id=issue.claimed_by_user_id AND owner.role='admin') AS claimed_by_active_admin,
                  reply.author_user_id AS reply_author_user_id,
                  NULLIF(BTRIM(to_jsonb(author)->>'full_name'), '') AS reply_author_display_name,
                  reply.created_at AS replied_at
           FROM participant_data_issue_reports issue
           LEFT JOIN participant_data_issue_replies reply ON reply.issue_id=issue.id
           LEFT JOIN users author ON author.id=reply.author_user_id
           WHERE issue.user_id=%s {organization_filter}
           ORDER BY issue.created_at DESC, issue.id DESC""",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def list_participant_issues(connection, *, user_id: int) -> list[dict]:
    issues = list_issues(connection, organization_id=None, user_id=user_id)
    exact_ids = [
        item['id'] for item in issues if item['assignment_ref']
        and item['assignment_id'] is not None and item['questionnaire_revision_id'] is not None
    ]
    names = {}
    if exact_ids and assessment_assignment_sources.schema_available(connection):
        # The same reference can be assigned again. Read only this issue's saved
        # assignment and revision, including historical bindings. If the pair
        # has held different configurations, it no longer identifies one name.
        rows = connection.execute("""
            SELECT issue.id,
                CASE WHEN COUNT(DISTINCT binding.assessment_configuration_id) = 1
                     THEN MAX(NULLIF(BTRIM(configuration.name), '')) END AS assessment_display_name
            FROM participant_data_issue_reports issue
            JOIN organization_assessment_assignments assignment
              ON assignment.id=issue.assignment_id AND assignment.recipient_user_id=issue.user_id
             AND assignment.organization_id=issue.organization_id AND assignment.assignment_ref=issue.assignment_ref
            JOIN questionnaire_response_revisions revision
              ON revision.id=issue.questionnaire_revision_id AND revision.organization_id=issue.organization_id
             AND revision.assignment_ref=issue.assignment_ref
            JOIN organization_assessment_source_bindings binding
              ON binding.assignment_id=assignment.id AND binding.questionnaire_revision_id=revision.id
            JOIN assessment_configurations configuration ON configuration.id=binding.assessment_configuration_id
            WHERE issue.user_id=%s AND issue.id=ANY(%s)
            GROUP BY issue.id
        """, (user_id, exact_ids)).fetchall()
        names = {row['id']: row['assessment_display_name'] for row in rows}

    visible = ('id', 'organization_id', 'message', 'status', 'created_at',
               'assignment_ref', 'assignment_id', 'questionnaire_revision_id',
               'reply_message', 'reply_author_display_name', 'replied_at')
    return [
        {**{key: item[key] for key in visible}, 'assessment_display_name': names.get(item['id'])}
        for item in issues
    ]


def claim_issue(connection, *, organization_id: int, user_id: int, issue_id: int, actor_id: int) -> dict | None:
    row = connection.execute(
        """UPDATE participant_data_issue_reports issue
           SET claimed_by_user_id=%s,
               claimed_at=CASE WHEN issue.claimed_by_user_id=%s THEN issue.claimed_at ELSE NOW() END,
               status='in_progress'
           WHERE issue.id=%s AND issue.organization_id=%s AND issue.user_id=%s
             AND issue.status IN ('open','in_progress')
             AND (issue.claimed_by_user_id IS NULL OR issue.claimed_by_user_id=%s
               OR NOT EXISTS (SELECT 1 FROM organization_memberships owner
                 WHERE owner.organization_id=issue.organization_id
                   AND owner.user_id=issue.claimed_by_user_id AND owner.role='admin'))
           RETURNING id,claimed_by_user_id,status""",
        (actor_id, actor_id, issue_id, organization_id, user_id, actor_id),
    ).fetchone()
    return dict(row) if row else None


def reply_to_issue(connection, *, organization_id: int, user_id: int, issue_id: int,
                   actor_id: int, message: str) -> dict:
    normalized = str(message or "").strip()
    if not normalized or len(normalized) > 4000:
        raise ValueError("ISSUE_REPLY_INVALID")
    issue = connection.execute(
        """SELECT id, status, claimed_by_user_id FROM participant_data_issue_reports
           WHERE id=%s AND organization_id=%s AND user_id=%s FOR UPDATE""",
        (issue_id, organization_id, user_id),
    ).fetchone()
    if issue is None:
        raise LookupError("ISSUE_NOT_FOUND")
    existing = connection.execute(
        "SELECT author_user_id,message,created_at FROM participant_data_issue_replies WHERE issue_id=%s",
        (issue_id,),
    ).fetchone()
    if existing:
        if int(existing["author_user_id"]) == actor_id and existing["message"] == normalized:
            return {"issue_id": issue_id, **dict(existing)}
        raise ValueError("ISSUE_ALREADY_ANSWERED")
    if int(issue["claimed_by_user_id"] or 0) != actor_id or issue["status"] != "in_progress":
        raise ValueError("ISSUE_CLAIM_REQUIRED")
    row = connection.execute(
        """INSERT INTO participant_data_issue_replies(issue_id,author_user_id,message)
           VALUES(%s,%s,%s) RETURNING author_user_id,message,created_at""",
        (issue_id, actor_id, normalized),
    ).fetchone()
    connection.execute(
        "UPDATE participant_data_issue_reports SET status='answered',resolved_at=NOW() WHERE id=%s",
        (issue_id,),
    )
    return {"issue_id": issue_id, **dict(row)}
