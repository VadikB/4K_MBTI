"""Versioned M7 parameter sources and per-Cycle resolution."""
from __future__ import annotations

import json
from uuid import UUID, uuid4

from Api.m5_case_runtime import checksum
from Api.m7_planning_package import load_rules


PARAMETERS = ("time_budget_seconds", "calendar_window_seconds")


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_parameter_revisions (
        id UUID PRIMARY KEY, source_scope TEXT NOT NULL CHECK(source_scope IN('organization','program')),
        organization_id BIGINT NOT NULL, assessment_configuration_id BIGINT,
        revision_no INTEGER NOT NULL CHECK(revision_no>0), status TEXT NOT NULL CHECK(status IN('draft','published','retired')),
        values_json JSONB NOT NULL, values_checksum TEXT NOT NULL, created_by BIGINT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), published_at TIMESTAMPTZ,
        CHECK((source_scope='organization' AND assessment_configuration_id IS NULL) OR
              (source_scope='program' AND assessment_configuration_id IS NOT NULL)),
        UNIQUE(source_scope,organization_id,assessment_configuration_id,revision_no))""")
    connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_m7_active_parameter_revision
        ON m7_parameter_revisions(source_scope,organization_id,COALESCE(assessment_configuration_id,0))
        WHERE status='published'""")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_published_m7_parameter_change() RETURNS trigger AS $$
        BEGIN
          IF OLD.status='published' AND NOT (TG_OP='UPDATE' AND NEW.status='retired'
             AND NEW.values_json=OLD.values_json AND NEW.values_checksum=OLD.values_checksum
             AND NEW.source_scope=OLD.source_scope AND NEW.organization_id=OLD.organization_id
             AND NEW.assessment_configuration_id IS NOT DISTINCT FROM OLD.assessment_configuration_id
             AND NEW.revision_no=OLD.revision_no) THEN
            RAISE EXCEPTION 'Published M7 parameter revision is immutable';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
    connection.execute("DROP TRIGGER IF EXISTS immutable_published_m7_parameters ON m7_parameter_revisions")
    connection.execute("""CREATE TRIGGER immutable_published_m7_parameters BEFORE UPDATE OR DELETE
        ON m7_parameter_revisions FOR EACH ROW EXECUTE FUNCTION prevent_published_m7_parameter_change()""")


def _values(value: object) -> dict:
    if not isinstance(value, dict) or set(value) - set(PARAMETERS):
        raise ValueError("M7_PARAMETER_CONFIGURATION_INVALID")
    result = {}
    for name, raw in value.items():
        if type(raw) is not int or raw <= 0:
            raise ValueError("M7_PARAMETER_VALUE_INVALID")
        result[name] = raw
    if not result:
        raise ValueError("M7_PARAMETER_CONFIGURATION_INVALID")
    return result


