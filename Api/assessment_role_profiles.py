"""Versioned M3 RoleProfile storage, separate from legacy numeric role IDs."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from Api.assessment_configuration import definition_checksum
from scripts.build_m3_base_roles import CARD_FIELDS, DESCRIPTION_FIELDS, validate_package


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def role_checksum(definition: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(definition).encode("utf-8")).hexdigest()


def validate_role_definition(definition: dict[str, Any]) -> None:
    if definition.get("schema_version") != 1 or definition.get("methodology_version") != "1.1":
        raise ValueError("RoleProfile must use the M3 1.1 contract.")
    if definition.get("kind") not in {"base_role", "role_profile"} or not str(definition.get("code") or "").strip():
        raise ValueError("RoleProfile kind and code are required.")
    for field, names in (("description", DESCRIPTION_FIELDS), ("card", CARD_FIELDS)):
        value = definition.get(field)
        expected = {name for _, name in names}
        if not isinstance(value, dict) or set(value) != expected or not all(
            isinstance(item, str) and item.strip() for item in value.values()
        ):
            raise ValueError(f"RoleProfile {field} is incomplete.")


def _require_organization_membership(connection, *, user_id: int, organization_id: int) -> None:
    row = connection.execute(
        """
        SELECT 1
        FROM organization_memberships membership
        JOIN organizations organization ON organization.id = membership.organization_id
        WHERE membership.user_id = %s AND membership.organization_id = %s
          AND organization.is_active = TRUE
        """,
        (user_id, organization_id),
    ).fetchone()
    if row is None:
        raise ValueError("RoleProfile is not available to this organization member.")


def create_organization_role_profile_draft(
    connection,
    *,
    organization_id: int,
    definition: dict[str, Any],
    provenance: dict[str, Any],
    base_role_version_id: int | None = None,
) -> int:
    """Create an organization role without changing the normative six BaseRoles."""
    validate_role_definition(definition)
    if definition["kind"] != "role_profile" or organization_id <= 0:
        raise ValueError("An organization RoleProfile and organization are required.")
    if not isinstance(provenance, dict) or not provenance.get("formation_method") or not provenance.get("sources"):
        raise ValueError("RoleProfile formation method and sources are required.")
    organization = connection.execute(
        "SELECT id FROM organizations WHERE id = %s AND is_active = TRUE",
        (organization_id,),
    ).fetchone()
    if organization is None:
        raise ValueError("An active organization is required.")
    existing = connection.execute(
        "SELECT id FROM assessment_role_profiles WHERE scope = 'organization' AND organization_id = %s AND code = %s",
        (organization_id, definition["code"]),
    ).fetchone()
    if existing is not None:
        raise ValueError("RoleProfile code already exists in this organization.")
    if base_role_version_id is not None:
        base = load_published_role_profile(connection, base_role_version_id)
        if base["definition"]["kind"] != "base_role":
            raise ValueError("The adaptation source must be a published BaseRole.")
    profile = connection.execute(
        """
        INSERT INTO assessment_role_profiles (code, name, scope, organization_id)
        VALUES (%s, %s, 'organization', %s)
        RETURNING id
        """,
        (definition["code"], definition["description"]["name"], organization_id),
    ).fetchone()
    row = connection.execute(
        """
        INSERT INTO assessment_role_profile_versions (
            role_profile_id, version, status, methodology_version,
            definition_json, source_manifest_json, checksum, base_role_version_id
        ) VALUES (%s, 1, 'draft', '1.1', %s::jsonb, %s::jsonb, %s, %s)
        RETURNING id
        """,
        (
            int(profile["id"]), canonical_json(definition), canonical_json(provenance),
            role_checksum(definition), base_role_version_id,
        ),
    ).fetchone()
    return int(row["id"])


def import_base_roles_draft(connection, package: dict[str, Any], manifest: dict[str, Any]) -> list[int]:
    """Import M3 BaseRoles as draft v1; reject divergent repeats instead of overwriting."""
    validate_package(package)
    if manifest.get("methodology_version") != "1.1" or manifest.get("status") != "draft":
        raise ValueError("M3 manifest must describe a 1.1 draft.")
    artifact = manifest.get("artifact") or {}
    expected_content = json.dumps(package, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if artifact.get("name") != "base_roles.json" or artifact.get("sha256") != hashlib.sha256(expected_content.encode()).hexdigest():
        raise ValueError("M3 manifest does not match BaseRoles package.")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or len(sources) != 2 or any(
        not isinstance(source, dict) or not source.get("name") or len(str(source.get("sha256") or "")) != 64
        for source in sources
    ):
        raise ValueError("M3 manifest must identify two source documents.")

    version_ids = []
    for role in package["base_roles"]:
        code = role["code"]
        definition = {"schema_version": 1, "kind": "base_role", "methodology_version": "1.1", **role}
        profile_row = connection.execute(
            """
            INSERT INTO assessment_role_profiles (code, name, scope)
            VALUES (%s, %s, 'base')
            ON CONFLICT DO NOTHING
            RETURNING id, name, scope
            """,
            (code, role["description"]["name"]),
        ).fetchone()
        if profile_row is None:
            profile_row = connection.execute(
                "SELECT id, name, scope FROM assessment_role_profiles WHERE code = %s AND scope = 'base'",
                (code,),
            ).fetchone()
        if profile_row is None or profile_row["scope"] != "base" or profile_row["name"] != role["description"]["name"]:
            raise ValueError(f"Existing RoleProfile identity differs for {code}.")
        profile_id = int(profile_row["id"])
        checksum = role_checksum(definition)
        validate_role_definition(definition)
        row = connection.execute(
            """
            INSERT INTO assessment_role_profile_versions (
                role_profile_id, version, status, methodology_version,
                definition_json, source_manifest_json, checksum
            ) VALUES (%s, 1, 'draft', '1.1', %s::jsonb, %s::jsonb, %s)
            ON CONFLICT (role_profile_id, version) DO NOTHING
            RETURNING id, checksum, status
            """,
            (profile_id, canonical_json(definition), canonical_json(manifest), checksum),
        ).fetchone()
        if row is None:
            row = connection.execute(
                """
                SELECT id, checksum, status
                FROM assessment_role_profile_versions
                WHERE role_profile_id = %s AND version = 1
                """,
                (profile_id,),
            ).fetchone()
        if row is None or row["checksum"] != checksum or row["status"] != "draft":
            raise ValueError(f"Existing RoleProfile {code} v1 differs or is already published.")
        version_ids.append(int(row["id"]))
    return version_ids


def load_published_role_profile(connection, version_id: int) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT profile.id AS profile_id, profile.code, profile.scope, profile.organization_id, version.version, version.status,
               version.methodology_version, version.definition_json, version.checksum
        FROM assessment_role_profile_versions version
        JOIN assessment_role_profiles profile ON profile.id = version.role_profile_id
        WHERE version.id = %s
        """,
        (version_id,),
    ).fetchone()
    if row is None or row["status"] != "published":
        raise ValueError("A published RoleProfile version is required.")
    definition = dict(row["definition_json"] or {})
    validate_role_definition(definition)
    if (row["scope"] == "base") != (definition["kind"] == "base_role"):
        raise ValueError("RoleProfile scope and kind are inconsistent.")
    if definition.get("code") != row["code"] or definition.get("methodology_version") != row["methodology_version"]:
        raise ValueError("RoleProfile identity is inconsistent.")
    if role_checksum(definition) != row["checksum"]:
        raise ValueError("RoleProfile checksum mismatch.")
    return {
        "id": version_id,
        "profile_id": int(row["profile_id"]),
        "code": str(row["code"]),
        "scope": str(row["scope"]),
        "organization_id": row["organization_id"],
        "version": int(row["version"]),
        "definition": definition,
        "checksum": row["checksum"],
    }


