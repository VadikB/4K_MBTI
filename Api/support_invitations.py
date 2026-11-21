"""Ограниченное чтение сохранённой строки персонального приглашения."""
import re

from Api import invitation_outcomes
from Api.public_origin import build_public_link


_PAGE_SIZE = 50
_REFERENCE = re.compile(r"INV-([1-9][0-9]{0,18})")
_ASSIGNMENT_REF = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,199}")

_SELECT = """
    SELECT i.id, i.organization_id, i.assignment_ref,
           i.delivery_status, i.delivery_error,
           i.created_at AT TIME ZONE 'UTC' AS created_at,
           i.expires_at AT TIME ZONE 'UTC' AS expires_at,
           i.sent_at AT TIME ZONE current_setting('TimeZone') AS sent_at,
           i.delivery_started_at AT TIME ZONE current_setting('TimeZone') AS delivery_started_at,
           i.used_at AT TIME ZONE current_setting('TimeZone') AS used_at,
           i.revoked_at AT TIME ZONE current_setting('TimeZone') AS revoked_at,
           statement_timestamp() AS read_at
    FROM organization_invitations i
    WHERE i.purpose = 'personal_registration'
      AND NULLIF(btrim(i.request_id), '') IS NOT NULL
      AND NULLIF(btrim(i.assignment_ref), '') IS NOT NULL
"""


def _project(row):
    delivery = row["delivery_status"]
    fact = invitation_outcomes.facts(delivery, row["delivery_error"])
    link = invitation_outcomes.link_status(
        used_at=row["used_at"], revoked_at=row["revoked_at"], expires_at=row["expires_at"], now=row["read_at"],
    )
    event_at = max(value for value in (
        row["created_at"], row["delivery_started_at"], row["sent_at"], row["used_at"], row["revoked_at"],
        row["expires_at"] if link == "expired" else None,
    ) if value is not None)
    assignment = row["assignment_ref"]
    return {
        "kind": "invitation",
        "reference": f"INV-{row['id']}",
        "organization_id": row["organization_id"],
        "assignment_ref": assignment if _ASSIGNMENT_REF.fullmatch(assignment) else None,
        "outcome": fact["outcome"],
        "reason_code": fact["reason_code"],
        "link_status": link,
        "started_at": row["created_at"].isoformat(),
        "sent_at": row["sent_at"].isoformat() if row["sent_at"] and fact["outcome"] == "accepted" else None,
        "expires_at": row["expires_at"].isoformat(),
        "used_at": row["used_at"].isoformat() if row["used_at"] else None,
        "last_confirmed_at": event_at.isoformat(),
        "read_at": row["read_at"].isoformat(),
        "source": "organization_invitations",
    }


def list_uncertain(connection, *, before=None, organization_id=None):
    rows = connection.execute(
        _SELECT + """
          AND i.delivery_status IN ('sending', 'uncertain')
          AND i.revoked_at IS NULL AND i.used_at IS NULL
          AND i.expires_at > (statement_timestamp() AT TIME ZONE 'UTC')
          AND (%(before)s::bigint IS NULL OR i.id < %(before)s)
          AND (%(organization_id)s::bigint IS NULL OR i.organization_id = %(organization_id)s)
        ORDER BY i.id DESC LIMIT %(limit)s
        """,
        {"before": before, "organization_id": organization_id, "limit": _PAGE_SIZE + 1},
    ).fetchall()
    return {
        "items": [_project(row) for row in rows[:_PAGE_SIZE]],
        "next_before": rows[_PAGE_SIZE - 1]["id"] if len(rows) > _PAGE_SIZE else None,
    }


def read(connection, reference):
    match = _REFERENCE.fullmatch(reference)
    if not match or int(match[1]) > 2**63 - 1:
        return None
    row = connection.execute(_SELECT + " AND i.id = %s", (int(match[1]),)).fetchone()
    return _project(row) if row else None


def handoff(problem, *, origin, mode, version):
    org_id = problem["organization_id"]
    url = build_public_link(origin, {"screen": "admin-organizations", "org": str(org_id)}, mode=mode)
    return "\n".join([
        "Проверка персонального приглашения",
        f"Контур: {mode} · {origin}",
        f"Версия продукта при чтении: {version}",
        f"Организация: #{org_id} · {url}",
        f"Назначение: {problem['assignment_ref'] or 'см. сохранённую запись'}",
        f"Номер приглашения: {problem['reference']}",
        f"Источник: {problem['source']}",
        f"Время создания: {problem['started_at']}",
        f"Исход отправки: {problem['outcome']} · {problem['reason_code']}",
        f"Состояние ссылки: {problem['link_status']}",
        f"Последний сохранённый факт: {problem['last_confirmed_at']}",
        f"Время чтения: {problem['read_at']}",
    ])
