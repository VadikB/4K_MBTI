from __future__ import annotations

import json
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.assessment_role_profiles import (
    bind_role_profile_to_session,
    create_organization_role_profile_draft,
    import_base_roles_draft,
    list_available_role_profiles,
    load_published_role_profile,
    get_selected_role_profile,
    select_role_profile_for_user,
)
from Api.database import ensure_role_profile_schema


PACKAGE_DIR = Path(__file__).resolve().parents[2] / "assessment_definitions/role_profiles/competencies_4k/1.1"


@pytest.mark.integration
def test_base_and_organization_roles_are_versioned_visible_and_immutable(test_database_url) -> None:
    package = json.loads((PACKAGE_DIR / "base_roles.json").read_text(encoding="utf-8"))
    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute("CREATE TABLE users (id BIGINT PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE user_sessions (id BIGINT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id), "
            "execution_snapshot_json JSONB, execution_checksum TEXT)"
        )
        connection.execute("INSERT INTO users VALUES (7), (8), (9)")
        connection.execute("CREATE TABLE organizations (id BIGINT PRIMARY KEY, is_active BOOLEAN NOT NULL)")
        connection.execute("INSERT INTO organizations VALUES (10, TRUE), (20, TRUE)")
        connection.execute(
            "CREATE TABLE organization_memberships (user_id BIGINT REFERENCES users(id), "
            "organization_id BIGINT REFERENCES organizations(id), UNIQUE (user_id, organization_id))"
        )
        connection.execute("INSERT INTO organization_memberships VALUES (7, 10), (9, 10), (8, 20)")
        ensure_role_profile_schema(connection)
        base_ids = import_base_roles_draft(connection, package, manifest)
        assert len(base_ids) == 6
        assert import_base_roles_draft(connection, package, manifest) == base_ids
        assert list_available_role_profiles(connection, user_id=7) == []
        with pytest.raises(ValueError, match="published"):
            select_role_profile_for_user(connection, user_id=7, version_id=base_ids[0])

        connection.execute(
            "UPDATE assessment_role_profile_versions SET status = 'published' WHERE id = ANY(%s)",
            (base_ids,),
        )
        assert len(list_available_role_profiles(connection, user_id=7)) == 6

        definition = {
            "schema_version": 1,
            "kind": "role_profile",
            "methodology_version": "1.1",
            "code": "org_10_research_coordinator",
            "description": dict(package["base_roles"][1]["description"]),
            "card": dict(package["base_roles"][1]["card"]),
        }
        definition["description"]["name"] = "Координатор исследований"
        organization_role_id = create_organization_role_profile_draft(
            connection,
            organization_id=10,
            definition=definition,
            provenance={"formation_method": "interview", "sources": ["confirmed role interview"]},
            base_role_version_id=base_ids[1],
        )
        with pytest.raises(ValueError, match="already exists"):
            create_organization_role_profile_draft(
                connection,
                organization_id=10,
                definition=definition,
                provenance={"formation_method": "interview", "sources": ["confirmed role interview"]},
            )
        assert len(list_available_role_profiles(connection, user_id=7)) == 6
        connection.execute(
            "UPDATE assessment_role_profile_versions SET status = 'published' WHERE id = %s",
            (organization_role_id,),
        )
        assert len(list_available_role_profiles(connection, user_id=7)) == 7
        assert len(list_available_role_profiles(connection, user_id=9)) == 7
        assert len(list_available_role_profiles(connection, user_id=8)) == 6
        assert load_published_role_profile(connection, organization_role_id)["code"] == definition["code"]
        assert select_role_profile_for_user(connection, user_id=7, version_id=organization_role_id)["id"] == organization_role_id
        assert get_selected_role_profile(connection, user_id=7)["id"] == organization_role_id
        assert select_role_profile_for_user(connection, user_id=9, version_id=organization_role_id)["id"] == organization_role_id
        with pytest.raises(ValueError, match="organization member"):
            select_role_profile_for_user(connection, user_id=8, version_id=organization_role_id)

        other_organization_role_id = create_organization_role_profile_draft(
            connection,
            organization_id=20,
            definition=definition,
            provenance={"formation_method": "documents", "sources": ["approved role description"]},
        )
        connection.execute(
            "UPDATE assessment_role_profile_versions SET status = 'published' WHERE id = %s",
            (other_organization_role_id,),
        )
        assert len(list_available_role_profiles(connection, user_id=7)) == 7
        assert len(list_available_role_profiles(connection, user_id=8)) == 7
        connection.execute("INSERT INTO organization_memberships VALUES (7, 20)")
        assert len(list_available_role_profiles(connection, user_id=7)) == 8
        connection.execute("DELETE FROM organization_memberships WHERE user_id = 7 AND organization_id = 20")

        with pytest.raises(psycopg.Error, match="immutable"):
            with connection.transaction():
                connection.execute(
                    "UPDATE assessment_role_profile_versions SET checksum = 'changed' WHERE id = %s",
                    (organization_role_id,),
                )
        assert load_published_role_profile(connection, organization_role_id)["checksum"] != "changed"
        connection.execute(
            "INSERT INTO user_sessions (id, user_id, execution_snapshot_json) VALUES (42, 7, %s::jsonb)",
            (json.dumps({"methodology": {"definition": {"methodology_version": "1.1"}}}),),
        )
        frozen = bind_role_profile_to_session(connection, session_id=42, user_id=7, version_id=organization_role_id)
        assert frozen["role_profile"]["definition"]["description"]["name"] == "Координатор исследований"
        assert frozen["role_profile"]["organization_id"] == 10
        assert bind_role_profile_to_session(connection, session_id=42, user_id=7, version_id=organization_role_id) == frozen
        assert connection.execute("SELECT role_profile_version_id FROM user_sessions WHERE id = 42").fetchone()["role_profile_version_id"] == organization_role_id
        with pytest.raises(ValueError, match="session does not belong"):
            bind_role_profile_to_session(connection, session_id=42, user_id=8, version_id=organization_role_id)
        connection.execute("DELETE FROM organization_memberships WHERE user_id = 7 AND organization_id = 10")
        assert len(list_available_role_profiles(connection, user_id=7)) == 6
        assert get_selected_role_profile(connection, user_id=7) is None
        assert bind_role_profile_to_session(connection, session_id=42, user_id=7, version_id=organization_role_id) == frozen
        connection.rollback()