def list_available_role_profiles(connection, *, user_id: int) -> list[dict[str, Any]]:
    """Offer BaseRoles and roles of the user's active organizations."""
    rows = connection.execute(
        """
        SELECT version.id
        FROM assessment_role_profile_versions version
        JOIN assessment_role_profiles profile ON profile.id = version.role_profile_id
        WHERE version.status = 'published'
          AND version.methodology_version = '1.1'
          AND (
              profile.scope = 'base'
              OR EXISTS (
                  SELECT 1 FROM organization_memberships membership
                  JOIN organizations organization ON organization.id = membership.organization_id
                  WHERE membership.user_id = %s
                    AND membership.organization_id = profile.organization_id
                    AND organization.is_active = TRUE
              )
          )
        ORDER BY profile.scope ASC, profile.code ASC, version.version DESC
        """,
        (user_id,),
    ).fetchall()
    seen: set[int] = set()
    result = []
    for row in rows:
        role = load_published_role_profile(connection, int(row["id"]))
        if role["profile_id"] not in seen:
            result.append(role)
            seen.add(role["profile_id"])
    return result


def select_role_profile_for_user(connection, *, user_id: int, version_id: int) -> dict[str, Any]:
    """Persist a published M3 role visible to this user, without legacy role IDs."""
    role = load_published_role_profile(connection, version_id)
    if role["scope"] == "organization":
        _require_organization_membership(connection, user_id=user_id, organization_id=int(role["organization_id"]))
    row = connection.execute(
        """
        UPDATE users
        SET selected_role_profile_version_id = %s
        WHERE id = %s
        RETURNING id
        """,
        (version_id, user_id),
    ).fetchone()
    if row is None:
        raise ValueError("User not found.")
    return role


