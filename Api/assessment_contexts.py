"""M4 context validation and immutable PersonalizedProfile assembly."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from Api.assessment_role_profiles import load_published_role_profile
from scripts.build_m4_context_package import ORGANIZATION_REQUIRED_FIELDS


BLOCKING_CONFLICTS = {"role_selection", "authority", "mandatory_organization_constraint"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def context_checksum(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_organization_context(definition: dict[str, Any]) -> None:
    missing = [key for key in ORGANIZATION_REQUIRED_FIELDS if not str(definition.get(key) or "").strip()]
    if missing:
        raise ValueError(f"OrganizationContext required fields are missing: {', '.join(missing)}")


def validate_user_context(identity: dict[str, Any], professional: dict[str, Any]) -> None:
    if not str(identity.get("full_name") or "").strip():
        raise ValueError("UserContext full_name is required.")
    if not isinstance(professional, dict):
        raise ValueError("UserContext professional context must be an object.")


def build_personalized_profile(
    *,
    organization_id: int,
    organization_context: dict[str, Any],
    organization_context_ref: dict[str, Any],
    role_profile: dict[str, Any],
    role_profile_ref: dict[str, Any],
    user_identity: dict[str, Any],
    user_context: dict[str, Any],
    user_context_ref: dict[str, Any],
    conflicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the M4 snapshot while keeping identity and contacts outside runtime content."""
    validate_organization_context(organization_context)
    validate_user_context(user_identity, user_context)
    if role_profile.get("methodology_version") != "1.1":
        raise ValueError("M4 requires a methodology 1.1 RoleProfile.")
    conflicts = [dict(item) for item in (conflicts or [])]
    blocking = any(item.get("type") in BLOCKING_CONFLICTS and not item.get("resolved") for item in conflicts)
    profile = {
        "schema_version": 1,
        "methodology_version": "1.1",
        "organization_id": organization_id,
        "status": "blocked" if blocking else "ready",
        "sources": {
            "organization_context": dict(organization_context_ref),
            "role_profile": dict(role_profile_ref),
            "user_context": dict(user_context_ref),
        },
        "content": {
            "organization_context": dict(organization_context),
            "role_profile": dict(role_profile),
            "user_context": dict(user_context),
        },
        "provenance": {
            "organization_context": "organization",
            "role_profile": "role_profile",
            "user_context": "user",
        },
        "conflicts": conflicts,
    }
    profile["checksum"] = context_checksum(profile)
    return profile


def load_single_active_organization_id(connection, *, user_id: int) -> int:
    rows = connection.execute(
        """
        SELECT membership.organization_id
        FROM organization_memberships membership
        JOIN organizations organization ON organization.id = membership.organization_id
        WHERE membership.user_id = %s AND organization.is_active = TRUE
        """,
        (user_id,),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("M4 requires exactly one active organization membership.")
    return int(rows[0]["organization_id"])


def create_organization_context_draft(
    connection,
    *,
    organization_id: int,
    definition: dict[str, Any],
    source_manifest: dict[str, Any] | None = None,
    code: str = "default",
) -> int:
    validate_organization_context(definition)
    parent = connection.execute(
        """
        INSERT INTO assessment_organization_contexts (organization_id, code)
        VALUES (%s, %s)
        ON CONFLICT (organization_id, code) DO UPDATE SET code = EXCLUDED.code
        RETURNING id
        """,
        (organization_id, code),
    ).fetchone()
    connection.execute("SELECT id FROM assessment_organization_contexts WHERE id = %s FOR UPDATE", (int(parent["id"]),))
    version = connection.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM assessment_organization_context_versions "
        "WHERE organization_context_id = %s",
        (int(parent["id"]),),
    ).fetchone()["version"]
    row = connection.execute(
        """
        INSERT INTO assessment_organization_context_versions (
            organization_context_id, version, status, definition_json, source_manifest_json, checksum
        ) VALUES (%s, %s, 'draft', %s::jsonb, %s::jsonb, %s) RETURNING id
        """,
        (
            int(parent["id"]), int(version), canonical_json(definition),
            canonical_json(source_manifest or {}), context_checksum(definition),
        ),
    ).fetchone()
    return int(row["id"])


