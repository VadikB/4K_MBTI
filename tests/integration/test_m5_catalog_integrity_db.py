from __future__ import annotations

import json
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_case_runtime import checksum
from Api.m5_catalog_integrity import catalog_readback, publication_plan, publish_catalog


pytestmark = pytest.mark.integration


def evidence(case, scope, *, result="PASS", origin="human_review", usage_scopes=None):
    payload = {
        "schema_version": 1,
        "eligibility": "user_admission",
        "scope": scope,
        "result": result,
        "case_ref": {"id": case["case_id"], "version": case["case_version"],
                     "checksum": case["content_checksum"]},
        "base_role": case["base_role"],
        "usage_scopes": usage_scopes or ["assessment", "qa"],
        "origin": {"type": origin, "actor_ref": "review:owned-test"},
    }
    return payload, checksum(payload)


def test_catalog_publication_is_exact_idempotent_and_immutable(test_database_url):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "task1011_pytest_" + uuid4().hex
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        connection.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (7),(8)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO organizations VALUES (11)")
        connection.execute("CREATE TABLE assessment_personalized_profiles(id BIGINT PRIMARY KEY)")
        ensure_m5_runtime_schema(connection)
        manifest = {"dependencies": {"m2": "b" * 64}}
        package = connection.execute(
            """INSERT INTO m5_packages(package_id,package_version,schema_version,status,source_checksum,
               package_checksum,manifest_json,package_json,runtime_rules_json)
               VALUES ('pkg','1.0',2,'FROZEN',%s,%s,%s::jsonb,'{}'::jsonb,'{}'::jsonb) RETURNING id""",
            ("c" * 64, "d" * 64, json.dumps(manifest)),
        ).fetchone()
        content = {"unresolved_decisions": []}
        case = connection.execute(
            """INSERT INTO m5_case_versions(package_id,case_id,case_version,status,base_role,content_json,content_checksum)
               VALUES (%s,'CASE-01','1.0','FROZEN','team_lead',%s::jsonb,%s) RETURNING *""",
            (package["id"], json.dumps(content), checksum(content)),
        ).fetchone()
        for scope in ("case_format", "case_dialogue", "assessment_situation"):
            payload, digest = evidence(case, scope)
            connection.execute(
                """INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum)
                   VALUES (%s,%s,'PASS',%s::jsonb,%s)""",
                (case["id"], scope, json.dumps(payload), digest),
            )

        plan = publication_plan(connection, package_db_id=package["id"],
                                case_version_ids=[case["id"]], usage_scope="assessment",
                                organization_id=11)
        assert plan["publishable"] is True
        dry_run = publish_catalog(
            connection, catalog_id="controlled", catalog_version="1.0",
            package_db_id=package["id"], case_version_ids=[case["id"]],
            usage_scope="assessment", organization_id=11, published_by=7,
            decision_basis="owned integration review", idempotency_key="publish-1", dry_run=True,
        )
        assert dry_run["dry_run"] is True
        published = publish_catalog(
            connection, catalog_id="controlled", catalog_version="1.0",
            package_db_id=package["id"], case_version_ids=[case["id"]],
            usage_scope="assessment", organization_id=11, published_by=7,
            decision_basis="owned integration review", idempotency_key="publish-1",
        )
        repeated = publish_catalog(
            connection, catalog_id="controlled", catalog_version="1.0",
            package_db_id=package["id"], case_version_ids=[case["id"]],
            usage_scope="assessment", organization_id=11, published_by=7,
            decision_basis="owned integration review", idempotency_key="publish-1",
        )
        assert repeated["idempotent"] is True
        assert catalog_readback(connection, published["catalog_db_id"])["manifest_checksum"] == published["manifest_checksum"]
        with pytest.raises(psycopg.Error, match="Published M5 catalog is immutable"):
            with connection.transaction():
                connection.execute("UPDATE m5_catalogs SET catalog_version='2.0' WHERE id=%s",
                                   (published["catalog_db_id"],))

        failing, failing_digest = evidence(case, "case_dialogue", result="FAIL")
        connection.execute(
            """INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum)
               VALUES (%s,'case_dialogue','FAIL',%s::jsonb,%s)""",
            (case["id"], json.dumps(failing), failing_digest),
        )
        blocked = publication_plan(connection, package_db_id=package["id"],
                                   case_version_ids=[case["id"]], usage_scope="assessment")
        assert blocked["publishable"] is False
        assert "QA_EVIDENCE_FAIL:case_dialogue" in blocked["decisions"][0]["reasons"]
        connection.rollback()