def get_selected_role_profile(connection, *, user_id: int) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT users.selected_role_profile_version_id, version.status
        FROM users
        LEFT JOIN assessment_role_profile_versions version
          ON version.id = users.selected_role_profile_version_id
        WHERE users.id = %s
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        raise ValueError("User not found.")
    version_id = row["selected_role_profile_version_id"]
    if version_id is None or row["status"] != "published":
        return None
    role = load_published_role_profile(connection, int(version_id))
    if role["scope"] == "organization":
        try:
            _require_organization_membership(connection, user_id=user_id, organization_id=int(role["organization_id"]))
        except ValueError:
            return None
    return role


def bind_role_profile_to_session(connection, *, session_id: int, user_id: int, version_id: int) -> dict[str, Any]:
    """Freeze the published role definition in a 1.1 session before case generation."""
    role = load_published_role_profile(connection, version_id)
    session = connection.execute(
        """
        SELECT user_id, role_profile_version_id, execution_snapshot_json
        FROM user_sessions WHERE id = %s FOR UPDATE
        """,
        (session_id,),
    ).fetchone()
    if session is None or int(session["user_id"]) != user_id:
        raise ValueError("Assessment session does not belong to this user.")
    existing_version = session["role_profile_version_id"]
    snapshot = session["execution_snapshot_json"]
    if not isinstance(snapshot, dict) or str((snapshot.get("methodology") or {}).get("definition", {}).get("methodology_version")) != "1.1":
        raise ValueError("RoleProfile can only be bound to a methodology 1.1 snapshot.")
    if existing_version is not None:
        if int(existing_version) != version_id:
            raise ValueError("A different RoleProfile is already frozen in this session.")
        if snapshot.get("role_profile", {}).get("checksum") != role["checksum"]:
            raise ValueError("Frozen RoleProfile checksum mismatch.")
        return snapshot
    if role["scope"] == "organization":
        _require_organization_membership(connection, user_id=user_id, organization_id=int(role["organization_id"]))
    frozen = dict(snapshot)
    frozen["role_profile"] = {key: role[key] for key in ("id", "code", "version", "organization_id", "definition", "checksum")}
    connection.execute(
        """
        UPDATE user_sessions
        SET role_profile_version_id = %s,
            execution_snapshot_json = %s::jsonb,
            execution_checksum = %s
        WHERE id = %s AND user_id = %s AND role_profile_version_id IS NULL
        """,
        (version_id, canonical_json(frozen), definition_checksum(frozen), session_id, user_id),
    )
    return frozen