def publish_organization_context(connection, *, version_id: int, confirmed_by_user_id: int) -> None:
    row = connection.execute(
        "SELECT status, definition_json FROM assessment_organization_context_versions WHERE id = %s FOR UPDATE",
        (version_id,),
    ).fetchone()
    if row is None or row["status"] not in {"draft", "ready_for_review"}:
        raise ValueError("An editable OrganizationContext version is required.")
    validate_organization_context(dict(row["definition_json"] or {}))
    connection.execute(
        "UPDATE assessment_organization_context_versions SET status = 'published', "
        "confirmed_by_user_id = %s, confirmed_at = NOW() WHERE id = %s",
        (confirmed_by_user_id, version_id),
    )


def create_user_context_draft(
    connection,
    *,
    user_id: int,
    identity: dict[str, Any],
    professional: dict[str, Any] | None = None,
) -> int:
    professional = professional or {}
    validate_user_context(identity, professional)
    organization_id = load_single_active_organization_id(connection, user_id=user_id)
    parent = connection.execute(
        """
        INSERT INTO assessment_user_contexts (user_id, organization_id)
        VALUES (%s, %s)
        ON CONFLICT (user_id, organization_id) DO UPDATE SET organization_id = EXCLUDED.organization_id
        RETURNING id
        """,
        (user_id, organization_id),
    ).fetchone()
    connection.execute("SELECT id FROM assessment_user_contexts WHERE id = %s FOR UPDATE", (int(parent["id"]),))
    version = connection.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM assessment_user_context_versions "
        "WHERE user_context_id = %s",
        (int(parent["id"]),),
    ).fetchone()["version"]
    checksum = context_checksum({"identity": identity, "professional": professional})
    row = connection.execute(
        """
        INSERT INTO assessment_user_context_versions (
            user_context_id, version, status, identity_json, professional_context_json, checksum
        ) VALUES (%s, %s, 'draft', %s::jsonb, %s::jsonb, %s) RETURNING id
        """,
        (int(parent["id"]), int(version), canonical_json(identity), canonical_json(professional), checksum),
    ).fetchone()
    return int(row["id"])


def confirm_user_context(connection, *, version_id: int, user_id: int) -> None:
    row = connection.execute(
        """
        SELECT version.status, version.identity_json, version.professional_context_json
        FROM assessment_user_context_versions version
        JOIN assessment_user_contexts context ON context.id = version.user_context_id
        WHERE version.id = %s AND context.user_id = %s FOR UPDATE
        """,
        (version_id, user_id),
    ).fetchone()
    if row is None or row["status"] not in {"draft", "needs_clarification"}:
        raise ValueError("An editable UserContext owned by the user is required.")
    validate_user_context(dict(row["identity_json"] or {}), dict(row["professional_context_json"] or {}))
    connection.execute(
        "UPDATE assessment_user_context_versions SET status = 'confirmed', "
        "confirmed_by_user_id = %s, confirmed_at = NOW() WHERE id = %s",
        (user_id, version_id),
    )


def assign_role_profile(
    connection,
    *,
    user_id: int,
    role_profile_version_id: int,
    determined_by: str,
    determined_by_user_id: int,
) -> int:
    if determined_by not in {"user", "organization"}:
        raise ValueError("RoleProfile determined_by must be user or organization.")
    organization_id = load_single_active_organization_id(connection, user_id=user_id)
    role = load_published_role_profile(connection, role_profile_version_id)
    if role["organization_id"] not in (None, organization_id):
        raise ValueError("RoleProfile is not available in the active organization.")
    connection.execute(
        "UPDATE assessment_role_profile_assignments SET superseded_at = NOW() "
        "WHERE user_id = %s AND superseded_at IS NULL",
        (user_id,),
    )
    row = connection.execute(
        """
        INSERT INTO assessment_role_profile_assignments (
            user_id, organization_id, role_profile_version_id,
            determined_by, determined_by_user_id
        ) VALUES (%s, %s, %s, %s, %s) RETURNING id
        """,
        (user_id, organization_id, role_profile_version_id, determined_by, determined_by_user_id),
    ).fetchone()
    connection.execute(
        "UPDATE users SET selected_role_profile_version_id = %s WHERE id = %s",
        (role_profile_version_id, user_id),
    )
    return int(row["id"])


