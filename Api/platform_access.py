from __future__ import annotations

from Api.org_access import configured_superadmin_emails, normalize_email_for_access


LOCAL_SUPERADMIN_EMAIL = "admin@agent4k.local"


def has_platform_permission(connection, user, permission_code: str) -> bool:
    if user is None:
        return False
    email = normalize_email_for_access(getattr(user, "email", None))
    if email == LOCAL_SUPERADMIN_EMAIL or email in configured_superadmin_emails():
        return True
    row = connection.execute(
        """
        SELECT 1
        FROM user_platform_roles assignment
        JOIN platform_role_permissions role_permission
          ON role_permission.platform_role_id = assignment.platform_role_id
        JOIN platform_permissions permission
          ON permission.id = role_permission.permission_id
        WHERE assignment.user_id = %s
          AND assignment.revoked_at IS NULL
          AND permission.code = %s
        LIMIT 1
        """,
        (int(user.id), permission_code),
    ).fetchone()
    return row is not None


def require_platform_permission(connection, user, permission_code: str) -> None:
    if not has_platform_permission(connection, user, permission_code):
        raise PermissionError(f"Platform permission required: {permission_code}")
