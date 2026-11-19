"""Participant data appeals. Authorization is performed by the HTTP boundary."""


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
                  reply.created_at AS replied_at
           FROM participant_data_issue_reports issue
           LEFT JOIN participant_data_issue_replies reply ON reply.issue_id=issue.id
           WHERE issue.user_id=%s {organization_filter}
           ORDER BY issue.created_at DESC, issue.id DESC""",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


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