def create_personalized_profile(
    connection,
    *,
    user_id: int,
    assessment_configuration_id: int,
    organization_context_version_id: int,
    role_profile_version_id: int,
    user_context_version_id: int,
    conflicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Freeze confirmed M4 sources for a methodology 1.1 assessment configuration."""
    organization_id = load_single_active_organization_id(connection, user_id=user_id)
    configuration = connection.execute(
        """
        SELECT methodology_version.definition_json
        FROM assessment_configurations configuration
        JOIN assessment_methodology_versions methodology_version
          ON methodology_version.id = configuration.methodology_version_id
        WHERE configuration.id = %s
          AND configuration.status = 'published'
          AND methodology_version.status = 'published'
        """,
        (assessment_configuration_id,),
    ).fetchone()
    methodology = dict(configuration["definition_json"] or {}) if configuration else {}
    if methodology.get("methodology_version") != "1.1":
        raise ValueError("A published methodology 1.1 configuration is required.")

    organization_row = connection.execute(
        """
        SELECT version.definition_json, version.checksum
        FROM assessment_organization_context_versions version
        JOIN assessment_organization_contexts context ON context.id = version.organization_context_id
        WHERE version.id = %s AND version.status = 'published' AND context.organization_id = %s
        """,
        (organization_context_version_id, organization_id),
    ).fetchone()
    if organization_row is None:
        raise ValueError("A published OrganizationContext for the active organization is required.")
    organization_definition = dict(organization_row["definition_json"] or {})
    if context_checksum(organization_definition) != organization_row["checksum"]:
        raise ValueError("OrganizationContext checksum mismatch.")

    user_row = connection.execute(
        """
        SELECT version.identity_json, version.professional_context_json, version.checksum
        FROM assessment_user_context_versions version
        JOIN assessment_user_contexts context ON context.id = version.user_context_id
        WHERE version.id = %s AND version.status = 'confirmed'
          AND context.user_id = %s AND context.organization_id = %s
        """,
        (user_context_version_id, user_id, organization_id),
    ).fetchone()
    if user_row is None:
        raise ValueError("A confirmed UserContext for the active organization is required.")
    user_identity = dict(user_row["identity_json"] or {})
    user_professional = dict(user_row["professional_context_json"] or {})
    if context_checksum({"identity": user_identity, "professional": user_professional}) != user_row["checksum"]:
        raise ValueError("UserContext checksum mismatch.")

    role = load_published_role_profile(connection, role_profile_version_id)
    if role["organization_id"] not in (None, organization_id):
        raise ValueError("RoleProfile is not available in the active organization.")
    snapshot = build_personalized_profile(
        organization_id=organization_id,
        organization_context=organization_definition,
        organization_context_ref={"version_id": organization_context_version_id, "checksum": organization_row["checksum"]},
        role_profile=role["definition"],
        role_profile_ref={"version_id": role_profile_version_id, "checksum": role["checksum"]},
        user_identity=user_identity,
        user_context=user_professional,
        user_context_ref={"version_id": user_context_version_id, "checksum": user_row["checksum"]},
        conflicts=conflicts,
    )
    row = connection.execute(
        """
        INSERT INTO assessment_personalized_profiles (
            user_id, organization_id, assessment_configuration_id,
            organization_context_version_id, role_profile_version_id, user_context_version_id,
            status, content_json, provenance_json, conflicts_json, checksum
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
        ON CONFLICT (user_id, assessment_configuration_id, checksum) DO UPDATE SET checksum = EXCLUDED.checksum
        RETURNING id
        """,
        (
            user_id, organization_id, assessment_configuration_id,
            organization_context_version_id, role_profile_version_id, user_context_version_id,
            snapshot["status"], canonical_json(snapshot["content"]), canonical_json(snapshot["provenance"]),
            canonical_json(snapshot["conflicts"]), snapshot["checksum"],
        ),
    ).fetchone()
    return {"id": int(row["id"]), **snapshot}