def save_revision(connection, *, source_scope: str, organization_id: int,
                  assessment_configuration_id: int | None, values: dict,
                  created_by: int, publish: bool = True) -> dict:
    """Technical write seam; a full administrative editor is intentionally out of scope."""
    ensure_schema(connection)
    if source_scope not in {"organization", "program"}:
        raise ValueError("M7_PARAMETER_SCOPE_INVALID")
    if (source_scope == "organization") != (assessment_configuration_id is None):
        raise ValueError("M7_PARAMETER_SCOPE_INVALID")
    if connection.execute("SELECT 1 FROM organizations WHERE id=%s AND is_active=TRUE", (organization_id,)).fetchone() is None:
        raise ValueError("M7_PARAMETER_ORGANIZATION_NOT_ALLOWED")
    if assessment_configuration_id is not None and connection.execute(
        "SELECT 1 FROM assessment_configurations WHERE id=%s AND status='published'",
        (assessment_configuration_id,),
    ).fetchone() is None:
        raise ValueError("M7_PARAMETER_CONFIGURATION_NOT_ALLOWED")
    normalized = _values(values)
    current = _published(connection, scope=source_scope, organization_id=organization_id,
                         configuration_id=assessment_configuration_id)
    if publish and current and current["values_json"] == normalized:
        return current
    revision = connection.execute("""SELECT COALESCE(MAX(revision_no),0)+1 AS value
        FROM m7_parameter_revisions WHERE source_scope=%s AND organization_id=%s
          AND assessment_configuration_id IS NOT DISTINCT FROM %s""",
        (source_scope, organization_id, assessment_configuration_id)).fetchone()["value"]
    if publish:
        connection.execute("""UPDATE m7_parameter_revisions SET status='retired'
            WHERE source_scope=%s AND organization_id=%s
              AND assessment_configuration_id IS NOT DISTINCT FROM %s AND status='published'""",
            (source_scope, organization_id, assessment_configuration_id))
    row = connection.execute("""INSERT INTO m7_parameter_revisions
        (id,source_scope,organization_id,assessment_configuration_id,revision_no,status,
         values_json,values_checksum,created_by,published_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,CASE WHEN %s THEN NOW() END) RETURNING *""",
        (uuid4(), source_scope, organization_id, assessment_configuration_id, revision,
         "published" if publish else "draft", json.dumps(normalized), checksum(normalized),
         created_by, publish)).fetchone()
    return dict(row)


def _published(connection, *, scope: str, organization_id: int,
               configuration_id: int | None) -> dict | None:
    row = connection.execute("""SELECT * FROM m7_parameter_revisions
        WHERE source_scope=%s AND organization_id=%s
          AND assessment_configuration_id IS NOT DISTINCT FROM %s AND status='published'""",
        (scope, organization_id, configuration_id)).fetchone()
    if not row:
        return None
    value = dict(row)
    normalized = _values(value["values_json"])
    if checksum(normalized) != value["values_checksum"]:
        raise ValueError("M7_PARAMETER_CONFIGURATION_CHECKSUM_MISMATCH")
    value["values_json"] = normalized
    return value


def resolve(connection, *, personalized_profile_id: int, usage_scope: str,
            qa_overrides: dict | None = None) -> dict:
    ensure_schema(connection)
    profile_row = connection.execute("""SELECT to_jsonb(profile) AS value
        FROM assessment_personalized_profiles profile WHERE id=%s AND status='ready'""",
        (personalized_profile_id,)).fetchone()
    profile = dict(profile_row["value"]) if profile_row else None
    rules = load_rules()
    values = {name: int(rules[f"default_{name}"]) for name in PARAMETERS}
    sources = {name: {"kind":"method_default","artifact_id":rules["id"],
        "version":rules["version"],"checksum":rules["snapshot_checksum"]} for name in PARAMETERS}
    if profile and profile.get("organization_id") is not None and profile.get("assessment_configuration_id") is not None:
        organization_id = int(profile["organization_id"])
        configuration_id = int(profile["assessment_configuration_id"])
        for scope, config_id in (("organization", None), ("program", configuration_id)):
            revision = _published(connection, scope=scope, organization_id=organization_id,
                                  configuration_id=config_id)
            if not revision:
                continue
            for name, value in revision["values_json"].items():
                values[name] = value
                sources[name] = {"kind":scope,"revision_id":str(revision["id"]),
                    "revision_no":int(revision["revision_no"]),"checksum":revision["values_checksum"],
                    "organization_id":organization_id,"assessment_configuration_id":config_id}
    if qa_overrides:
        if usage_scope != "qa":
            raise ValueError("M7_PARAMETER_OVERRIDE_NOT_ALLOWED")
        for name, value in _values(qa_overrides).items():
            values[name] = value
            sources[name] = {"kind":"qa_explicit_override","authorized_scope":"superadmin_qa"}
    return {"values": values, "sources": sources,
            "resolved_checksum": checksum({"values":values,"sources":sources})}
