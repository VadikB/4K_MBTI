"""Versioned product programs connecting organizations to admitted assessment sources."""
from __future__ import annotations

import hashlib
import json


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS assessment_program_definitions (
        id BIGSERIAL PRIMARY KEY,
        code TEXT NOT NULL,
        version TEXT NOT NULL,
        name TEXT NOT NULL,
        assignment_ref TEXT NOT NULL,
        mode TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('draft','published','retired')),
        assessment_configuration_id BIGINT NOT NULL REFERENCES assessment_configurations(id) ON DELETE RESTRICT,
        catalog_version_id BIGINT REFERENCES m5_catalogs(id) ON DELETE RESTRICT,
        source_refs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        definition_checksum TEXT NOT NULL,
        published_by_user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT,
        published_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(code,version)
    )""")
    connection.execute("ALTER TABLE assessment_program_definitions ADD COLUMN IF NOT EXISTS catalog_version_id BIGINT")
    connection.execute("ALTER TABLE assessment_program_definitions ADD COLUMN IF NOT EXISTS source_refs_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    connection.execute("""UPDATE assessment_program_definitions p SET catalog_version_id=c.catalog_version_id
        FROM assessment_configurations c WHERE p.assessment_configuration_id=c.id AND p.catalog_version_id IS NULL""")
    connection.execute("""UPDATE assessment_program_definitions p SET source_refs_json=jsonb_build_object(
            'methodology_version_id',c.methodology_version_id,
            'scenario_version_id',c.scenario_version_id,
            'prompt_bundle_checksum',c.prompt_bundle_checksum)
        FROM assessment_configurations c WHERE p.assessment_configuration_id=c.id
          AND p.source_refs_json='{}'::jsonb""")
    connection.execute("ALTER TABLE assessment_program_definitions ALTER COLUMN catalog_version_id SET NOT NULL")
    connection.execute("""DO $$ BEGIN
        IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='assessment_program_catalog_version_fk') THEN
            ALTER TABLE assessment_program_definitions ADD CONSTRAINT assessment_program_catalog_version_fk
              FOREIGN KEY(catalog_version_id) REFERENCES m5_catalogs(id) ON DELETE RESTRICT;
        END IF;
    END $$""")
    connection.execute("""CREATE TABLE IF NOT EXISTS assessment_program_allowed_roles (
        program_definition_id BIGINT NOT NULL REFERENCES assessment_program_definitions(id) ON DELETE RESTRICT,
        role_profile_version_id BIGINT NOT NULL REFERENCES assessment_role_profile_versions(id) ON DELETE RESTRICT,
        display_order INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(program_definition_id,role_profile_version_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS organization_assessment_program_connections (
        id BIGSERIAL PRIMARY KEY,
        organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
        program_definition_id BIGINT NOT NULL REFERENCES assessment_program_definitions(id) ON DELETE RESTRICT,
        connected_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
        operation_id TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL,
        is_current BOOLEAN NOT NULL DEFAULT TRUE,
        connected_at TIMESTAMP NOT NULL DEFAULT NOW(),
        superseded_at TIMESTAMP,
        UNIQUE(organization_id,operation_id)
    )""")
    connection.execute("""DO $$ DECLARE actor_constraint TEXT; delete_action "char"; BEGIN
        SELECT constraint_row.conname,constraint_row.confdeltype
          INTO actor_constraint,delete_action
        FROM pg_constraint constraint_row
        JOIN pg_attribute attribute
          ON attribute.attrelid=constraint_row.conrelid
         AND attribute.attnum=ANY(constraint_row.conkey)
        WHERE constraint_row.conrelid='organization_assessment_program_connections'::regclass
          AND constraint_row.confrelid='users'::regclass
          AND attribute.attname='connected_by_user_id' LIMIT 1;
        IF EXISTS (
            SELECT 1 FROM pg_attribute attribute
            WHERE attribute.attrelid='organization_assessment_program_connections'::regclass
              AND attribute.attname='connected_by_user_id' AND attribute.attnotnull
        ) OR actor_constraint IS NULL OR delete_action <> 'n' THEN
            ALTER TABLE organization_assessment_program_connections ALTER COLUMN connected_by_user_id DROP NOT NULL;
            IF actor_constraint IS NOT NULL THEN
                EXECUTE format('ALTER TABLE organization_assessment_program_connections DROP CONSTRAINT %I', actor_constraint);
            END IF;
            ALTER TABLE organization_assessment_program_connections ADD CONSTRAINT org_assessment_program_connected_by_fk
              FOREIGN KEY(connected_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
        END IF;
    END $$""")
    connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_org_assessment_program_current
        ON organization_assessment_program_connections(organization_id) WHERE is_current""")
    connection.execute("""CREATE OR REPLACE FUNCTION protect_published_assessment_program()
        RETURNS trigger AS $$ BEGIN
            IF TG_OP='DELETE' AND OLD.status IN ('published','retired') THEN
                RAISE EXCEPTION 'Published assessment program definitions are immutable';
            END IF;
            IF TG_OP='UPDATE' AND OLD.status IN ('published','retired') THEN
                IF NOT (OLD.status='published' AND NEW.status='retired'
                    AND ROW(NEW.code,NEW.version,NEW.name,NEW.assignment_ref,NEW.mode,
                            NEW.assessment_configuration_id,NEW.catalog_version_id,NEW.source_refs_json,NEW.definition_checksum,
                            NEW.published_by_user_id,NEW.published_at,NEW.created_at)
                      IS NOT DISTINCT FROM
                        ROW(OLD.code,OLD.version,OLD.name,OLD.assignment_ref,OLD.mode,
                            OLD.assessment_configuration_id,OLD.catalog_version_id,OLD.source_refs_json,OLD.definition_checksum,
                            OLD.published_by_user_id,OLD.published_at,OLD.created_at)) THEN
                    RAISE EXCEPTION 'Published assessment program definitions are immutable';
                END IF;
            END IF;
            RETURN COALESCE(NEW,OLD);
        END $$ LANGUAGE plpgsql""")
    connection.execute("DROP TRIGGER IF EXISTS trg_assessment_program_immutable ON assessment_program_definitions")
    connection.execute("""CREATE TRIGGER trg_assessment_program_immutable
        BEFORE UPDATE OR DELETE ON assessment_program_definitions
        FOR EACH ROW EXECUTE FUNCTION protect_published_assessment_program()""")
    connection.execute("""CREATE OR REPLACE FUNCTION protect_published_assessment_program_role()
        RETURNS trigger AS $$ DECLARE program_status TEXT; BEGIN
            SELECT status INTO program_status FROM assessment_program_definitions
              WHERE id=COALESCE(NEW.program_definition_id,OLD.program_definition_id);
            IF program_status IN ('published','retired') THEN
                RAISE EXCEPTION 'Published assessment program roles are immutable';
            END IF;
            RETURN COALESCE(NEW,OLD);
        END $$ LANGUAGE plpgsql""")
    connection.execute("DROP TRIGGER IF EXISTS trg_assessment_program_role_immutable ON assessment_program_allowed_roles")
    connection.execute("""CREATE TRIGGER trg_assessment_program_role_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON assessment_program_allowed_roles
        FOR EACH ROW EXECUTE FUNCTION protect_published_assessment_program_role()""")


def definition_checksum(*, code: str, version: str, name: str, assignment_ref: str,
                        mode: str, configuration_id: int, role_version_ids: list[int],
                        catalog_version_id: int | None = None,
                        source_refs: dict | None = None) -> str:
    payload = {'code': code, 'version': version, 'name': name,
        'assignment_ref': assignment_ref, 'mode': mode,
        'assessment_configuration_id': configuration_id,
        'catalog_version_id': catalog_version_id,
        'source_refs': source_refs or {},
        'role_profile_version_ids': sorted(role_version_ids)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def list_published(connection) -> list[dict]:
    rows = connection.execute("""SELECT p.id,p.code,p.version,p.name,p.assignment_ref,p.mode,
            p.assessment_configuration_id,p.catalog_version_id,p.source_refs_json,p.definition_checksum,p.published_at,
            COALESCE(jsonb_agg(jsonb_build_object(
              'version_id',rv.id,'code',r.code,'version',rv.version,
              'name',rv.definition_json->'description'->>'name') ORDER BY ar.display_order,rv.id)
              FILTER (WHERE rv.id IS NOT NULL),'[]'::jsonb) AS roles
        FROM assessment_program_definitions p
        LEFT JOIN assessment_program_allowed_roles ar ON ar.program_definition_id=p.id
        LEFT JOIN assessment_role_profile_versions rv ON rv.id=ar.role_profile_version_id
        LEFT JOIN assessment_role_profiles r ON r.id=rv.role_profile_id
        WHERE p.status='published'
        GROUP BY p.id ORDER BY p.code,p.version""").fetchall()
    return [dict(row) for row in rows]


def current_connection(connection, *, organization_id: int) -> dict | None:
    row = connection.execute("""SELECT c.id AS connection_id,c.organization_id,c.connected_at,
            p.id AS program_definition_id,p.code AS program_code,p.version AS program_version,
            p.name AS program_name,p.assignment_ref,p.mode,p.status AS program_status,
            p.assessment_configuration_id,p.catalog_version_id,p.source_refs_json,p.definition_checksum
        FROM organization_assessment_program_connections c
        JOIN assessment_program_definitions p ON p.id=c.program_definition_id
        WHERE c.organization_id=%s AND c.is_current=TRUE""", (organization_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result['roles'] = [dict(role) for role in connection.execute(
        """SELECT rv.id AS version_id,r.code,rv.version,
                  rv.definition_json->'description'->>'name' AS name
           FROM assessment_program_allowed_roles ar
           JOIN assessment_role_profile_versions rv ON rv.id=ar.role_profile_version_id
           JOIN assessment_role_profiles r ON r.id=rv.role_profile_id
           WHERE ar.program_definition_id=%s
           ORDER BY ar.display_order,rv.id""",
        (result['program_definition_id'],),
    ).fetchall()]
    return result


def connect(connection, *, organization_id: int, program_definition_id: int,
            actor_user_id: int, operation_id: str) -> dict:
    connection.execute("SELECT id FROM organizations WHERE id=%s FOR UPDATE", (organization_id,))
    program = connection.execute("""SELECT id,status FROM assessment_program_definitions
        WHERE id=%s""", (program_definition_id,)).fetchone()
    if not program or program['status'] != 'published':
        raise ValueError('PROGRAM_NOT_AVAILABLE')
    fingerprint = hashlib.sha256(f'{organization_id}:{program_definition_id}'.encode()).hexdigest()
    prior = connection.execute("""SELECT request_fingerprint FROM organization_assessment_program_connections
        WHERE organization_id=%s AND operation_id=%s""", (organization_id, operation_id)).fetchone()
    if prior:
        if prior['request_fingerprint'] != fingerprint:
            raise ValueError('PROGRAM_CONNECTION_IDEMPOTENCY_CONFLICT')
        row = connection.execute("""SELECT c.id AS connection_id,c.organization_id,c.connected_at,
                p.id AS program_definition_id,p.code AS program_code,p.version AS program_version,
                p.name AS program_name,p.assignment_ref,p.mode,p.status AS program_status,
                p.assessment_configuration_id,p.catalog_version_id,p.source_refs_json,p.definition_checksum
            FROM organization_assessment_program_connections c
            JOIN assessment_program_definitions p ON p.id=c.program_definition_id
            WHERE c.organization_id=%s AND c.operation_id=%s""",
            (organization_id,operation_id)).fetchone()
        return dict(row)
    current = current_connection(connection, organization_id=organization_id)
    if current and int(current['program_definition_id']) == program_definition_id:
        return current
    connection.execute("""UPDATE organization_assessment_program_connections
        SET is_current=FALSE,superseded_at=NOW()
        WHERE organization_id=%s AND is_current=TRUE""", (organization_id,))
    connection.execute("""INSERT INTO organization_assessment_program_connections
        (organization_id,program_definition_id,connected_by_user_id,operation_id,request_fingerprint)
        VALUES(%s,%s,%s,%s,%s)""",
        (organization_id, program_definition_id, actor_user_id, operation_id, fingerprint))
    return current_connection(connection, organization_id=organization_id)


def resolve(connection, *, organization_id: int, assignment_ref: str,
            role_profile_version_id: int | None = None) -> dict:
    program = current_connection(connection, organization_id=organization_id)
    if not program:
        raise ValueError('PROGRAM_NOT_CONNECTED')
    if program['program_status'] != 'published':
        raise ValueError('PROGRAM_NOT_AVAILABLE_FOR_NEW_ASSIGNMENTS')
    if program['assignment_ref'] != assignment_ref:
        raise ValueError('PROGRAM_ASSIGNMENT_REF_MISMATCH')
    roles = connection.execute("""SELECT ar.role_profile_version_id,r.code AS role_code,
            rv.status AS role_status,rv.methodology_version
        FROM assessment_program_allowed_roles ar
        JOIN assessment_role_profile_versions rv ON rv.id=ar.role_profile_version_id
        JOIN assessment_role_profiles r ON r.id=rv.role_profile_id
        WHERE ar.program_definition_id=%s ORDER BY ar.display_order,ar.role_profile_version_id""",
        (program['program_definition_id'],)).fetchall()
    selected = [row for row in roles if role_profile_version_id is None
        or int(row['role_profile_version_id']) == role_profile_version_id]
    if role_profile_version_id is None and len(roles) != 1:
        raise ValueError('PROGRAM_ROLE_SELECTION_REQUIRED')
    if len(selected) != 1 or selected[0]['role_status'] != 'published':
        raise ValueError('PROGRAM_ROLE_NOT_AVAILABLE')
    configuration = connection.execute("""SELECT c.code,c.status,c.catalog_version_id,
            catalog.status AS catalog_status,catalog.usage_scope AS catalog_usage_scope,
            catalog.organization_id AS catalog_organization_id
        FROM assessment_configurations c JOIN m5_catalogs catalog ON catalog.id=c.catalog_version_id
        WHERE c.id=%s""", (program['assessment_configuration_id'],)).fetchone()
    if not configuration or configuration['status'] != 'published':
        raise ValueError('PROGRAM_CONFIGURATION_NOT_AVAILABLE')
    if configuration['catalog_status'] != 'published' or configuration['catalog_usage_scope'] != 'assessment':
        raise ValueError('PROGRAM_CATALOG_NOT_AVAILABLE')
    if int(configuration['catalog_version_id']) != int(program['catalog_version_id']):
        raise ValueError('PROGRAM_CATALOG_VERSION_MISMATCH')
    catalog_org = configuration['catalog_organization_id']
    if catalog_org is not None and int(catalog_org) != organization_id:
        raise ValueError('PROGRAM_CATALOG_SCOPE_MISMATCH')
    return {**program, **dict(configuration), **dict(selected[0]),
        'role_profile_version_id': int(selected[0]['role_profile_version_id'])}
